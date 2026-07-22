from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from razzle_api.api.schemas.players_detail import (
    AdjacentPlayers,
    PlayerDetail,
    PlayerSeason,
    WeekStats,
)
from razzle_api.core.db import get_session
from razzle_api.services.players_detail_service import get_player_detail, list_adjacent_players

router = APIRouter(prefix="/api", tags=["players_detail"])

_POSITION_LITERAL = Literal["QB", "RB", "WR", "TE"]


@router.get("/players/{gsis_id}", response_model=PlayerDetail)
async def get_player(
    gsis_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> PlayerDetail:
    detail = get_player_detail(session, gsis_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="player not found")

    seasons = [
        PlayerSeason(
            season=s["season"],
            week_stats=[WeekStats(**w) for w in s["week_stats"]],
        )
        for s in detail["seasons"]
    ]
    return PlayerDetail(
        gsis_id=detail["gsis_id"],
        name=detail["name"],
        position=detail["position"],
        team=detail["team"],
        seasons=seasons,
    )


@router.get("/players/{gsis_id}/adjacent", response_model=AdjacentPlayers)
async def get_adjacent_players(
    gsis_id: str,
    session: Annotated[Session, Depends(get_session)],
    season: Annotated[int, Query(ge=2000, le=2100)] = 2025,
    position: Annotated[_POSITION_LITERAL | None, Query()] = None,
) -> AdjacentPlayers:
    prev_id, next_id = list_adjacent_players(
        session,
        season=season,
        position=position,
        gsis_id=gsis_id,
    )
    return AdjacentPlayers(prev_gsis_id=prev_id, next_gsis_id=next_id)
