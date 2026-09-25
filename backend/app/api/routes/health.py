"""Liveness endpoint used by the frontend and deployment checks."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.schemas.common import HealthResponse
from app.services.llm_service import get_llm_provider

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, llm_provider=get_llm_provider().name)
