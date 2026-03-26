from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.repos.user_repo import UserRepository
from app.schemas.auth_schema import AuthTokenRead, LoginRequest, RegisterRequest, UserRead


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def register(self, session: AsyncSession, payload: RegisterRequest) -> AuthTokenRead:
        email = payload.email.lower().strip()
        existing = await self.user_repository.get_by_email(session, email)
        if existing is not None:
            raise ValueError("User already exists.")

        password_hash, password_salt = hash_password(payload.password)
        user = await self.user_repository.create(
            session,
            email=email,
            password_hash=password_hash,
            password_salt=password_salt,
        )
        await session.commit()
        token = create_access_token(user_id=str(user.id), email=user.email)
        return AuthTokenRead(access_token=token, user=UserRead.model_validate(user))

    async def login(self, session: AsyncSession, payload: LoginRequest) -> AuthTokenRead:
        email = payload.email.lower().strip()
        user = await self.user_repository.get_by_email(session, email)
        if user is None:
            raise LookupError("Invalid email or password.")

        is_valid = verify_password(payload.password, user.password_hash, user.password_salt)
        if not is_valid:
            raise LookupError("Invalid email or password.")

        token = create_access_token(user_id=str(user.id), email=user.email)
        return AuthTokenRead(access_token=token, user=UserRead.model_validate(user))

    async def get_user_by_id(self, session: AsyncSession, user_id: uuid.UUID) -> UserRead | None:
        user = await self.user_repository.get_by_id(session, user_id)
        if user is None:
            return None
        return UserRead.model_validate(user)


def get_auth_service() -> AuthService:
    return AuthService(user_repository=UserRepository())
