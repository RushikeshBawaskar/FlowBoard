import logging

from app.db.base import Base
from app.db.session import engine
from app.models import Board, Card, List, User

logger = logging.getLogger(__name__)


async def initialize_database() -> None:
    _ = (Board, List, Card, User)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    logger.info("Database schema ensured.")
