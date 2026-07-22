"""Screener service: aggregate season totals from player_week_stats."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from razzle_api.domain.scoring.config import ScoringRules
from razzle_api.domain.scoring.engine import PlayerWeekStats, score_week
from razzle_api.ingest.nflverse import STAT_COLUMNS, player_week_stats_table, players_table

# Single registry: every stored week-stat field participates in scoring.
SCREENER_STAT_COLS = STAT_COLUMNS

# Slim columns returned on the wire (plus fantasy_points).
RESPONSE_STAT_COLS = [
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

_SORT_KEY_NAMES = {"name", "games", "fantasy_points", *RESPONSE_STAT_COLS}

MAX_FANTASY_POINT_SORT_PLAYERS = 5000


class FantasySortTooLargeError(Exception):
    """Raised when fantasy_points sort would score more players than allowed."""

    def __init__(self, total: int, limit: int = MAX_FANTASY_POINT_SORT_PLAYERS) -> None:
        self.total = total
        self.limit = limit
        super().__init__(
            f"fantasy_points sort supports at most {limit} players; got {total}",
        )


def _week_stats_to_player_week(row: dict) -> PlayerWeekStats:
    return PlayerWeekStats(**{col: float(row.get(col) or 0.0) for col in SCREENER_STAT_COLS})


def _score_week_row(row: dict, scoring_rules: ScoringRules) -> float:
    stats = _week_stats_to_player_week(row)
    position = row.get("position") or "RB"
    return score_week(stats, scoring_rules, position=position)  # type: ignore[arg-type]


def _sum_week_fantasy_points(
    session: Session,
    season: int,
    position: str | None,
    scoring_rules: ScoringRules,
    player_ids: set[str] | None = None,
) -> dict[str, float]:
    """Sum score_week() per player across weekly rows.

    When player_ids is provided, only those players' weekly rows are fetched
    and scored (used for non-fantasy sorts so only the page is scored).
    """
    if player_ids is not None and len(player_ids) == 0:
        return {}

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
    if player_ids is not None:
        q = q.where(p.c.gsis_id.in_(player_ids))

    totals: dict[str, float] = {}
    for wrow in session.execute(q).mappings():
        gsis_id = wrow["gsis_id"]
        pts = _score_week_row(dict(wrow), scoring_rules)
        totals[gsis_id] = totals.get(gsis_id, 0.0) + pts

    return totals


def _player_count_query(season: int, position: str | None):
    p = players_table
    w = player_week_stats_table
    q = (
        sa.select(p.c.gsis_id)
        .select_from(p.join(w, p.c.gsis_id == w.c.player_id))
        .where(w.c.season == season)
        .group_by(p.c.gsis_id)
    )
    if position is not None:
        q = q.where(p.c.position == position)
    return q


def _aggregate_base_query(season: int, position: str | None):
    """Season aggregates for slim response columns only."""
    p = players_table
    w = player_week_stats_table

    stat_aggs = [
        sa.func.coalesce(sa.func.sum(w.c[col]), 0.0).label(col) for col in RESPONSE_STAT_COLS
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
        .group_by(p.c.gsis_id, p.c.name, p.c.position, p.c.team)
    )
    if position is not None:
        base_query = base_query.where(p.c.position == position)
    return base_query


def _fetch_aggregate_rows_for_ids(
    session: Session,
    season: int,
    position: str | None,
    player_ids: list[str],
) -> list[dict]:
    if not player_ids:
        return []

    base_query = _aggregate_base_query(season, position).where(
        players_table.c.gsis_id.in_(player_ids)
    )
    by_id = {row["gsis_id"]: dict(row) for row in session.execute(base_query).mappings()}
    # Preserve caller order (ranked page order).
    return [by_id[gid] for gid in player_ids if gid in by_id]


def _rank_fantasy_ids(
    fp_by_player: dict[str, float],
    *,
    descending: bool,
) -> list[str]:
    """Rank player ids by fantasy points; ties always break gsis_id ASC."""
    items = list(fp_by_player.items())
    # Two-pass stable sort: gsis_id ASC first, then FP with requested direction.
    items.sort(key=lambda item: item[0])
    items.sort(key=lambda item: item[1], reverse=descending)
    return [gsis_id for gsis_id, _ in items]


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

    Fantasy points are always the sum of score_week() over actual week rows
    (never score_week on season aggregates — yardage bonuses are per-week).
    """
    if scoring_rules is None:
        scoring_rules = ScoringRules()

    if sort not in _SORT_KEY_NAMES:
        raise ValueError(f"unsupported sort key: {sort}")

    count_subq = _player_count_query(season, position).subquery()
    total: int = session.execute(sa.select(sa.func.count()).select_from(count_subq)).scalar_one()

    if sort == "fantasy_points":
        if total > MAX_FANTASY_POINT_SORT_PLAYERS:
            raise FantasySortTooLargeError(total)

        # Score all candidates, rank globally, then materialize only the page.
        fp_by_player = _sum_week_fantasy_points(session, season, position, scoring_rules)
        # Players with stats but zero points (no weekly rows scored) still need a slot.
        if len(fp_by_player) < total:
            id_rows = session.execute(_player_count_query(season, position)).all()
            for (gsis_id,) in id_rows:
                fp_by_player.setdefault(gsis_id, 0.0)

        ranked_ids = _rank_fantasy_ids(fp_by_player, descending=descending)
        page_ids = ranked_ids[offset : offset + limit]
        rows = _fetch_aggregate_rows_for_ids(session, season, position, page_ids)
        for row in rows:
            row["fantasy_points"] = round(fp_by_player.get(row["gsis_id"], 0.0), 2)
        return rows, total

    # Non-fantasy sort: SQL orders/limits first, then score only page player ids.
    p = players_table
    base_query = _aggregate_base_query(season, position)

    if sort == "name":
        sort_col = p.c.name
    elif sort == "games":
        sort_col = sa.literal_column("games")
    else:
        sort_col = sa.literal_column(sort)

    order_expr = sort_col.desc() if descending else sort_col.asc()
    tiebreak = p.c.gsis_id.asc()
    data_query = base_query.order_by(order_expr, tiebreak).limit(limit).offset(offset)
    rows = [dict(row) for row in session.execute(data_query).mappings()]

    page_ids = {row["gsis_id"] for row in rows}
    fp_by_player = _sum_week_fantasy_points(
        session,
        season,
        position,
        scoring_rules,
        player_ids=page_ids,
    )
    for row in rows:
        row["fantasy_points"] = round(fp_by_player.get(row["gsis_id"], 0.0), 2)

    return rows, total
