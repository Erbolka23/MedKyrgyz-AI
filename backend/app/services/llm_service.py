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

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import urlparse

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


# --------------------------------------------------------------------- errors


class LLMErrorKind(str, Enum):
    """Internal failure categories. Logged, never shown to the user."""

    INVALID_API_KEY = "invalid_api_key"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    QUOTA_EXCEEDED = "quota_exceeded"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    INVALID_MODEL = "invalid_model"
    CONTEXT_TOO_LONG = "context_too_long"
    UNSUPPORTED_PARAMETER = "unsupported_parameter"
    SERVER_ERROR = "server_error"
    EMPTY_RESPONSE = "empty_response"
    UNKNOWN = "unknown"


# Transient problems that may succeed on a second attempt.
_RETRYABLE = frozenset(
    {LLMErrorKind.TIMEOUT, LLMErrorKind.CONNECTION, LLMErrorKind.RATE_LIMIT, LLMErrorKind.SERVER_ERROR}
)

# Safe user-facing texts. Configuration problems (bad key, quota, unknown model)
# deliberately fall back to the generic "temporarily unavailable" message.
_USER_MESSAGES: dict[LLMErrorKind, str] = {
    LLMErrorKind.TIMEOUT: "The AI service took too long to respond. Please try again.",
    LLMErrorKind.RATE_LIMIT: "The AI service is busy right now. Please try again in a moment.",
    LLMErrorKind.CONTEXT_TOO_LONG: (
        "The conversation is too long for the AI service. Please start a new conversation."
    ),
    LLMErrorKind.EMPTY_RESPONSE: "The AI service returned an empty answer. Please try again.",
}

# Operator hints for errors that need a configuration change, not a retry.
_ADMIN_HINTS: dict[LLMErrorKind, str] = {
    LLMErrorKind.INVALID_API_KEY: "check OPENAI_API_KEY",
    LLMErrorKind.AUTHENTICATION: "check OPENAI_API_KEY and the key's project/model permissions",
    LLMErrorKind.QUOTA_EXCEEDED: "check the OpenAI account billing and usage limits",
    LLMErrorKind.INVALID_MODEL: "check OPENAI_MODEL (and OPENAI_BASE_URL)",
    LLMErrorKind.CONTEXT_TOO_LONG: "lower HISTORY_LIMIT or LLM_MAX_INPUT_CHARS",
}

_TOKEN_PARAMS: tuple[str, ...] = ("max_completion_tokens", "max_tokens")
_ADJUSTABLE_PARAMS: tuple[str, ...] = (*_TOKEN_PARAMS, "temperature")
_UNSUPPORTED_MARKERS: tuple[str, ...] = (
    "unsupported", "not supported", "unrecognized", "unknown parameter", "extra", "not permitted",
)


def _error_fields(exc: BaseException) -> tuple[int | None, str, str, str]:
    status = getattr(exc, "status_code", None)
    code = str(getattr(exc, "code", None) or "").lower()
    param = str(getattr(exc, "param", None) or "").lower()
    message = str(getattr(exc, "message", None) or exc).lower()
    return (status if isinstance(status, int) else None), code, param, message


def rejected_parameter(exc: BaseException) -> str | None:
    """Name of the request parameter the server refused (only ones we can drop/swap)."""
    status, code, param, message = _error_fields(exc)
    if status not in (400, 422):
        return None
    if code not in ("unsupported_parameter", "unsupported_value") and not any(
        marker in message for marker in _UNSUPPORTED_MARKERS
    ):
        return None
    if param in _ADJUSTABLE_PARAMS:
        return param
    # No `param` field (common on OpenAI-compatible servers): take the first
    # parameter mentioned — "'max_tokens' is not supported ... use 'max_completion_tokens'".
    mentioned = [(message.find(name), name) for name in _ADJUSTABLE_PARAMS if name in message]
    return min(mentioned)[1] if mentioned else None


