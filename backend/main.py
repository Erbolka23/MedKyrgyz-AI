"""
MedKyrgyz AI — backend entry point.

Run from the `backend/` directory:

    uvicorn main:app --reload            # development
    python main.py                       # same, via the __main__ block
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.database.session import init_db
from app.services.llm_service import get_llm_provider

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger("medkyrgyz")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    provider = get_llm_provider()
    logger.info("%s v%s started (env=%s, llm=%s)", settings.app_name, __version__, settings.app_env, provider.name)
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    """Application factory — also used by the test-suite."""
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Кыргыз тилиндеги интеллектуалдык медициналык жардамчы. "
            "AI medical information assistant for Kyrgyz and Russian speakers. "
            "It does not diagnose and does not prescribe medication."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=settings.debug)
