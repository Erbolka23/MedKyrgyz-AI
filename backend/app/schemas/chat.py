"""
Chat API contract.

This file is the single source of truth for the frontend <-> backend
integration. Any change here must be reflected in docs/api.md and
frontend/js/api.js.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MESSAGE_LENGTH = 2000

AnswerLanguage = Literal["ky", "ru"]


class RequestLanguage(str, Enum):
    KY = "ky"
    RU = "ru"
    AUTO = "auto"


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGE_LENGTH,
        description="The user's question.",
        examples=["Башым ооруп жатат"],
    )
    language: RequestLanguage = Field(
        default=RequestLanguage.AUTO,
        description="Answer language. `auto` detects it from the message.",
    )
    conversation_id: str | None = Field(
        default=None,
        max_length=36,
        description="Id returned by a previous response; omit to start a new conversation.",
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


class ChatResponse(BaseModel):
    answer: str = Field(..., examples=["Качантан бери ооруп жатат?"])
    conversation_id: str
    language: AnswerLanguage
    is_emergency: bool = Field(
        default=False, description="True when emergency symptoms were detected."
    )
    disclaimer: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "assistant"]
    content: str
    language: AnswerLanguage
    is_emergency: bool
    created_at: datetime

    @field_validator("role", mode="before")
    @classmethod
    def role_to_str(cls, value: object) -> object:
        return getattr(value, "value", value)


class ConversationHistory(BaseModel):
    conversation_id: str
    messages: list[MessageOut]
