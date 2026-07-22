from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/context", tags=["context"])


@router.post("/connect")
async def connect(_body: dict[str, Any]) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="not implemented",
    )


@router.post("/leagues/{league_id}/refresh")
async def refresh_league(league_id: str, _body: dict[str, Any]) -> None:
    del league_id
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="not implemented",
    )


@router.get("/revision/{revision_id}")
async def get_revision(revision_id: str) -> None:
    del revision_id
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="not implemented",
    )
