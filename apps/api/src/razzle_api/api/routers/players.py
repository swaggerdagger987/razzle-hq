from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from razzle_api.api.schemas.players import PlayerOut, PlayersResponse
from razzle_api.core.db import get_session
from razzle_api.services.players_service import list_players

router = APIRouter(prefix="/api", tags=["players"])


@router.get("/players", response_model=PlayersResponse)
async def get_players(
    session: Annotated[Session, Depends(get_session)],
    position: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> PlayersResponse:
    rows = list_players(session, position=position, limit=limit)
    return PlayersResponse(players=[PlayerOut(**row) for row in rows])
