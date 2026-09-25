# MedKyrgyz AI — Architecture

## 1. System architecture

MedKyrgyz AI is a classic three-tier web application with an external AI provider.

```
┌──────────────────────────┐        HTTP/JSON         ┌──────────────────────────────────┐
│  Presentation tier       │  ─────────────────────▶  │  Application tier (FastAPI)      │
│  frontend/ (static)      │  ◀─────────────────────  │  backend/                        │
│  HTML · CSS · Vanilla JS │                          │                                  │
└──────────────────────────┘                          │   ┌──────────────┐   HTTPS       │
                                                      │   │ LLM provider │ ─────────▶ OpenAI /
                                                      │   └──────────────┘      compatible API
                                                      │          │                       │
                                                      │   ┌──────▼───────┐               │
                                                      │   │ SQLAlchemy   │               │
                                                      └───┴──────┬───────┴───────────────┘
                                                                 │
                                                      ┌──────────▼───────────┐
                                                      │ Data tier: SQLite    │
                                                      │ database/medkyrgyz.db│
                                                      └──────────────────────┘
```

### Backend layers (clean architecture)

Dependencies point **downwards only**. Upper layers know nothing about the implementation details of lower ones.

| Layer | Folder | Responsibility | Knows about |
|-------|--------|----------------|-------------|
| API | `app/api/` | HTTP routes, status codes, dependency injection | schemas, services |
| Schemas | `app/schemas/` | Public JSON contract (Pydantic) | — |
| Services | `app/services/` | Business logic: orchestration, safety, language, LLM | repositories, core |
| Repositories | `app/database/repositories.py` | Data access | models |
| Models | `app/models/` | Database tables (SQLAlchemy) | — |
| Core | `app/core/` | Config, logging, errors, prompts | — |

Key design decisions:

- **`LLMProvider` interface** — the chat service depends on an abstract provider, so OpenAI can be replaced by another vendor or a local Kyrgyz model by adding one class.
- **Safety outside the model** — emergency detection and the dosage guard are deterministic Python code, not only prompt instructions.
- **Repository pattern** — SQLite can be replaced by PostgreSQL by changing `DATABASE_URL`, with no code changes in services.
- **Mock provider** — the whole system runs offline for development, tests and demos.

---

## 2. Component diagram

```
                              ┌─────────────────────── frontend ────────────────────────┐
                              │  index.html                                              │
                              │    ├── config.js   (API_BASE_URL, limits)                │
                              │    ├── i18n.js     (ky / ru UI texts)                    │
                              │    ├── api.js      (fetch, timeout, ApiError) ◀─┐        │
                              │    └── app.js      (state, rendering, events) ──┘        │
                              └──────────────────────────┬───────────────────────────────┘
                                                         │ POST /chat
                                                         ▼
┌──────────────────────────────────────────── backend ─────────────────────────────────────────────┐
│ main.py ── create_app(): CORS, exception handlers, lifespan(init_db)                              │
│   │                                                                                               │
│   └── api/router.py                                                                               │
│         ├── routes/health.py      GET /health                                                     │
│         └── routes/chat.py        POST /chat, GET /conversations/{id}/messages                    │
│                 │ Depends(get_chat_service)  (api/deps.py)                                        │
│                 ▼                                                                                 │
│         services/chat_service.py ── ChatService                                                   │
│             ├── services/language_service.py   detect_language()                                 │
│             ├── services/safety_service.py     EmergencyDetector · AnswerGuard                    │
│             ├── services/llm_service.py        LLMProvider ◁── OpenAIProvider / MockProvider      │
│             ├── core/prompts.py                system prompt, disclaimers, emergency texts        │
│             └── database/repositories.py       ConversationRepository                             │
│                        └── models/conversation.py   Conversation 1──* Message                     │
│                                  └── database/session.py  engine, sessions ──▶ SQLite             │
│                                                                                                   │
│ core/config.py (Settings from .env) · core/logging.py · core/exceptions.py                        │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data flow — one message

```
User types "Башым ооруп жатат" and presses Enter
│
├─ app.js      : show user bubble, show typing animation, disable input
├─ api.js      : POST /chat {message, language:"ky", conversation_id}
│
▼ backend
├─ 1. Pydantic validates body (non-empty, ≤ 2000 chars)             ── 422 on failure
├─ 2. Language: explicit "ky"/"ru", or detect_language() for "auto"
├─ 3. Repository: load conversation by id, or create a new one
├─ 4. EmergencyDetector.check(message)
│      ├─ match  ──▶ answer = fixed emergency text (103 / 112) ─────────────┐
│      └─ no match                                                          │
├─ 5. Build prompt: system prompt + language rule + last N messages + new   │
├─ 6. LLMProvider.generate()                                  ── 503 on failure
├─ 7. AnswerGuard.sanitise(): dosage found → safe refusal text              │
├─ 8. Save user + assistant messages, commit  ◀─────────────────────────────┘
├─ 9. Log metadata only (lang, emergency, lengths) — never the text
└─ 10. Return {answer, conversation_id, language, is_emergency, disclaimer}
│
▼ frontend
├─ store conversation_id in sessionStorage
├─ hide typing, render assistant bubble (red style if is_emergency)
└─ on error: translated error banner + Retry button
```

---

## 4. API specification (summary)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat` | Send a message, get an answer |
| `GET` | `/conversations/{id}/messages` | Conversation history |
| `GET` | `/health` | Liveness + active LLM provider |
| `GET` | `/docs` | Swagger UI (auto-generated) |

