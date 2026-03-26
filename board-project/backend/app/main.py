from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import initialize_database

logger = logging.getLogger(__name__)


def _parse_allowed_origins(raw_origins: str) -> list[str]:
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_application: FastAPI):
    await initialize_database()
    yield


def create_application() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    application = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_allowed_origins(settings.FRONTEND_ORIGINS),
        allow_origin_regex=settings.FRONTEND_ORIGIN_REGEX,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = exc.errors()
        messages: list[str] = []
        for item in details:
            loc = item.get("loc", [])
            msg = item.get("msg", "Invalid request.")
            if isinstance(loc, (list, tuple)) and len(loc) > 0:
                location = ".".join([str(part) for part in loc if part != "body"])
                if location != "":
                    messages.append(f"{location}: {msg}")
                    continue
            messages.append(str(msg))

        detail = "; ".join(messages) if messages else "Invalid request payload."
        return JSONResponse(status_code=422, content={"detail": detail})

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    return application


app = create_application()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_RELOAD,
    )
