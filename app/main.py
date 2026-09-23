from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.exceptions import EngineError
from app.core.logging_config import configure_logging
import app.db.models  # noqa: F401  (registers mappers before create_all)
from app.db.base import Base
from app.db.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    Base.metadata.create_all(bind=engine)
    logger.info("Qualification & Lead Scoring Engine %s started", __version__)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Multi-tenant engine that turns a conversation transcript plus a six-part "
            "qualification template into a qualification decision, lead score and temperature."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(EngineError)
    async def handle_engine_error(_: Request, exc: EngineError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"code": exc.code, "message": exc.message}
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
