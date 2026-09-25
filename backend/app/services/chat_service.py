"""
Chat orchestration — the heart of the backend.

Pipeline for one user message:

    1. resolve answer language (explicit or auto-detected)
    2. load / create the conversation
    3. emergency check      -> fixed emergency answer, LLM is skipped
    4. build prompt (system prompt + recent history + new message)
    5. call the LLM provider
    6. output guard (no dosages / prescriptions)
    7. persist both messages and return the response
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import ConversationNotFoundError
from app.core.logging import get_logger
from app.core.prompts import DISCLAIMERS, build_system_prompt
from app.database.repositories import ConversationRepository
from app.models.conversation import Message, MessageRole
from app.schemas.chat import ChatRequest, ChatResponse, ConversationHistory, MessageOut, RequestLanguage
from app.services.language_service import detect_language
from app.services.llm_service import LLMMessage, LLMProvider
from app.services.safety_service import AnswerGuard, EmergencyDetector

logger = get_logger(__name__)


class ChatService:
    def __init__(
        self,
        repository: ConversationRepository,
        llm: LLMProvider,
        settings: Settings,
        emergency_detector: EmergencyDetector | None = None,
        answer_guard: AnswerGuard | None = None,
    ) -> None:
        self._repo = repository
        self._llm = llm
        self._settings = settings
        self._emergency = emergency_detector or EmergencyDetector()
        self._guard = answer_guard or AnswerGuard()

    # ------------------------------------------------------------------ public

    def handle_message(self, request: ChatRequest) -> ChatResponse:
        language = self._resolve_language(request)
        conversation = self._repo.get_or_create(request.conversation_id, language)
        emergency = self._emergency.check(request.message)

        if emergency.is_emergency:
            answer = self._emergency.emergency_message(language)
        else:
            # History is read BEFORE the new message is stored, so it is not duplicated.
            history = self._repo.recent_messages(conversation.id, self._settings.history_limit)
            prompt = self._build_prompt(history, request.message, language)
            raw_answer = self._llm.generate(prompt, language)
            answer = self._guard.sanitise(raw_answer, language)

        try:
            self._repo.add_message(
                conversation, MessageRole.USER, request.message, language, emergency.is_emergency
            )
            self._repo.add_message(
                conversation, MessageRole.ASSISTANT, answer, language, emergency.is_emergency
            )
            self._repo.commit()
        except Exception:
            self._repo.rollback()
            raise

        # Metadata only — never log medical content.
        logger.info(
            "chat conversation=%s lang=%s emergency=%s provider=%s in_len=%d out_len=%d",
            conversation.id, language, emergency.is_emergency, self._llm.name,
            len(request.message), len(answer),
        )

        return ChatResponse(
            answer=answer,
            conversation_id=conversation.id,
            language=language,  # type: ignore[arg-type]
            is_emergency=emergency.is_emergency,
            disclaimer=DISCLAIMERS[language],
        )

    def get_history(self, conversation_id: str) -> ConversationHistory:
        if self._repo.get(conversation_id) is None:
            raise ConversationNotFoundError()
        messages = self._repo.all_messages(conversation_id)
        return ConversationHistory(
            conversation_id=conversation_id,
            messages=[MessageOut.model_validate(m) for m in messages],
        )

    # ----------------------------------------------------------------- helpers

    def _resolve_language(self, request: ChatRequest) -> str:
        if request.language == RequestLanguage.AUTO:
            return detect_language(request.message, default=self._settings.default_language)
        return request.language.value

    @staticmethod
    def _build_prompt(history: list[Message], message: str, language: str) -> list[LLMMessage]:
        prompt = [LLMMessage(role="system", content=build_system_prompt(language))]
        prompt.extend(LLMMessage(role=m.role.value, content=m.content) for m in history)
        prompt.append(LLMMessage(role="user", content=message))
        return prompt
