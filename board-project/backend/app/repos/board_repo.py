from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria

from app.models import Board, Card, List


class BoardRepository:
    def _active_board_query(self) -> Select[tuple[Board]]:
        return (
            select(Board)
            .where(Board.deleted_at.is_(None))
            .options(
                selectinload(Board.lists).selectinload(List.cards),
                with_loader_criteria(List, List.deleted_at.is_(None), include_aliases=True),
                with_loader_criteria(Card, Card.deleted_at.is_(None), include_aliases=True),
            )
        )

    async def list_boards(self, session: AsyncSession) -> list[Board]:
        result = await session.execute(
            select(Board).where(Board.deleted_at.is_(None)).order_by(Board.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_board(self, session: AsyncSession, board_id: uuid.UUID) -> Board | None:
        result = await session.execute(self._active_board_query().where(Board.id == board_id))
        return result.scalars().first()

    async def create_demo_board_if_missing(self, session: AsyncSession) -> Board:
        existing_demo = await session.execute(
            self._active_board_query().where(Board.name == "Demo Task Flow Board")
        )
        board = existing_demo.scalars().first()
        if board is not None:
            return board

        board = Board(name="Demo Task Flow Board")
        todo_list = List(name="To Do", position_rank=Decimal("1024"), board=board)
        in_progress_list = List(name="In Progress", position_rank=Decimal("2048"), board=board)
        done_list = List(name="Done", position_rank=Decimal("3072"), board=board)

        Card(
            board=board,
            list=todo_list,
            title="Design board schema",
            description="Define board/list/card schema and soft-delete columns.",
            position_rank=Decimal("1024"),
        )
        Card(
            board=board,
            list=todo_list,
            title="Set up API routes",
            description="Create /boards and /boards/{id} endpoints.",
            position_rank=Decimal("2048"),
        )
        Card(
            board=board,
            list=in_progress_list,
            title="Build frontend board view",
            description="Render columns and cards from backend API.",
            position_rank=Decimal("1024"),
        )
        Card(
            board=board,
            list=done_list,
            title="Bootstrap Docker Postgres",
            description="Run DB in container and wire backend credentials.",
            position_rank=Decimal("1024"),
        )

        session.add(board)
        await session.flush()
        refreshed = await self.get_board(session, board.id)
        if refreshed is None:
            return board
        return refreshed

    async def create_board(self, session: AsyncSession, name: str) -> Board:
        board = Board(name=name)
        List(name="To Do", position_rank=Decimal("1024"), board=board)
        List(name="In Progress", position_rank=Decimal("2048"), board=board)
        List(name="Done", position_rank=Decimal("3072"), board=board)
        session.add(board)
        await session.flush()
        refreshed = await self.get_board(session, board.id)
        if refreshed is None:
            return board
        return refreshed

    async def get_active_board_for_update(self, session: AsyncSession, board_id: uuid.UUID) -> Board | None:
        result = await session.execute(
            select(Board)
            .where(Board.id == board_id, Board.deleted_at.is_(None))
            .with_for_update()
        )
        return result.scalars().first()

    async def update_board_name(self, session: AsyncSession, board_id: uuid.UUID, name: str) -> Board | None:
        board = await self.get_active_board_for_update(session, board_id)
        if board is None:
            return None
        board.name = name
        await session.flush()
        return await self.get_board(session, board_id)

    async def soft_delete_board(self, session: AsyncSession, board_id: uuid.UUID) -> bool:
        board = await self.get_active_board_for_update(session, board_id)
        if board is None:
            return False

        deleted_at = datetime.now(timezone.utc)
        board.deleted_at = deleted_at

        await session.execute(
            update(List)
            .where(List.board_id == board_id, List.deleted_at.is_(None))
            .values(deleted_at=deleted_at)
        )
        await session.execute(
            update(Card)
            .where(Card.board_id == board_id, Card.deleted_at.is_(None))
            .values(deleted_at=deleted_at)
        )
        return True
