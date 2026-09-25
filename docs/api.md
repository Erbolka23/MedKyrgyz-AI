# API specification

Base URL (local): `http://127.0.0.1:8000`
Interactive docs: `http://127.0.0.1:8000/docs` (Swagger UI) · `http://127.0.0.1:8000/redoc`

All requests and responses use `application/json; charset=utf-8`.

---

## `POST /chat`

Send a user question, receive the assistant's answer.

### Request

| Field | Type | Required | Description |
|-------|------|:---:|-------------|
| `message` | string (1–2000 chars) | ✅ | User's question. Leading/trailing spaces are trimmed. |
| `language` | `"ky"` \| `"ru"` \| `"auto"` | — | Answer language. Default `auto` (detected from the message). |
| `conversation_id` | string (UUID) | — | From a previous response. Omit to start a new conversation. |

Minimal request (as in the project specification):

```json
{ "message": "Башым ооруп жатат" }
```

Full request:

```json
{
  "message": "Эки күндөн бери",
  "language": "ky",
  "conversation_id": "3f1c2a8e-5b7d-4e0a-9c61-2d8f4b9e7a10"
}
```

### Response `200 OK`

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Assistant's answer (plain text, may contain `\n`). |
| `conversation_id` | string | Send it back with the next message to keep context. |
| `language` | `"ky"` \| `"ru"` | Language of the answer. |
| `is_emergency` | boolean | `true` if emergency symptoms were detected — the UI must highlight the answer. |
| `disclaimer` | string | Medical disclaimer in the answer language. |

```json
{
  "answer": "Качантан бери ооруп жатат?",
  "conversation_id": "3f1c2a8e-5b7d-4e0a-9c61-2d8f4b9e7a10",
  "language": "ky",
  "is_emergency": false,
  "disclaimer": "MedKyrgyz AI дарыгердин ордун баспайт: диагноз койбойт жана дары жазып бербейт. ..."
}
```

Emergency example (`"message": "Дем ала албай жатам"`):

```json
{
  "answer": "⚠️ Сиз сүрөттөгөн белгилер өмүргө коркунуч туудурушу мүмкүн.\n\nДароо тез жардамга чалыңыз: 103 же 112. ...",
  "language": "ky",
  "is_emergency": true,
  "...": "..."
}
```

---

## `GET /conversations/{conversation_id}/messages`

Return the full history of a conversation (used by the frontend to restore the chat after a page reload).

```json
{
  "conversation_id": "3f1c2a8e-...",
  "messages": [
    { "role": "user", "content": "Башым ооруп жатат", "language": "ky", "is_emergency": false, "created_at": "2026-09-25T10:00:00Z" },
    { "role": "assistant", "content": "Качантан бери ооруп жатат?", "language": "ky", "is_emergency": false, "created_at": "2026-09-25T10:00:01Z" }
  ]
}
```

---

## `GET /health`

```json
{ "status": "ok", "version": "0.1.0", "llm_provider": "openai" }
```

`llm_provider` is `mock` when the backend runs without an API key.

---

## Errors

Every error has the same shape:

```json
{ "detail": "message: message must not be empty", "code": "validation_error" }
```

| HTTP | `code` | When | Frontend behaviour |
|------|--------|------|--------------------|
| 422 | `validation_error` | Empty/too long message, wrong `language` | "Invalid message" text |
| 404 | `conversation_not_found` | Unknown id in `/conversations/...` | Start a new chat silently |
| 503 | `llm_unavailable` | LLM provider down / timeout / bad key | "AI temporarily unavailable" + Retry |
| 500 | `internal_error` | Unexpected server error | "Server error" + Retry |
| — | (network) | Backend not running / CORS | "No connection" + Retry |

---

## Contract change rules

The contract is defined in `backend/app/schemas/chat.py` and consumed in `frontend/js/api.js`.

- **Adding** an optional response field → backwards-compatible, backend may ship first.
- **Renaming/removing** a field or changing a type → both students agree first, update this file, change both sides in one pull request.