def classify_openai_error(exc: BaseException) -> LLMErrorKind:
    """Map an OpenAI SDK exception (or anything else) to an `LLMErrorKind`."""
    try:
        import openai
    except ImportError:  # pragma: no cover - the SDK is a hard dependency
        return LLMErrorKind.UNKNOWN

    # APITimeoutError is a subclass of APIConnectionError — check it first.
    if isinstance(exc, openai.APITimeoutError):
        return LLMErrorKind.TIMEOUT
    if isinstance(exc, openai.APIConnectionError):
        return LLMErrorKind.CONNECTION
    if not isinstance(exc, openai.OpenAIError):
        return LLMErrorKind.UNKNOWN

    status, code, param, message = _error_fields(exc)
    if isinstance(exc, openai.AuthenticationError) or status == 401:
        if code == "invalid_api_key" or "api key" in message:
            return LLMErrorKind.INVALID_API_KEY
        return LLMErrorKind.AUTHENTICATION
    if isinstance(exc, openai.PermissionDeniedError) or status == 403:
        return LLMErrorKind.AUTHENTICATION
    if isinstance(exc, openai.RateLimitError) or status == 429:
        if code == "insufficient_quota" or "quota" in message:
            return LLMErrorKind.QUOTA_EXCEEDED
        return LLMErrorKind.RATE_LIMIT
    if code == "model_not_found" or param == "model" or (status == 404 and "model" in message):
        return LLMErrorKind.INVALID_MODEL
    if code == "context_length_exceeded" or "maximum context length" in message:
        return LLMErrorKind.CONTEXT_TOO_LONG
    if rejected_parameter(exc) is not None:
        return LLMErrorKind.UNSUPPORTED_PARAMETER
    if status is not None and status >= 500:
        return LLMErrorKind.SERVER_ERROR
    return LLMErrorKind.UNKNOWN


# ------------------------------------------------------------------ helpers


def is_official_openai(base_url: str | None) -> bool:
    """True for api.openai.com (the default when OPENAI_BASE_URL is empty)."""
    if not base_url:
        return True
    host = (urlparse(base_url).hostname or "").lower()
    return host == "openai.com" or host.endswith(".openai.com")


def resolve_token_param(settings: Settings) -> str:
    """
    Which field limits the answer length.

    OpenAI deprecated `max_tokens` for chat completions; newer models (o-series,
    gpt-5*) reject it and require `max_completion_tokens`, which gpt-4o/gpt-4o-mini
    also accept. Many OpenAI-compatible servers still only know `max_tokens`.
    Either way the provider adapts at runtime if the server refuses the choice.
    """
    if settings.openai_token_param != "auto":
        return settings.openai_token_param
    return "max_completion_tokens" if is_official_openai(settings.openai_base_url) else "max_tokens"


def fit_messages_to_budget(messages: list[LLMMessage], max_chars: int) -> list[LLMMessage]:
    """
    Keep the prompt below a rough size limit by dropping the OLDEST history.
    System prompt(s) and the latest message are always kept.
    """
    if sum(len(m.content) for m in messages) <= max_chars:
        return list(messages)

    system = [m for m in messages if m.role == "system"]
    dialogue = [m for m in messages if m.role != "system"]
    latest, history = dialogue[-1:], dialogue[:-1]

    budget = max_chars - sum(len(m.content) for m in system + latest)
    kept: list[LLMMessage] = []
    for message in reversed(history):
        if len(message.content) > budget:
            break
        kept.append(message)
        budget -= len(message.content)
    kept.reverse()

    logger.info(
        "Prompt trimmed to fit LLM_MAX_INPUT_CHARS: dropped %d old message(s)", len(history) - len(kept)
    )
    return system + kept + latest


