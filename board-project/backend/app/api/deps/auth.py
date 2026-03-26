from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_auth_db_session
from app.schemas.auth_schema import UserRead
from app.services.auth_service import AuthService, get_auth_service

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_session: AsyncSession = Depends(get_auth_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserRead:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token.",
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload.sub)
    except (ValueError, TypeError):
        raise unauthorized

    user = await auth_service.get_user_by_id(auth_session, user_id)
    if user is None:
        raise unauthorized
    return user
