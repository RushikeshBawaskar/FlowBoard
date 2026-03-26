import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.db.session import get_db_session
from app.schemas.auth_schema import UserRead
from app.schemas.board_schema import (
    CardCreateRequest,
    CardMoveRead,
    CardMoveRequest,
    CardRead,
    CardUpdateRequest,
)
from app.services.card_service import CardService, get_card_service

router = APIRouter(prefix="/cards")


@router.post("", response_model=CardRead, status_code=status.HTTP_201_CREATED, summary="Create card")
async def create_card(
    payload: CardCreateRequest,
    db_session: AsyncSession = Depends(get_db_session),
    card_service: CardService = Depends(get_card_service),
    _current_user: UserRead = Depends(get_current_user),
) -> CardRead:
    try:
        return await card_service.create_card(db_session, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch("/{card_id}", response_model=CardRead, summary="Edit card")
async def update_card(
    card_id: uuid.UUID,
    payload: CardUpdateRequest,
    db_session: AsyncSession = Depends(get_db_session),
    card_service: CardService = Depends(get_card_service),
    _current_user: UserRead = Depends(get_current_user),
) -> CardRead:
    try:
        return await card_service.update_card(db_session, card_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch("/{card_id}/move", response_model=CardMoveRead, summary="Move card within/between lists")
async def move_card(
    card_id: uuid.UUID,
    payload: CardMoveRequest,
    db_session: AsyncSession = Depends(get_db_session),
    card_service: CardService = Depends(get_card_service),
    _current_user: UserRead = Depends(get_current_user),
) -> CardMoveRead:
    try:
        return await card_service.move_card(db_session, card_id, payload)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
