"""Screener service: aggregate season totals from player_week_stats."""

import sqlalchemy as sa
from sqlalchemy.orm import Session

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
_SORT_KEY_NAMES = {"name", "games", *SCREENER_STAT_COLS}


def list_season_totals(
    session: Session,
    *,
    season: int,
    position: str | None,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
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

    Returns:
        (rows, total) where total is the count before LIMIT/OFFSET.
    """
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
    return rows, total
