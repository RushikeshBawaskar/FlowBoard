from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repos.card_repo import CardRepository
from app.schemas.board_schema import CardCreateRequest, CardMoveRead, CardMoveRequest, CardRead, CardUpdateRequest


class CardService:
    def __init__(self, card_repository: CardRepository) -> None:
        self.card_repository = card_repository
        settings = get_settings()
        self.base_gap = Decimal(str(settings.BASE_GAP))
        self.min_gap = Decimal(str(settings.MIN_GAP))

    @staticmethod
    def _compute_rank(
        base_gap: Decimal,
        prev_rank: Decimal | None,
        next_rank: Decimal | None,
    ) -> Decimal:
        if prev_rank is None and next_rank is None:
            return base_gap
        if prev_rank is None and next_rank is not None:
            return next_rank - base_gap
        if prev_rank is not None and next_rank is None:
            return prev_rank + base_gap
        if prev_rank is None or next_rank is None:
            return base_gap
        return (prev_rank + next_rank) / Decimal("2")

    def _needs_rebalance(self, prev_rank: Decimal | None, next_rank: Decimal | None) -> bool:
        if prev_rank is None or next_rank is None:
            return False
        return (next_rank - prev_rank) <= self.min_gap

    async def move_card(
        self,
        session: AsyncSession,
        card_id: uuid.UUID,
        payload: CardMoveRequest,
    ) -> CardMoveRead:
        async with session.begin():
            moving_card = await self.card_repository.get_card_for_update(session, card_id)
            if moving_card is None:
                raise LookupError("Card not found.")

            target_list = await self.card_repository.get_list_for_update(session, payload.target_list_id)
            if target_list is None:
                raise LookupError("Target list not found.")

            if moving_card.board_id != target_list.board_id:
                raise ValueError("Cannot move card across different boards.")

            await self.card_repository.lock_lists(
                session,
                list(set([moving_card.list_id, target_list.id])),
            )

            prev_card = None
            if payload.prev_card_id is not None:
                prev_card = await self.card_repository.get_neighbor_card_for_update(
                    session,
                    payload.prev_card_id,
                )
                if prev_card is None or prev_card.list_id != target_list.id:
                    raise ValueError("Invalid prev_card_id for target list.")
                if prev_card.id == moving_card.id:
                    raise ValueError("prev_card_id cannot be the moving card.")

            next_card = None
            if payload.next_card_id is not None:
                next_card = await self.card_repository.get_neighbor_card_for_update(
                    session,
                    payload.next_card_id,
                )
                if next_card is None or next_card.list_id != target_list.id:
                    raise ValueError("Invalid next_card_id for target list.")
                if next_card.id == moving_card.id:
                    raise ValueError("next_card_id cannot be the moving card.")

            if prev_card is not None and next_card is not None:
                if prev_card.position_rank >= next_card.position_rank:
                    raise ValueError("prev_card_id must be before next_card_id.")

            prev_rank = prev_card.position_rank if prev_card is not None else None
            next_rank = next_card.position_rank if next_card is not None else None

            if self._needs_rebalance(prev_rank, next_rank):
                await self.card_repository.rebalance_list(
                    session,
                    list_id=target_list.id,
                    base_gap=self.base_gap,
                    exclude_card_id=moving_card.id,
                )
                if prev_card is not None:
                    prev_card = await self.card_repository.get_neighbor_card_for_update(session, prev_card.id)
                if next_card is not None:
                    next_card = await self.card_repository.get_neighbor_card_for_update(session, next_card.id)
                prev_rank = prev_card.position_rank if prev_card is not None else None
                next_rank = next_card.position_rank if next_card is not None else None

            moving_card.list_id = target_list.id
            moving_card.position_rank = self._compute_rank(self.base_gap, prev_rank, next_rank)

        return CardMoveRead(
            card_id=moving_card.id,
            board_id=moving_card.board_id,
            list_id=moving_card.list_id,
        )

    async def create_card(self, session: AsyncSession, payload: CardCreateRequest) -> CardRead:
        title = payload.title.strip()
        if title == "":
            raise ValueError("Card title is required.")

        async with session.begin():
            target_list = await self.card_repository.get_list_for_update(session, payload.list_id)
            if target_list is None:
                raise LookupError("List not found.")

            last_rank = await self.card_repository.get_last_rank(session, target_list.id)
            new_rank = self._compute_rank(base_gap=self.base_gap, prev_rank=last_rank, next_rank=None)
            card = await self.card_repository.create_card(
                session,
                board_id=target_list.board_id,
                list_id=target_list.id,
                title=title,
                description=payload.description,
                position_rank=new_rank,
            )

        return CardRead.model_validate(card)

    async def update_card(
        self,
        session: AsyncSession,
        card_id: uuid.UUID,
        payload: CardUpdateRequest,
    ) -> CardRead:
        if payload.title is None and payload.description is None:
            raise ValueError("At least one field is required.")

        async with session.begin():
            card = await self.card_repository.get_card_for_update(session, card_id)
            if card is None:
                raise LookupError("Card not found.")

            if payload.title is not None:
                next_title = payload.title.strip()
                if next_title == "":
                    raise ValueError("Card title cannot be empty.")
                card.title = next_title
            if payload.description is not None:
                card.description = payload.description

        refreshed = await self.card_repository.get_card(session, card_id)
        if refreshed is None:
            raise LookupError("Card not found.")
        return CardRead.model_validate(refreshed)


def get_card_service() -> CardService:
    return CardService(card_repository=CardRepository())
