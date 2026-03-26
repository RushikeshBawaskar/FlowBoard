from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        result = await session.execute(
            select(User).where(User.email == email.lower().strip(), User.deleted_at.is_(None))
        )
        return result.scalars().first()

    async def get_by_id(self, session: AsyncSession, user_id: uuid.UUID) -> User | None:
        result = await session.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
        return result.scalars().first()

    async def create(self, session: AsyncSession, *, email: str, password_hash: str, password_salt: str) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            password_salt=password_salt,
        )
        session.add(user)
        await session.flush()
        return user
