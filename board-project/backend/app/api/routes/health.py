from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.health_service import HealthService, get_health_service

router = APIRouter()


@router.get("/health", summary="Service and database health check")
async def health_check(
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
    health_service: HealthService = Depends(get_health_service),
) -> dict[str, str]:
    payload, is_healthy = await health_service.get_health_status(db_session)
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