`POST /chat`

```json
// request
{ "message": "Башым ооруп жатат", "language": "auto", "conversation_id": null }

// response 200
{
  "answer": "Качантан бери ооруп жатат?",
  "conversation_id": "3f1c2a8e-5b7d-4e0a-9c61-2d8f4b9e7a10",
  "language": "ky",
  "is_emergency": false,
  "disclaimer": "MedKyrgyz AI дарыгердин ордун баспайт: ..."
}

// error (any status)
{ "detail": "The AI service is temporarily unavailable. Please try again later.", "code": "llm_unavailable" }
```

Full specification: [docs/api.md](docs/api.md).

---

## 5. Data model

```
conversations                      messages
─────────────                      ────────
id          PK  UUID      1 ──── * id               PK
language        ky|ru              conversation_id  FK → conversations.id (CASCADE)
created_at                         role             user|assistant
updated_at                         content
                                   language         ky|ru
                                   is_emergency     bool
                                   created_at
```

---

## 6. Non-functional aspects

| Aspect | Current solution |
|--------|------------------|
| Security | API key only in `.env` (git-ignored); CORS whitelist; output rendered with `textContent` (no XSS) |
| Privacy | No personal identifiers stored; message text never logged |
| Reliability | LLM timeout + 2 retries; uniform error format; frontend Retry |
| Testability | Mock provider, temporary test DB, `pytest` suite (API, safety, language) |
| Maintainability | Layered structure, type hints, single source of truth for contract/config |
| Accessibility | Keyboard navigation, `aria-live` chat log, reduced-motion support, dark mode |

---

## 7. Future improvements

**AI quality**
- RAG over trusted sources (Ministry of Health of the Kyrgyz Republic, WHO) with citations in answers.
- Fine-tuned or specialised Kyrgyz language model; evaluation dataset of Kyrgyz medical Q&A.
- ML-based emergency and intent classifier in addition to keyword rules.
- Streaming answers (Server-Sent Events) for faster perceived response.

**Product**
- Voice input/output (Kyrgyz speech-to-text / text-to-speech).
- "Find the nearest clinic / ЦСМ" using a map API.
- Feedback buttons (👍/👎) on answers to build an evaluation set.
- Telegram / WhatsApp bot using the same backend API.

**Engineering**
- API versioning (`/api/v1`), rate limiting per IP, request IDs.
- Alembic migrations; PostgreSQL for production.
- Docker + docker-compose; CI (GitHub Actions) running `pytest` and linters (ruff, mypy).
- Admin dashboard: usage and emergency statistics (anonymised).
- User accounts (optional) with encrypted history and data-deletion on request.
