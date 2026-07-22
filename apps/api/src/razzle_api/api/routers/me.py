from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
async def get_me() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="not implemented",
    )
