from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.auth_schema import AuthTokenRead, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService, get_auth_service

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=AuthTokenRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db_session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenRead:
    try:
        return await auth_service.register(db_session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/login", response_model=AuthTokenRead)
async def login(
    payload: LoginRequest,
    db_session: AsyncSession = Depends(get_db_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenRead:
    try:
        return await auth_service.login(db_session, payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
