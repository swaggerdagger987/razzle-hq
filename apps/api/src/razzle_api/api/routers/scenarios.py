from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.post("")
async def create_scenario(_body: dict[str, Any]) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="not implemented",
    )
