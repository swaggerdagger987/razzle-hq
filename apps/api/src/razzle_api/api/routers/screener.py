from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from razzle_api.api.schemas.screener import ScreenerResponse, ScreenerRow
from razzle_api.core.db import get_session
from razzle_api.services.screener_service import list_season_totals

router = APIRouter(prefix="/api", tags=["screener"])

# Valid sort values: "name", "games", plus the 13 stat aggregation columns.
_SORT_LITERAL = Literal[
    "name",
    "games",
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

_POSITION_LITERAL = Literal["QB", "RB", "WR", "TE"]


@router.get("/screener", response_model=ScreenerResponse)
async def get_screener(
    session: Annotated[Session, Depends(get_session)],
    season: Annotated[int, Query(ge=2000, le=2100)] = 2025,
    position: Annotated[_POSITION_LITERAL | None, Query()] = None,
    sort: Annotated[_SORT_LITERAL, Query()] = "name",
    dir: Annotated[Literal["asc", "desc"], Query()] = "asc",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScreenerResponse:
    # Default sort direction: asc for name, desc for numeric columns.
    descending = dir == "desc"

    rows, total = list_season_totals(
        session,
        season=season,
        position=position,
        sort=sort,
        descending=descending,
        limit=limit,
        offset=offset,
    )
    return ScreenerResponse(
        season=season,
        total=total,
        rows=[ScreenerRow(**row) for row in rows],
    )
