import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repos.health_repo import HealthRepository

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, health_repository: HealthRepository) -> None:
        self.health_repository = health_repository

    async def get_health_status(self, session: AsyncSession) -> tuple[dict[str, str], bool]:
        try:
            is_database_ready = await self.health_repository.check_database_connection(session)
        except SQLAlchemyError as exc:
            logger.exception("Database health check failed due to SQLAlchemy error: %s", exc)
            return (
                {
                    "service": "ok",
                    "database": "not_connected",
                    "reason": "database_error",
                },
                False,
            )
        except Exception as exc:
            logger.exception("Database health check failed with unexpected error: %s", exc)
            return (
                {
                    "service": "ok",
                    "database": "not_connected",
                    "reason": "unexpected_error",
                },
                False,
            )

        database_status = "connected" if is_database_ready else "not_connected"
        return (
            {
                "service": "ok",
                "database": database_status,
            },
            is_database_ready,
        )


def get_health_service() -> HealthService:
    return HealthService(health_repository=HealthRepository())
