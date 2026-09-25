# MedKyrgyz AI — Backend

FastAPI service that answers medical questions in Kyrgyz and Russian with safety guards.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
uvicorn main:app --reload
```

- API: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs

Without `OPENAI_API_KEY` the server starts in **mock** mode (offline, rule-based answers) — enough for frontend development.

## Structure

```
backend/
├── main.py                     app factory, CORS, lifespan (DB init)
├── app/
│   ├── api/
│   │   ├── routes/chat.py      POST /chat, GET /conversations/{id}/messages
│   │   ├── routes/health.py    GET /health
│   │   ├── deps.py             builds ChatService per request
│   │   └── router.py
│   ├── core/
│   │   ├── config.py           Settings from .env
│   │   ├── exceptions.py       AppError hierarchy + JSON error handlers
│   │   ├── logging.py          logging setup (no medical content in logs!)
│   │   └── prompts.py          system prompt, disclaimers, emergency texts
│   ├── database/
│   │   ├── base.py             DeclarativeBase
│   │   ├── session.py          engine, get_db(), init_db()
│   │   └── repositories.py     ConversationRepository
│   ├── models/conversation.py  Conversation, Message
│   ├── schemas/                Pydantic request/response models (API contract)
│   └── services/
│       ├── chat_service.py     orchestration pipeline
│       ├── llm_service.py      LLMProvider, OpenAIProvider, MockProvider
│       ├── safety_service.py   EmergencyDetector, AnswerGuard
│       └── language_service.py ky/ru detection
└── tests/                      pytest (uses temp DB + mock LLM)
```

## Request pipeline

`validate → detect language → load conversation → emergency check → prompt → LLM → output guard → save → respond`

See [../architecture.md](../architecture.md) for details.

## Tests

```bash
pytest -q
```

## Common tasks

| Task | Where |
|------|-------|
| Change assistant behaviour | `app/core/prompts.py` |
| Add emergency keywords | `app/services/safety_service.py` + a case in `tests/test_safety.py` |
| Add another LLM vendor | new `LLMProvider` subclass in `app/services/llm_service.py`, select it in `create_llm_provider()` |
| Add an endpoint | new module in `app/api/routes/`, include it in `app/api/router.py` |
| Add a table | model in `app/models/`, export in `app/models/__init__.py`, update `database/schema.sql` |
