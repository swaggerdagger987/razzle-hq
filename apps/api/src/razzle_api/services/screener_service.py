"""Screener service: aggregate season totals from player_week_stats."""

import sqlalchemy as sa
from sqlalchemy.orm import Session

from razzle_api.domain.scoring.config import ScoringRules
from razzle_api.domain.scoring.engine import PlayerWeekStats, score_week
from razzle_api.ingest.nflverse import player_week_stats_table, players_table

# Columns that are aggregated via SUM in the screener query.
SCREENER_STAT_COLS = [
    "pass_att",
    "pass_cmp",
    "pass_yd",
    "pass_td",
    "pass_int",
    "rush_att",
    "rush_yd",
    "rush_td",
    "target",
    "rec",
    "rec_yd",
    "rec_td",
    "fumble_lost",
]

# Allowed sort keys — maps the API param to the SQLAlchemy column expression.
# Built lazily so the dict is created once at import.
_SORT_KEY_NAMES = {"name", "games", "fantasy_points", *SCREENER_STAT_COLS}


def _compute_fantasy_points(row: dict, scoring_rules: ScoringRules) -> float:
    """Compute fantasy points for a season-total row using scoring rules.

    The screener row holds season totals (already summed). We treat the totals
    as a single synthetic week so we can pass them to score_week without
    refetching individual week rows. This is semantically equivalent to
    summing score_week() across all weeks because score_week is linear
    (no per-week bonuses like 100-yd game bonuses are applied at this layer).
    """
    stats = PlayerWeekStats(
        pass_att=row.get("pass_att", 0.0),
        pass_yd=row.get("pass_yd", 0.0),
        pass_td=row.get("pass_td", 0.0),
        pass_int=row.get("pass_int", 0.0),
        rush_att=row.get("rush_att", 0.0),
        rush_yd=row.get("rush_yd", 0.0),
        rush_td=row.get("rush_td", 0.0),
        target=row.get("target", 0.0),
        rec=row.get("rec", 0.0),
        rec_yd=row.get("rec_yd", 0.0),
        rec_td=row.get("rec_td", 0.0),
        fumble_lost=row.get("fumble_lost", 0.0),
    )
    position = row.get("position", "RB")
    return score_week(stats, scoring_rules, position=position)  # type: ignore[arg-type]


def _sum_week_fantasy_points(
    session: Session,
    season: int,
    position: str | None,
    scoring_rules: ScoringRules,
) -> dict[str, float]:
    """Fetch individual week rows and sum score_week() per player.

    Returns a dict of {gsis_id: total_fantasy_points}.
    Used when yardage bonuses (100-yd game) are configured so per-week
    thresholds are honoured. For simple linear presets this is equivalent to
    scoring the season totals directly, but we always use this path for
    correctness.
    """
    p = players_table
    w = player_week_stats_table

    week_cols = [w.c[col] for col in SCREENER_STAT_COLS]
    q = (
        sa.select(
            p.c.gsis_id,
            p.c.position,
            *week_cols,
        )
        .select_from(p.join(w, p.c.gsis_id == w.c.player_id))
        .where(w.c.season == season)
    )
    if position is not None:
        q = q.where(p.c.position == position)

    totals: dict[str, float] = {}
    for wrow in session.execute(q).mappings():
        gsis_id = wrow["gsis_id"]
        pts = _compute_fantasy_points(dict(wrow), scoring_rules)
        totals[gsis_id] = totals.get(gsis_id, 0.0) + pts

    return totals


def list_season_totals(
    session: Session,
    *,
    season: int,
    position: str | None,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
    scoring_rules: ScoringRules | None = None,
) -> tuple[list[dict], int]:
    """Return aggregated season totals and the ungated player count.

    Args:
        session: SQLAlchemy session (caller owns the lifecycle).
        season: NFL season year (e.g. 2025).
        position: Optional position filter (QB/RB/WR/TE); None = all.
        sort: Column name from _SORT_KEY_NAMES.
        descending: True = DESC, False = ASC.
        limit: Max rows to return (1–500).
        offset: Number of rows to skip.
        scoring_rules: Optional ScoringRules; defaults to standard if None.

    Returns:
        (rows, total) where total is the count before LIMIT/OFFSET.
    """
    if scoring_rules is None:
        scoring_rules = ScoringRules()

    p = players_table
    w = player_week_stats_table

    stat_aggs = [
        sa.func.coalesce(sa.func.sum(w.c[col]), 0.0).label(col) for col in SCREENER_STAT_COLS
    ]

    base_query = (
        sa.select(
            p.c.gsis_id,
            p.c.name,
            p.c.position,
            p.c.team,
            sa.func.count(w.c.week).label("games"),
            *stat_aggs,
        )
        .select_from(p.join(w, p.c.gsis_id == w.c.player_id))
        .where(w.c.season == season)
    )

    if position is not None:
        base_query = base_query.where(p.c.position == position)

    base_query = base_query.group_by(p.c.gsis_id, p.c.name, p.c.position, p.c.team)

    # Count query (same WHERE, no GROUP BY limit)
    count_subq = base_query.subquery()
    total: int = session.execute(sa.select(sa.func.count()).select_from(count_subq)).scalar_one()

    # Compute per-week fantasy points (honours per-game yardage bonuses).
    fp_by_player = _sum_week_fantasy_points(session, season, position, scoring_rules)

    # For fantasy_points sort we need all rows, attach points, sort, then slice.
    if sort == "fantasy_points":
        all_rows_query = base_query.order_by(p.c.gsis_id.asc())
        all_rows = [dict(row) for row in session.execute(all_rows_query).mappings()]
        for row in all_rows:
            row["fantasy_points"] = round(fp_by_player.get(row["gsis_id"], 0.0), 2)
        all_rows.sort(
            key=lambda r: (r["fantasy_points"], r["gsis_id"]),
            reverse=descending,
        )
        rows = all_rows[offset : offset + limit]
        return rows, total

    # Sorting: build the ORDER BY expression from the aggregated columns.
    # We never interpolate the sort string into SQL — we look it up from the
    # labelled columns in the SELECT list.
    if sort == "name":
        sort_col = p.c.name
    elif sort == "games":
        sort_col = sa.literal_column("games")
    else:
        sort_col = sa.literal_column(sort)

    order_expr = sort_col.desc() if descending else sort_col.asc()
    # Tiebreak by gsis_id for stable pagination.
    tiebreak = p.c.gsis_id.asc()

    data_query = base_query.order_by(order_expr, tiebreak).limit(limit).offset(offset)
    rows = [dict(row) for row in session.execute(data_query).mappings()]

    # Attach fantasy_points from the per-week computation.
    for row in rows:
        row["fantasy_points"] = round(fp_by_player.get(row["gsis_id"], 0.0), 2)

    return rows, total
