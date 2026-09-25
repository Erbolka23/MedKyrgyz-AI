"""
LLM provider abstraction.

`LLMProvider` is the only interface the rest of the application depends on.
Swapping OpenAI for another vendor (Anthropic, a local Ollama model, a
fine-tuned Kyrgyz model...) means adding one class here — nothing else changes.

Providers:
  * OpenAIProvider — OpenAI or any OpenAI-compatible API (via OPENAI_BASE_URL).
  * MockProvider   — offline, rule-based answers. Lets the frontend be built
                     and the test-suite run without an API key or internet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from app.core.config import Settings, get_settings
from app.core.exceptions import LLMServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str


class LLMProvider(ABC):
    """Common interface for all language model backends."""

    name: str = "base"

    @abstractmethod
    def generate(self, messages: list[LLMMessage], language: str) -> str:
        """Return the assistant's reply for the given conversation."""


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        # Imported lazily so the mock provider works even without the SDK installed.
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )
        self._model = settings.openai_model
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens

    def generate(self, messages: list[LLMMessage], language: str) -> str:
        from openai import OpenAIError

        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        except OpenAIError as exc:
            logger.error("OpenAI request failed: %s", type(exc).__name__)
            raise LLMServiceError() from exc

        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise LLMServiceError("The AI service returned an empty answer.")
        return content


class MockProvider(LLMProvider):
    """
    Deterministic offline provider. Recognises a few common complaints and
    otherwise asks a generic clarifying question, mimicking the real
    assistant's behaviour closely enough for UI development and tests.
    """

    name = "mock"

    _RULES: tuple[tuple[tuple[str, ...], dict[str, str]], ...] = (
        (
            ("башым", "баш оору", "голов"),
            {
                "ky": (
                    "Качантан бери ооруп жатат? "
                    "Ошондой эле оорунун күчү кандай экенин (жеңил, орточо, катуу) жана "
                    "ысык, жүрөк айлануу сыяктуу башка белгилер бар-жогун айтып бериңизчи."
                ),
                "ru": (
                    "Как давно у вас болит голова? "
                    "Расскажите также, насколько сильная боль (слабая, умеренная, сильная) "
                    "и есть ли другие симптомы — температура, тошнота?"
                ),
            },
        ),
        (
            ("ысык", "температур", "ысыгым"),
            {
                "ky": (
                    "Ысыгыңыз канча градус жана канча күндөн бери? "
                    "Көп суюктук ичип, эс алыңыз. Ысык 3 күндөн ашык сакталса же 39°C жогору болсо, "
                    "дарыгерге кайрылыңыз."
                ),
                "ru": (
                    "Какая у вас температура и сколько дней она держится? "
                    "Пейте больше жидкости и отдыхайте. Если температура держится дольше 3 дней "
                    "или выше 39°C — обратитесь к врачу."
                ),
            },
        ),
    )

    _FALLBACK: dict[str, str] = {
        "ky": (
            "Сурооңуз үчүн рахмат. Так маалымат берүү үчүн тактап алайын: "
            "белгилер качантан бери байкалып жатат жана алар канчалык күчтүү? "
            "Абалыңыз начарласа, үй-бүлөлүк дарыгериңизге кайрылыңыз."
        ),
        "ru": (
            "Спасибо за вопрос. Чтобы дать точную информацию, уточните, пожалуйста: "
            "как давно появились симптомы и насколько они выражены? "
            "Если состояние ухудшится — обратитесь к семейному врачу."
        ),
    }

    def generate(self, messages: list[LLMMessage], language: str) -> str:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        lowered = last_user.lower()
        for keywords, answers in self._RULES:
            if any(keyword in lowered for keyword in keywords):
                return answers[language]
        return self._FALLBACK[language]


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Choose a provider according to LLM_PROVIDER and the available API key."""
    wants_openai = settings.llm_provider == "openai" or (
        settings.llm_provider == "auto" and settings.openai_api_key
    )
    if wants_openai:
        if not settings.openai_api_key and not settings.openai_base_url:
            logger.warning("LLM_PROVIDER=openai but OPENAI_API_KEY is empty — using mock provider")
            return MockProvider()
        return OpenAIProvider(settings)

    logger.warning("Using offline MockProvider — set OPENAI_API_KEY for real AI answers")
    return MockProvider()


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Process-wide provider instance (the HTTP client is reused between requests)."""
    return create_llm_provider(get_settings())
