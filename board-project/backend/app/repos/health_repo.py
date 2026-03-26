from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class HealthRepository:
    async def check_database_connection(self, session: AsyncSession) -> bool:
        result = await session.execute(text("SELECT 1"))
        return result.scalar_one() == 1
