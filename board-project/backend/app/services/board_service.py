from __future__ import annotations

import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.board_repo import BoardRepository
from app.schemas.board_schema import BoardCreateRequest, BoardDetailRead, BoardSummaryRead, BoardUpdateRequest


class BoardService:
    def __init__(self, board_repository: BoardRepository) -> None:
        self.board_repository = board_repository

    async def list_boards(self, session: AsyncSession) -> list[BoardSummaryRead]:
        boards = await self.board_repository.list_boards(session)
        return [BoardSummaryRead.model_validate(board) for board in boards]

    async def get_board(self, session: AsyncSession, board_id: uuid.UUID) -> BoardDetailRead | None:
        board = await self.board_repository.get_board(session, board_id)
        if board is None:
            return None
        return BoardDetailRead.model_validate(board)

    async def seed_demo_board(self, session: AsyncSession) -> BoardDetailRead:
        board = await self.board_repository.create_demo_board_if_missing(session)
        await session.commit()
        return BoardDetailRead.model_validate(board)

    async def create_board(
        self,
        session: AsyncSession,
        payload: BoardCreateRequest,
    ) -> BoardDetailRead:
        board = await self.board_repository.create_board(session, name=payload.name.strip())
        await session.commit()
        return BoardDetailRead.model_validate(board)

    async def update_board(
        self,
        session: AsyncSession,
        board_id: uuid.UUID,
        payload: BoardUpdateRequest,
    ) -> BoardDetailRead | None:
        board = await self.board_repository.update_board_name(
            session,
            board_id=board_id,
            name=payload.name.strip(),
        )
        if board is None:
            await session.rollback()
            return None
        await session.commit()
        return BoardDetailRead.model_validate(board)

    async def delete_board(self, session: AsyncSession, board_id: uuid.UUID) -> bool:
        was_deleted = await self.board_repository.soft_delete_board(session, board_id)
        if not was_deleted:
            await session.rollback()
            return False
        await session.commit()
        return True


def get_board_service() -> BoardService:
    return BoardService(board_repository=BoardRepository())
