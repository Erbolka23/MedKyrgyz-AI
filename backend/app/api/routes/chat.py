"""Chat endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse, ConversationHistory
from app.schemas.common import ErrorResponse
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])

_ERRORS = {
    422: {"model": ErrorResponse, "description": "Invalid request body"},
    503: {"model": ErrorResponse, "description": "AI service unavailable"},
    500: {"model": ErrorResponse, "description": "Unexpected server error"},
}


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses=_ERRORS,
    summary="Ask the medical assistant a question",
)
def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    """
    Send a user message and receive the assistant's answer in Kyrgyz or Russian.

    Pass `conversation_id` from the previous response to keep the context.
    """
    return service.handle_message(request)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationHistory,
    responses={404: {"model": ErrorResponse, "description": "Conversation not found"}},
    summary="Get the message history of a conversation",
)
def conversation_history(
    conversation_id: str, service: ChatService = Depends(get_chat_service)
) -> ConversationHistory:
    return service.get_history(conversation_id)
