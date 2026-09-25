"""Aggregates all route modules into a single router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import chat, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(chat.router)
