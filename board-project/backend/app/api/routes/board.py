import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.db.session import get_db_session
from app.schemas.auth_schema import UserRead
from app.schemas.board_schema import (
    BoardCreateRequest,
    BoardDetailRead,
    BoardSummaryRead,
    BoardUpdateRequest,
)
from app.services.board_service import BoardService, get_board_service

router = APIRouter(prefix="/boards")


@router.get("", response_model=list[BoardSummaryRead], summary="List active boards")
async def list_boards(
    db_session: AsyncSession = Depends(get_db_session),
    board_service: BoardService = Depends(get_board_service),
    _current_user: UserRead = Depends(get_current_user),
) -> list[BoardSummaryRead]:
    return await board_service.list_boards(db_session)


@router.get("/{board_id}", response_model=BoardDetailRead, summary="Get board with lists and cards")
async def get_board(
    board_id: uuid.UUID,
    db_session: AsyncSession = Depends(get_db_session),
    board_service: BoardService = Depends(get_board_service),
    _current_user: UserRead = Depends(get_current_user),
) -> BoardDetailRead:
    board = await board_service.get_board(db_session, board_id)
    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Board not found.",
        )
    return board


@router.post("", response_model=BoardDetailRead, status_code=status.HTTP_201_CREATED, summary="Create board")
async def create_board(
    payload: BoardCreateRequest,
    db_session: AsyncSession = Depends(get_db_session),
    board_service: BoardService = Depends(get_board_service),
    _current_user: UserRead = Depends(get_current_user),
) -> BoardDetailRead:
    if payload.name.strip() == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Board name is required.")
    return await board_service.create_board(db_session, payload)


@router.post(
    "/demo-seed",
    response_model=BoardDetailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create demo board data if missing",
)
async def seed_demo_board(
    db_session: AsyncSession = Depends(get_db_session),
    board_service: BoardService = Depends(get_board_service),
    _current_user: UserRead = Depends(get_current_user),
) -> BoardDetailRead:
    return await board_service.seed_demo_board(db_session)


@router.patch("/{board_id}", response_model=BoardDetailRead, summary="Update board")
async def update_board(
    board_id: uuid.UUID,
    payload: BoardUpdateRequest,
    db_session: AsyncSession = Depends(get_db_session),
    board_service: BoardService = Depends(get_board_service),
    _current_user: UserRead = Depends(get_current_user),
) -> BoardDetailRead:
    if payload.name.strip() == "":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Board name is required.")

    updated = await board_service.update_board(db_session, board_id=board_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
    return updated


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft delete board")
async def delete_board(
    board_id: uuid.UUID,
    db_session: AsyncSession = Depends(get_db_session),
    board_service: BoardService = Depends(get_board_service),
    _current_user: UserRead = Depends(get_current_user),
) -> None:
    was_deleted = await board_service.delete_board(db_session, board_id)
    if not was_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found.")
