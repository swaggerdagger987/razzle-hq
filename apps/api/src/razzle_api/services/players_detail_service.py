"""Player detail service: join players + player_week_stats, group by season."""

import sqlalchemy as sa
from sqlalchemy.orm import Session

from razzle_api.ingest.nflverse import STAT_COLUMNS, player_week_stats_table, players_table


def get_player_detail(session: Session, gsis_id: str) -> dict | None:
    """Return player identity + per-week stats grouped by season.

    Returns None if the gsis_id is not found in the players table.
    """
    p = players_table
    w = player_week_stats_table

    # Resolve identity first so we can return None on miss.
    identity = (
        session.execute(
            sa.select(p.c.gsis_id, p.c.name, p.c.position, p.c.team).where(p.c.gsis_id == gsis_id)
        )
        .mappings()
        .first()
    )

    if identity is None:
        return None

    # Fetch all weekly rows ordered by season, week.
    stat_cols = [w.c[col] for col in STAT_COLUMNS]
    rows = (
        session.execute(
            sa.select(w.c.season, w.c.week, *stat_cols)
            .where(w.c.player_id == gsis_id)
            .order_by(w.c.season.asc(), w.c.week.asc())
        )
        .mappings()
        .all()
    )

    # Group into seasons.
    seasons_map: dict[int, list[dict]] = {}
    for row in rows:
        season = row["season"]
        if season not in seasons_map:
            seasons_map[season] = []
        week_dict = {"week": row["week"]}
        for col in STAT_COLUMNS:
            week_dict[col] = row[col]
        seasons_map[season].append(week_dict)

    seasons = [
        {"season": s, "week_stats": wstats}
        for s, wstats in sorted(seasons_map.items(), reverse=True)
    ]

    return {
        "gsis_id": identity["gsis_id"],
        "name": identity["name"],
        "position": identity["position"],
        "team": identity["team"],
        "seasons": seasons,
    }


def list_adjacent_players(
    session: Session,
    *,
    season: int,
    position: str | None,
    gsis_id: str,
) -> tuple[str | None, str | None]:
    """Return (prev_gsis_id, next_gsis_id) adjacent to gsis_id sorted alphabetically by name.

    Scoped to players who have stats in the given season (and optionally same position).
    Falls back to all positions if no filter given.
    """
    p = players_table
    w = player_week_stats_table

    base = (
        sa.select(p.c.gsis_id, p.c.name)
        .select_from(p.join(w, p.c.gsis_id == w.c.player_id))
        .where(w.c.season == season)
        .group_by(p.c.gsis_id, p.c.name)
        .order_by(p.c.name.asc(), p.c.gsis_id.asc())
    )
    if position is not None:
        base = base.where(p.c.position == position)

    ordered = [(r["gsis_id"], r["name"]) for r in session.execute(base).mappings()]

    idx_map = {gid: i for i, (gid, _) in enumerate(ordered)}
    idx = idx_map.get(gsis_id)

    if idx is None:
        return None, None

    prev_id = ordered[idx - 1][0] if idx > 0 else None
    next_id = ordered[idx + 1][0] if idx < len(ordered) - 1 else None
    return prev_id, next_id
