from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str
    APP_ENV: str
    APP_HOST: str
    APP_PORT: int
    APP_RELOAD: bool
    API_V1_PREFIX: str
    LOG_LEVEL: str
    FRONTEND_ORIGINS: str
    FRONTEND_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"

    DATABASE_URL: str
    SQL_ECHO: bool

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    BASE_GAP: Decimal = Field(gt=0)
    MIN_GAP: Decimal = Field(gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
