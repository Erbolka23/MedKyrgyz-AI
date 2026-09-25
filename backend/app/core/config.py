"""
Application configuration.

Settings are read once from environment variables (optionally loaded from
`backend/.env`) and exposed as an immutable object through `get_settings()`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# backend/app/core/config.py -> backend/
BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
PROJECT_ROOT: Path = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")

SUPPORTED_LANGUAGES: tuple[str, ...] = ("ky", "ru")
SUPPORTED_PROVIDERS: tuple[str, ...] = ("auto", "openai", "mock")


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_database_url(url: str) -> str:
    """
    Make relative SQLite paths relative to the project root, so the database
    lands in `database/` no matter which directory uvicorn is started from.
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix) or url == "sqlite:///:memory:":
        return url
    raw_path = Path(url[len(prefix):])
    if not raw_path.is_absolute():
        raw_path = PROJECT_ROOT / raw_path
    return f"{prefix}{raw_path.as_posix()}"


def _optional_secret(name: str) -> str | None:
    """Treat empty values and the `.env.example` placeholder as 'not set'."""
    value = os.getenv(name, "").strip()
    if not value or value == "your_key_here":
        return None
    return value


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    app_name: str
    app_env: str
    debug: bool
    log_level: str
    cors_origins: list[str]
    database_url: str

    llm_provider: str
    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str
    llm_temperature: float
    llm_max_tokens: int
    llm_timeout_seconds: float

    default_language: str
    history_limit: int

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Build settings from the environment (cached for the process lifetime)."""
    provider = _env_str("LLM_PROVIDER", "auto").lower()
    if provider not in SUPPORTED_PROVIDERS:
        provider = "auto"

    default_language = _env_str("DEFAULT_LANGUAGE", "ky").lower()
    if default_language not in SUPPORTED_LANGUAGES:
        default_language = "ky"

    return Settings(
        app_name=_env_str("APP_NAME", "MedKyrgyz AI"),
        app_env=_env_str("APP_ENV", "development"),
        debug=_env_bool("DEBUG", False),
        log_level=_env_str("LOG_LEVEL", "INFO").upper(),
        cors_origins=_env_list(
            "CORS_ORIGINS",
            ["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:3000"],
        ),
        database_url=_resolve_database_url(
            _env_str("DATABASE_URL", "sqlite:///database/medkyrgyz.db")
        ),
        llm_provider=provider,
        openai_api_key=_optional_secret("OPENAI_API_KEY"),
        openai_base_url=_optional_secret("OPENAI_BASE_URL"),
        openai_model=_env_str("OPENAI_MODEL", "gpt-4o-mini"),
        llm_temperature=_env_float("LLM_TEMPERATURE", 0.3),
        llm_max_tokens=_env_int("LLM_MAX_TOKENS", 600),
        llm_timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 30.0),
        default_language=default_language,
        history_limit=max(0, _env_int("HISTORY_LIMIT", 10)),
    )
