"""FastAPI dependency providers (wiring of services for each request)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.repositories import ConversationRepository
from app.database.session import get_db
from app.services.chat_service import ChatService
from app.services.llm_service import get_llm_provider


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(
        repository=ConversationRepository(db),
        llm=get_llm_provider(),
        settings=get_settings(),
    )
