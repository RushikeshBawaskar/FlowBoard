from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, List


class CardRepository:
    async def get_card_for_update(self, session: AsyncSession, card_id: uuid.UUID) -> Card | None:
        result = await session.execute(
            select(Card)
            .where(Card.id == card_id, Card.deleted_at.is_(None))
            .with_for_update()
        )
        return result.scalars().first()

    async def get_list_for_update(self, session: AsyncSession, list_id: uuid.UUID) -> List | None:
        result = await session.execute(
            select(List)
            .where(List.id == list_id, List.deleted_at.is_(None))
            .with_for_update()
        )
        return result.scalars().first()

    async def get_list(self, session: AsyncSession, list_id: uuid.UUID) -> List | None:
        result = await session.execute(select(List).where(List.id == list_id, List.deleted_at.is_(None)))
        return result.scalars().first()

    async def lock_lists(self, session: AsyncSession, list_ids: list[uuid.UUID]) -> None:
        if not list_ids:
            return
        await session.execute(
            select(List)
            .where(List.id.in_(list_ids), List.deleted_at.is_(None))
            .order_by(List.id.asc())
            .with_for_update()
        )

    async def get_neighbor_card_for_update(
        self,
        session: AsyncSession,
        card_id: uuid.UUID,
    ) -> Card | None:
        result = await session.execute(
            select(Card)
            .where(Card.id == card_id, Card.deleted_at.is_(None))
            .with_for_update()
        )
        return result.scalars().first()

    async def get_card(self, session: AsyncSession, card_id: uuid.UUID) -> Card | None:
        result = await session.execute(select(Card).where(Card.id == card_id, Card.deleted_at.is_(None)))
        return result.scalars().first()

    async def get_last_rank(self, session: AsyncSession, list_id: uuid.UUID) -> Decimal | None:
        result = await session.execute(
            select(func.max(Card.position_rank)).where(Card.list_id == list_id, Card.deleted_at.is_(None))
        )
        rank = result.scalar_one_or_none()
        if rank is None:
            return None
        return Decimal(rank)

    async def create_card(
        self,
        session: AsyncSession,
        *,
        board_id: uuid.UUID,
        list_id: uuid.UUID,
        title: str,
        description: str | None,
        position_rank: Decimal,
    ) -> Card:
        card = Card(
            board_id=board_id,
            list_id=list_id,
            title=title,
            description=description,
            position_rank=position_rank,
        )
        session.add(card)
        await session.flush()
        return card

    async def rebalance_list(
        self,
        session: AsyncSession,
        list_id: uuid.UUID,
        base_gap: Decimal,
        exclude_card_id: uuid.UUID | None = None,
    ) -> None:
        query = (
            select(Card)
            .where(Card.list_id == list_id, Card.deleted_at.is_(None))
            .order_by(Card.position_rank.asc(), Card.id.asc())
            .with_for_update()
        )
        if exclude_card_id is not None:
            query = query.where(Card.id != exclude_card_id)

        result = await session.execute(query)
        cards = list(result.scalars().all())
        for index, card in enumerate(cards, start=1):
            card.position_rank = base_gap * Decimal(index)
