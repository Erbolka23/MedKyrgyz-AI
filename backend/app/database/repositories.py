"""
Repository layer: the only place that knows how conversations and messages
are stored. Services use repositories instead of writing SQL queries directly.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message, MessageRole


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, conversation_id: str) -> Conversation | None:
        return self._db.get(Conversation, conversation_id)

    def create(self, language: str) -> Conversation:
        conversation = Conversation(language=language)
        self._db.add(conversation)
        self._db.flush()  # assigns the primary key
        return conversation

    def get_or_create(self, conversation_id: str | None, language: str) -> Conversation:
        """
        Return an existing conversation, or start a new one when the id is
        missing or unknown (e.g. the database was reset while the browser
        still remembered an old id).
        """
        if conversation_id:
            existing = self.get(conversation_id)
            if existing is not None:
                return existing
        return self.create(language)

    def add_message(
        self,
        conversation: Conversation,
        role: MessageRole,
        content: str,
        language: str,
        is_emergency: bool = False,
    ) -> Message:
        message = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            language=language,
            is_emergency=is_emergency,
        )
        self._db.add(message)
        conversation.language = language
        return message

    def recent_messages(self, conversation_id: str, limit: int) -> list[Message]:
        """Return the last `limit` messages in chronological order."""
        if limit <= 0:
            return []
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        return list(reversed(self._db.scalars(stmt).all()))

    def all_messages(self, conversation_id: str) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.asc())
        )
        return list(self._db.scalars(stmt).all())

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
