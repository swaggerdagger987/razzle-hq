import sqlalchemy as sa
from sqlalchemy.orm import Session

from razzle_api.ingest.nflverse import players_table


def list_players(session: Session, position: str | None = None, limit: int = 100) -> list[dict]:
    query = sa.select(
        players_table.c.gsis_id,
        players_table.c.name,
        players_table.c.position,
        players_table.c.team,
    )
    if position is not None:
        query = query.where(players_table.c.position == position)
    query = query.order_by(players_table.c.name).limit(limit)
    return [dict(row) for row in session.execute(query).mappings()]