# SDK requires a non-empty key; keyless OpenAI-compatible servers ignore it.
_KEYLESS_PLACEHOLDER = "not-needed"
# Always passed explicitly: with base_url=None the SDK reads os.environ["OPENAI_BASE_URL"],
# and an empty "OPENAI_BASE_URL=" line in .env (loaded by load_dotenv) makes that "" —
# every request then fails with "URL is missing an 'http://' or 'https://' protocol".
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(LLMProvider):
    """
    OpenAI Chat Completions provider.

    * One time budget (LLM_TIMEOUT_SECONDS) covers the whole answer, retries
      included, so the backend gives up before the frontend's 45 s timeout.
    * Retries are done here (SDK retries are disabled) and only for transient
      errors: timeouts, connection problems, rate limits, 5xx.
    * If the model rejects `max_tokens` / `max_completion_tokens` / `temperature`,
      the request is adjusted and re-sent; the adjustment is remembered.
    """

    name = "openai"

    _MIN_ATTEMPT_SECONDS = 3.0  # do not start a retry with less time than this
    _BACKOFF_SECONDS = 1.0
    _MAX_ADAPTATIONS = 3

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if client is None:
            # Imported lazily so the mock provider works even without the SDK installed.
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.openai_api_key or _KEYLESS_PLACEHOLDER,
                base_url=settings.openai_base_url or OPENAI_DEFAULT_BASE_URL,
                timeout=settings.llm_timeout_seconds,
                max_retries=0,
            )
        self._client = client
        self._model = settings.openai_model
        self._temperature = settings.llm_temperature
        self._max_tokens = settings.llm_max_tokens
        self._budget = settings.llm_timeout_seconds
        self._max_retries = settings.llm_max_retries
        self._max_input_chars = settings.llm_max_input_chars

        # Request shape; may be adapted at runtime (shared across request threads).
        self._lock = threading.Lock()
        self._token_param: str | None = resolve_token_param(settings)
        self._rejected_token_params: set[str] = set()
        self._send_temperature = True

        # Overridable in tests.
        self._now: Callable[[], float] = time.monotonic
        self._sleep: Callable[[float], None] = time.sleep

    @property
    def token_param(self) -> str | None:
        return self._token_param

    @property
    def sends_temperature(self) -> bool:
        return self._send_temperature

    def generate(self, messages: list[LLMMessage], language: str) -> str:
        payload = [
            {"role": m.role, "content": m.content}
            for m in fit_messages_to_budget(messages, self._max_input_chars)
        ]
        deadline = self._now() + self._budget
        retries_left = self._max_retries
        adaptations_left = self._MAX_ADAPTATIONS
        attempts = 0

        while True:
            remaining = deadline - self._now()
            if remaining <= 0:
                raise self._failure(LLMErrorKind.TIMEOUT, None, attempts)

            with self._lock:
                token_param, send_temperature = self._token_param, self._send_temperature
            attempts += 1
            try:
                completion = self._client.chat.completions.create(
                    **self._request_kwargs(payload, token_param, send_temperature),
                    timeout=remaining,
                )
            except Exception as exc:  # noqa: BLE001 - every failure is classified below
                kind = classify_openai_error(exc)
                if (
                    kind is LLMErrorKind.UNSUPPORTED_PARAMETER
                    and adaptations_left > 0
                    and self._adapt(rejected_parameter(exc), token_param, send_temperature)
                ):
                    adaptations_left -= 1
                    continue
                if (
                    kind in _RETRYABLE
                    and retries_left > 0
                    and deadline - self._now() >= self._BACKOFF_SECONDS + self._MIN_ATTEMPT_SECONDS
                ):
                    retries_left -= 1
                    logger.warning(
                        "OpenAI request failed (kind=%s, attempt=%d) — retrying", kind.value, attempts
                    )
                    self._sleep(self._BACKOFF_SECONDS)
                    continue
                raise self._failure(kind, exc, attempts) from exc

            return self._extract_answer(completion)

    # ----------------------------------------------------------------- helpers

    def _request_kwargs(
        self, payload: list[dict[str, str]], token_param: str | None, send_temperature: bool
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"model": self._model, "messages": payload}
        if send_temperature:
            kwargs["temperature"] = self._temperature
        if token_param:
            # Sent via extra_body: older SDK releases allowed by requirements.txt do
            # not accept `max_completion_tokens` as a keyword argument.
            kwargs["extra_body"] = {token_param: self._max_tokens}
        return kwargs

    def _adapt(self, param: str | None, used_token_param: str | None, used_temperature: bool) -> bool:
        """Drop/swap a parameter the model refused. Returns True if the request changed."""
        if param not in _ADJUSTABLE_PARAMS:
            return False
        with self._lock:
            if param == "temperature":
                self._send_temperature = False
            else:
                self._rejected_token_params.add(param)
                if self._token_param == param:
                    other = next(p for p in _TOKEN_PARAMS if p != param)
                    self._token_param = None if other in self._rejected_token_params else other
            token_param, send_temperature = self._token_param, self._send_temperature
        changed = (token_param, send_temperature) != (used_token_param, used_temperature)
        if changed:
            logger.warning(
                "Model %s rejected '%s' — using token_param=%s, temperature=%s from now on",
                self._model, param, token_param or "none", "on" if send_temperature else "default",
            )
        return changed

    def _extract_answer(self, completion: Any) -> str:
        choices = getattr(completion, "choices", None) or []
        choice = choices[0] if choices else None
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        finish_reason = getattr(choice, "finish_reason", None)

        if isinstance(content, str) and content.strip():
            if finish_reason == "length":
                logger.warning(
                    "OpenAI answer was cut by the token limit (LLM_MAX_TOKENS=%d)", self._max_tokens
                )
            return content.strip()

        if finish_reason == "length":
            # Typical for reasoning models: hidden reasoning used up the whole limit.
            logger.error(
                "OpenAI returned no text: token limit reached (model=%s, LLM_MAX_TOKENS=%d)"
                " — raise LLM_MAX_TOKENS",
                self._model, self._max_tokens,
            )
        raise self._failure(LLMErrorKind.EMPTY_RESPONSE, None, 1)

    def _failure(self, kind: LLMErrorKind, exc: BaseException | None, attempts: int) -> LLMServiceError:
        """Log the internal details once and build a safe user-facing error."""
        status, code = (_error_fields(exc)[:2]) if exc is not None else (None, "")
        hint = _ADMIN_HINTS.get(kind)
        # Never log the SDK error message: it may echo parts of the key or the prompt.
        logger.error(
            "OpenAI request failed: kind=%s error=%s status=%s code=%s model=%s attempts=%d%s",
            kind.value, type(exc).__name__ if exc is not None else "-", status or "-", code or "-",
            self._model, attempts, f" hint: {hint}" if hint else "",
        )
        return LLMServiceError(_USER_MESSAGES.get(kind), kind=kind.value)


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
    """
    Choose a provider according to LLM_PROVIDER and the available API key.

    Falls back to MockProvider (with a log message) when OpenAI cannot be used;
    `/health` then reports "mock", so the active provider is always visible.
    """
    if settings.llm_provider == "mock":
        logger.info("Using offline MockProvider (LLM_PROVIDER=mock)")
        return MockProvider()

    wants_openai = settings.llm_provider == "openai" or (
        settings.llm_provider == "auto" and settings.openai_api_key
    )
    if not wants_openai:
        logger.warning("Using offline MockProvider — set OPENAI_API_KEY for real AI answers")
        return MockProvider()

    # A key is mandatory for api.openai.com; a custom OPENAI_BASE_URL may be keyless.
    if not settings.openai_api_key and is_official_openai(settings.openai_base_url):
        logger.warning("LLM_PROVIDER=openai but OPENAI_API_KEY is empty — using mock provider")
        return MockProvider()

    try:
        provider = OpenAIProvider(settings)
    except Exception as exc:  # noqa: BLE001 - missing SDK, malformed base URL, ...
        logger.error(
            "Could not initialise the OpenAI provider (%s) — using mock provider", type(exc).__name__
        )
        return MockProvider()

    logger.info(
        "Using OpenAIProvider (model=%s, endpoint=%s, token_param=%s, timeout=%.0fs, retries=%d)",
        settings.openai_model,
        "openai" if is_official_openai(settings.openai_base_url) else "custom",
        provider.token_param, settings.llm_timeout_seconds, settings.llm_max_retries,
    )
    return provider


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Process-wide provider instance (the HTTP client is reused between requests)."""
    return create_llm_provider(get_settings())
