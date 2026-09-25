"""
Engine and session management.

The engine is created lazily so tests can point DATABASE_URL at a temporary
database before the first connection is made.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.base import Base

logger = get_logger(__name__)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    connect_args: dict[str, object] = {}

    if settings.is_sqlite:
        # FastAPI may use the session from a different thread than the one that created it.
        connect_args["check_same_thread"] = False
        db_path = settings.database_url.removeprefix("sqlite:///")
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)

    if settings.is_sqlite:
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they do not exist yet."""
    # Import models so they are registered on Base.metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    logger.info("Database initialised")


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
