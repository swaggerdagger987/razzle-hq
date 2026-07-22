from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from razzle_api.api.schemas.context import (
    ConnectRequest,
    ConnectResponse,
    ContextRevisionResponse,
    RefreshRequest,
)
from razzle_api.core.db import get_session
from razzle_api.services.context_service import (
    ContextForbiddenError,
    ContextNotFoundError,
    ContextUpstreamError,
    connect_username,
    get_revision,
    refresh_league,
)

router = APIRouter(prefix="/api/context", tags=["context"])


@router.post("/connect", response_model=ConnectResponse)
def connect(
    body: ConnectRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ConnectResponse:
    try:
        payload = connect_username(session, body.username)
    except ContextNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ContextUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ConnectResponse.model_validate(payload)


@router.post("/leagues/{league_id}/refresh", response_model=ContextRevisionResponse)
def refresh(
    league_id: str,
    body: RefreshRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ContextRevisionResponse:
    try:
        payload = refresh_league(session, league_id, username=body.username)
    except ContextNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ContextForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ContextUpstreamError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ContextRevisionResponse.model_validate(payload)


@router.get("/revision/{revision_id}", response_model=ContextRevisionResponse)
def revision(
    revision_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> ContextRevisionResponse:
    payload = get_revision(session, revision_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"revision not found: {revision_id}",
        )
    return ContextRevisionResponse.model_validate(payload)
