"""
OpenAI integration layer tests.

No real OpenAI calls: the SDK client is replaced by `FakeClient`, SDK
exceptions are built without HTTP objects and time is simulated by `FakeClock`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import openai
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.core.config import MAX_LLM_TIMEOUT_SECONDS, Settings, get_settings
from app.core.exceptions import LLMServiceError
from app.services import llm_service
from app.services.llm_service import (
    LLMErrorKind,
    LLMMessage,
    MockProvider,
    OpenAIProvider,
    classify_openai_error,
    create_llm_provider,
    fit_messages_to_budget,
    resolve_token_param,
)

FAKE_KEY = "sk-test-not-a-real-key-1234567890"
PROMPT = [LLMMessage("system", "You are a helper."), LLMMessage("user", "Башым ооруп жатат")]


# ------------------------------------------------------------------ helpers


def make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "llm_provider": "openai",
        "openai_api_key": FAKE_KEY,
        "openai_base_url": None,
        "openai_model": "gpt-4o-mini",
        "openai_token_param": "auto",
        "llm_temperature": 0.3,
        "llm_max_tokens": 600,
        "llm_timeout_seconds": 30.0,
        "llm_max_retries": 1,
        "llm_max_input_chars": 24000,
    }
    return replace(get_settings(), **{**defaults, **overrides})


def api_error(cls: type[Exception], message: str = "error", *, status: int | None = None,
              code: str | None = None, param: str | None = None) -> Exception:
    """Build an SDK exception without the httpx request/response it normally needs."""
    exc = cls.__new__(cls)
    Exception.__init__(exc, message)
    exc.message = message  # type: ignore[attr-defined]
    exc.status_code = status  # type: ignore[attr-defined]
    exc.code = code  # type: ignore[attr-defined]
    exc.param = param  # type: ignore[attr-defined]
    exc.body = None  # type: ignore[attr-defined]
    return exc


def completion(text: str | None, finish_reason: str = "stop") -> SimpleNamespace:
    message = SimpleNamespace(content=text)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


Outcome = Any  # completion object | exception | callable(kwargs) -> either


class FakeClient:
    """Stands in for `openai.OpenAI`; plays back scripted outcomes and records calls."""

    def __init__(self, *outcomes: Outcome) -> None:
        self._outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if callable(outcome) and not isinstance(outcome, BaseException):
            outcome = outcome(kwargs)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def make_provider(client: FakeClient, clock: FakeClock | None = None, **overrides: Any) -> OpenAIProvider:
    provider = OpenAIProvider(make_settings(**overrides), client=client)
    clock = clock or FakeClock()
    provider._now = clock
    provider._sleep = clock.sleep
    return provider


def slow_timeout(clock: FakeClock, seconds: float | None = None) -> Callable[[dict[str, Any]], Exception]:
    """An attempt that burns `seconds` (capped by, and defaulting to, its timeout) and times out."""

    def outcome(kwargs: dict[str, Any]) -> Exception:
        clock.now += kwargs["timeout"] if seconds is None else min(seconds, kwargs["timeout"])
        return api_error(openai.APITimeoutError, "Request timed out.")

    return outcome


# -------------------------------------------------------- provider selection


def test_mock_provider_when_explicitly_requested() -> None:
    assert isinstance(create_llm_provider(make_settings(llm_provider="mock")), MockProvider)


def test_auto_with_key_selects_openai() -> None:
    provider = create_llm_provider(make_settings(llm_provider="auto"))
    assert isinstance(provider, OpenAIProvider)
    assert provider.name == "openai"


def test_auto_without_key_selects_mock() -> None:
    provider = create_llm_provider(make_settings(llm_provider="auto", openai_api_key=None))
    assert isinstance(provider, MockProvider)


def test_openai_without_key_falls_back_to_mock() -> None:
    provider = create_llm_provider(make_settings(openai_api_key=None))
    assert provider.name == "mock"


def test_openai_without_key_for_official_base_url_falls_back_to_mock() -> None:
    settings = make_settings(openai_api_key=None, openai_base_url="https://api.openai.com/v1")
    assert create_llm_provider(settings).name == "mock"


def test_keyless_compatible_server_selects_openai_with_max_tokens() -> None:
    settings = make_settings(openai_api_key=None, openai_base_url="http://localhost:11434/v1")
    provider = create_llm_provider(settings)
    assert isinstance(provider, OpenAIProvider)
    assert provider.token_param == "max_tokens"


def test_client_initialisation_failure_falls_back_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenProvider(OpenAIProvider):
        def __init__(self, settings: Settings, client: Any | None = None) -> None:
            raise RuntimeError("SDK missing")

    monkeypatch.setattr(llm_service, "OpenAIProvider", BrokenProvider)
    assert create_llm_provider(make_settings()).name == "mock"


def test_sdk_retries_are_disabled_and_timeout_is_budget() -> None:
    provider = OpenAIProvider(make_settings(llm_timeout_seconds=25.0))
    assert provider._client.max_retries == 0
    assert provider._client.timeout == 25.0


# ------------------------------------------------------ invalid configuration


@pytest.fixture()
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.usefixtures("fresh_settings")
def test_invalid_env_values_fall_back_to_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_TOKEN_PARAM", "max_output_tokens")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "not-a-number")
    monkeypatch.setenv("LLM_MAX_RETRIES", "-4")
    monkeypatch.setenv("LLM_MAX_TOKENS", "0")
    monkeypatch.setenv("LLM_TEMPERATURE", "7")
    settings = get_settings()
    assert settings.llm_provider == "auto"
    assert settings.openai_token_param == "auto"
    assert settings.llm_timeout_seconds == 30.0
    assert settings.llm_max_retries == 0
    assert settings.llm_max_tokens == 1
    assert settings.llm_temperature == 2.0


@pytest.mark.usefixtures("fresh_settings")
def test_timeout_and_retries_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "300")
    monkeypatch.setenv("LLM_MAX_RETRIES", "50")
    settings = get_settings()
    assert settings.llm_timeout_seconds == MAX_LLM_TIMEOUT_SECONDS
    assert settings.llm_max_retries == config.MAX_LLM_RETRIES


@pytest.mark.usefixtures("fresh_settings")
def test_placeholder_key_is_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "your_key_here")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    settings = get_settings()
    assert settings.openai_api_key is None
    assert create_llm_provider(settings).name == "mock"


def test_backend_budget_is_below_frontend_timeout() -> None:
    frontend_config = Path(__file__).resolve().parents[2] / "frontend" / "js" / "config.js"
    match = re.search(r"REQUEST_TIMEOUT_MS:\s*(\d+)", frontend_config.read_text(encoding="utf-8"))
    assert match, "REQUEST_TIMEOUT_MS not found in frontend/js/config.js"
    assert MAX_LLM_TIMEOUT_SECONDS * 1000 < int(match.group(1))


def test_api_key_is_not_in_settings_repr() -> None:
    assert FAKE_KEY not in repr(make_settings())


# ------------------------------------------------- request shape & fallbacks


def test_token_param_resolution() -> None:
    assert resolve_token_param(make_settings()) == "max_completion_tokens"
    assert resolve_token_param(make_settings(openai_base_url="https://api.openai.com/v1")) == "max_completion_tokens"
    assert resolve_token_param(make_settings(openai_base_url="http://127.0.0.1:8001/v1")) == "max_tokens"
    assert resolve_token_param(make_settings(openai_token_param="max_tokens")) == "max_tokens"


def test_successful_request_shape() -> None:
    client = FakeClient(completion("  Качантан бери?  "))
    answer = make_provider(client).generate(PROMPT, "ky")

    assert answer == "Качантан бери?"
    call = client.calls[0]
    assert call["model"] == "gpt-4o-mini"
    assert call["temperature"] == 0.3
    assert call["extra_body"] == {"max_completion_tokens": 600}
    assert "max_tokens" not in call
    assert call["timeout"] == pytest.approx(30.0)
    assert call["messages"] == [{"role": m.role, "content": m.content} for m in PROMPT]


def test_rejected_max_completion_tokens_falls_back_to_max_tokens() -> None:
    # Typical OpenAI-compatible server: no `param` field, parameter named in the message.
    rejected = api_error(
        openai.BadRequestError, "Extra inputs are not permitted: max_completion_tokens", status=400
    )
    client = FakeClient(rejected, completion("ok"), completion("ok again"))
    provider = make_provider(client)

    assert provider.generate(PROMPT, "ru") == "ok"
    assert client.calls[1]["extra_body"] == {"max_tokens": 600}
    # The adaptation is remembered: the next request goes straight to max_tokens.
    provider.generate(PROMPT, "ru")
    assert len(client.calls) == 3
    assert client.calls[2]["extra_body"] == {"max_tokens": 600}


def test_rejected_max_tokens_switches_to_max_completion_tokens() -> None:
    rejected = api_error(
        openai.BadRequestError,
        "Unsupported parameter: 'max_tokens' is not supported with this model. "
        "Use 'max_completion_tokens' instead.",
        status=400, code="unsupported_parameter", param="max_tokens",
    )
    client = FakeClient(rejected, completion("ok"))
    provider = make_provider(client, openai_token_param="max_tokens")

    assert provider.generate(PROMPT, "ky") == "ok"
    assert client.calls[1]["extra_body"] == {"max_completion_tokens": 600}


def test_both_token_params_rejected_sends_no_limit() -> None:
    client = FakeClient(
        api_error(openai.BadRequestError, "unsupported", status=400,
                  code="unsupported_parameter", param="max_completion_tokens"),
        api_error(openai.BadRequestError, "unsupported", status=400,
                  code="unsupported_parameter", param="max_tokens"),
        completion("ok"),
    )
    provider = make_provider(client)

    assert provider.generate(PROMPT, "ky") == "ok"
    assert "extra_body" not in client.calls[2]
    assert provider.token_param is None


def test_unsupported_temperature_is_dropped() -> None:
    rejected = api_error(
        openai.BadRequestError,
        "Unsupported value: 'temperature' does not support 0.3 with this model.",
        status=400, code="unsupported_value", param="temperature",
    )
    client = FakeClient(rejected, completion("ok"))
    provider = make_provider(client, openai_model="gpt-5-mini")

    assert provider.generate(PROMPT, "ky") == "ok"
    assert "temperature" not in client.calls[1]
    assert provider.sends_temperature is False


def test_prompt_is_trimmed_to_budget_keeping_system_and_latest() -> None:
    messages = [
        LLMMessage("system", "S" * 100),
        LLMMessage("user", "old question " * 50),
        LLMMessage("assistant", "old answer " * 50),
        LLMMessage("user", "recent"),
        LLMMessage("assistant", "reply"),
        LLMMessage("user", "latest question"),
    ]
    trimmed = fit_messages_to_budget(messages, max_chars=200)
    assert trimmed[0] == messages[0]
    assert trimmed[-1] == messages[-1]
    assert messages[1] not in trimmed and messages[2] not in trimmed
    assert messages[3] in trimmed and messages[4] in trimmed
    assert fit_messages_to_budget(messages, max_chars=10_000) == messages


# ------------------------------------------------------------ error handling


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (api_error(openai.AuthenticationError, "Incorrect API key provided: sk-test***", status=401,
                   code="invalid_api_key"), LLMErrorKind.INVALID_API_KEY),
        (api_error(openai.AuthenticationError, "Organization has been disabled", status=401),
         LLMErrorKind.AUTHENTICATION),
        (api_error(openai.PermissionDeniedError, "Project does not have access", status=403),
         LLMErrorKind.AUTHENTICATION),
        (api_error(openai.RateLimitError, "Rate limit reached for requests", status=429,
                   code="rate_limit_exceeded"), LLMErrorKind.RATE_LIMIT),
        (api_error(openai.RateLimitError, "You exceeded your current quota", status=429,
                   code="insufficient_quota"), LLMErrorKind.QUOTA_EXCEEDED),
        (api_error(openai.APITimeoutError, "Request timed out."), LLMErrorKind.TIMEOUT),
        (api_error(openai.APIConnectionError, "Connection error."), LLMErrorKind.CONNECTION),
        (api_error(openai.NotFoundError, "The model `gpt-9` does not exist", status=404,
                   code="model_not_found"), LLMErrorKind.INVALID_MODEL),
        (api_error(openai.BadRequestError, "This model's maximum context length is 128000 tokens",
                   status=400, code="context_length_exceeded"), LLMErrorKind.CONTEXT_TOO_LONG),
        (api_error(openai.InternalServerError, "server error", status=500), LLMErrorKind.SERVER_ERROR),
        (api_error(openai.BadRequestError, "Invalid 'messages'", status=400), LLMErrorKind.UNKNOWN),
        (ValueError("something odd"), LLMErrorKind.UNKNOWN),
    ],
)
def test_error_classification(exc: Exception, kind: LLMErrorKind) -> None:
    assert classify_openai_error(exc) is kind


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (api_error(openai.AuthenticationError, f"Incorrect API key provided: {FAKE_KEY}", status=401,
                   code="invalid_api_key"), "invalid_api_key"),
        (api_error(openai.RateLimitError, "You exceeded your current quota", status=429,
                   code="insufficient_quota"), "quota_exceeded"),
        (api_error(openai.NotFoundError, "The model `gpt-9` does not exist", status=404,
                   code="model_not_found"), "invalid_model"),
        (RuntimeError(f"internal detail {FAKE_KEY}"), "unknown"),
    ],
)
def test_configuration_errors_fail_fast_with_safe_message(
    exc: Exception, kind: str, caplog: pytest.LogCaptureFixture
) -> None:
    client = FakeClient(exc)
    with pytest.raises(LLMServiceError) as raised:
        make_provider(client).generate(PROMPT, "ky")

    assert len(client.calls) == 1  # not retried
    assert raised.value.kind == kind
    assert raised.value.code == "llm_unavailable"
    assert raised.value.status_code == 503
    assert raised.value.message == LLMServiceError.message  # generic, no internals
    assert FAKE_KEY not in caplog.text
    assert f"kind={kind}" in caplog.text


def test_rate_limit_is_retried_then_succeeds() -> None:
    client = FakeClient(api_error(openai.RateLimitError, "slow down", status=429), completion("ok"))
    assert make_provider(client).generate(PROMPT, "ky") == "ok"
    assert len(client.calls) == 2


def test_rate_limit_user_message_when_retries_exhausted() -> None:
    client = FakeClient(*[api_error(openai.RateLimitError, "slow down", status=429)] * 2)
    with pytest.raises(LLMServiceError) as raised:
        make_provider(client).generate(PROMPT, "ky")
    assert raised.value.kind == "rate_limit"
    assert "busy" in raised.value.message


def test_empty_answer_due_to_token_limit_is_reported() -> None:
    client = FakeClient(completion(None, finish_reason="length"))
    with pytest.raises(LLMServiceError) as raised:
        make_provider(client).generate(PROMPT, "ky")
    assert raised.value.kind == "empty_response"


def test_truncated_answer_is_still_returned() -> None:
    client = FakeClient(completion("Partial answer", finish_reason="length"))
    assert make_provider(client).generate(PROMPT, "ky") == "Partial answer"


# ------------------------------------------------------------------ timeouts


def test_timeout_is_retried_once_within_budget() -> None:
    clock = FakeClock()
    client = FakeClient(slow_timeout(clock, 10), slow_timeout(clock, 10))
    with pytest.raises(LLMServiceError) as raised:
        make_provider(client, clock).generate(PROMPT, "ky")

    assert raised.value.kind == "timeout"
    assert "too long" in raised.value.message
    assert len(client.calls) == 2
    # Second attempt only gets what is left: 30 - 10 (first try) - 1 (backoff).
    assert client.calls[0]["timeout"] == pytest.approx(30.0)
    assert client.calls[1]["timeout"] == pytest.approx(19.0)


def test_timeout_consuming_whole_budget_is_not_retried() -> None:
    clock = FakeClock()
    client = FakeClient(slow_timeout(clock), completion("never reached"))
    with pytest.raises(LLMServiceError) as raised:
        make_provider(client, clock, llm_max_retries=3).generate(PROMPT, "ky")

    assert raised.value.kind == "timeout"
    assert len(client.calls) == 1


def test_no_retry_when_too_little_time_is_left() -> None:
    clock = FakeClock()
    client = FakeClient(slow_timeout(clock, 27), completion("never reached"))
    with pytest.raises(LLMServiceError):
        make_provider(client, clock).generate(PROMPT, "ky")
    assert len(client.calls) == 1


def test_total_time_never_exceeds_budget() -> None:
    clock = FakeClock()
    start = clock.now
    client = FakeClient(*[slow_timeout(clock, 8)] * 4)
    with pytest.raises(LLMServiceError):
        make_provider(client, clock, llm_max_retries=3).generate(PROMPT, "ky")
    assert clock.now - start <= 30.0
    assert all(call["timeout"] > 0 for call in client.calls)


def test_retries_disabled() -> None:
    clock = FakeClock()
    client = FakeClient(slow_timeout(clock, 1), completion("never reached"))
    with pytest.raises(LLMServiceError):
        make_provider(client, clock, llm_max_retries=0).generate(PROMPT, "ky")
    assert len(client.calls) == 1


# ------------------------------------------------------------- API endpoints


def test_health_reports_mock_provider(client: TestClient) -> None:
    assert client.get("/health").json()["llm_provider"] == "mock"


def test_health_reports_openai_without_secrets(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAIProvider(make_settings(), client=FakeClient())
    monkeypatch.setattr("app.api.routes.health.get_llm_provider", lambda: provider)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["llm_provider"] == "openai"
    assert FAKE_KEY not in response.text
    assert "sk-" not in response.text


def test_chat_returns_safe_503_when_openai_fails(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    failing = api_error(openai.AuthenticationError, f"Incorrect API key provided: {FAKE_KEY}",
                        status=401, code="invalid_api_key")
    provider = make_provider(FakeClient(failing))
    monkeypatch.setattr("app.api.deps.get_llm_provider", lambda: provider)

    response = client.post("/chat", json={"message": "Башым ооруп жатат"})
    assert response.status_code == 503
    body = response.json()
    assert body == {"detail": LLMServiceError.message, "code": "llm_unavailable"}
    assert FAKE_KEY not in response.text


def test_chat_works_with_openai_provider(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = make_provider(FakeClient(completion("Качантан бери ооруп жатат?")))
    monkeypatch.setattr("app.api.deps.get_llm_provider", lambda: provider)

    response = client.post("/chat", json={"message": "Башым ооруп жатат"})
    assert response.status_code == 200
    assert response.json()["answer"].startswith("Качантан бери")


# ------------------------------------ empty OPENAI_BASE_URL (503 regression)


def test_empty_base_url_env_uses_official_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    # `.env` line "OPENAI_BASE_URL=" is loaded by load_dotenv as "". With base_url=None
    # the SDK would read that "" and every request failed with APIConnectionError -> 503.
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    provider = OpenAIProvider(make_settings(openai_base_url=None))
    assert str(provider._client.base_url).startswith("https://api.openai.com/v1")


def test_custom_base_url_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    provider = OpenAIProvider(make_settings(openai_base_url="http://localhost:11434/v1"))
    assert str(provider._client.base_url).startswith("http://localhost:11434/v1")


def test_empty_base_url_env_is_not_set_in_settings(monkeypatch: pytest.MonkeyPatch, fresh_settings: None) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    assert get_settings().openai_base_url is None
