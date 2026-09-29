"""
Domain exceptions and their mapping to HTTP responses.

Every error returned by the API has the same JSON shape:

    {"detail": "<human readable message>", "code": "<machine readable code>"}

so the frontend can handle errors uniformly.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "Internal server error."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class LLMServiceError(AppError):
    """The language model provider failed or is unreachable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "llm_unavailable"
    message = "The AI service is temporarily unavailable. Please try again later."

    def __init__(self, message: str | None = None, *, kind: str = "unknown") -> None:
        super().__init__(message)
        # Internal failure category (timeout, rate_limit, invalid_api_key, ...).
        # Used for logging and tests only — the HTTP response stays `llm_unavailable`.
        self.kind = kind


class ConversationNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "conversation_not_found"
    message = "Conversation not found."


def _error_body(detail: str, code: str) -> dict[str, str]:
    return {"detail": detail, "code": code}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach JSON error handlers to the FastAPI application."""

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError %s: %s", exc.code, exc.message)
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.message, exc.code))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Framework-level errors (malformed JSON, unknown route, wrong method).
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(str(exc.detail), f"http_{exc.status_code}"),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", []) if part != "body")
        detail = f"{field}: {first.get('msg', 'invalid value')}" if field else "Invalid request."
        return JSONResponse(
            status_code=422,
            content=_error_body(detail, "validation_error"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(AppError.message, AppError.code),
        )
