# Developer workflow — two students, working in parallel

The project is split along one clear boundary: **the HTTP API**.
Neither side needs the other to be finished to make progress.

```
 Student 2 (Frontend)                       Student 1 (Backend)
 ────────────────────                       ───────────────────
 frontend/index.html                        backend/main.py
 frontend/css/style.css      ┌──────────┐   backend/app/api/        (routes)
 frontend/js/app.js   ──────▶│ API      │◀──backend/app/services/   (AI, safety)
 frontend/js/i18n.js         │ CONTRACT │   backend/app/models/     (DB tables)
 frontend/js/api.js   ◀──────│docs/api.md│  backend/app/schemas/    (contract)
 frontend/assets/            └──────────┘   database/
```

## Ownership

| Area | Student 1 — Backend / AI / DB | Student 2 — Frontend / UI / UX |
|------|:---:|:---:|
| `backend/**` | **owner** | reviewer |
| `database/**` | **owner** | — |
| `frontend/**` | reviewer | **owner** |
| `docs/api.md` (contract) | co-owner | co-owner |
| `docs/safety-policy.md`, prompts texts | **owner** | reviews Kyrgyz/Russian wording |
| `README.md`, `architecture.md` | shared | shared |

### Student 1 — Backend

- FastAPI endpoints (`app/api/routes/`)
- LLM integration and prompt engineering (`app/services/llm_service.py`, `app/core/prompts.py`)
- Safety layer: emergency detection, output guard (`app/services/safety_service.py`)
- Language detection (`app/services/language_service.py`)
- Database models and repositories (`app/models/`, `app/database/`)
- Tests (`backend/tests/`)

### Student 2 — Frontend

- Layout, styles, responsiveness, dark mode (`css/style.css`)
- Chat behaviour: messages, typing animation, errors, retry (`js/app.js`)
- Kyrgyz/Russian UI texts (`js/i18n.js`)
- Backend client (`js/api.js`)
- Accessibility (keyboard, screen readers, contrast) and usability testing with real users

## Integration points

There are exactly **four**:

| # | Integration point | Backend file | Frontend file |
|---|-------------------|--------------|---------------|
| 1 | Request/response JSON of `POST /chat` | `app/schemas/chat.py` | `js/api.js → sendMessage()` |
| 2 | Error format `{detail, code}` + HTTP status | `app/core/exceptions.py` | `js/api.js → kindFromStatus()` |
| 3 | Backend URL and CORS origins | `.env → CORS_ORIGINS` | `js/config.js → API_BASE_URL` |
| 4 | Limits: max message length (2000) | `schemas/chat.py → MAX_MESSAGE_LENGTH` | `config.js → MAX_MESSAGE_LENGTH`, `maxlength` in `index.html` |

Everything else can change freely without telling the other person.

## How to work without waiting for each other

**Frontend without a finished backend:** run the backend with `LLM_PROVIDER=mock`. It needs no API key and returns realistic answers (including the spec example `Башым ооруп жатат → Качантан бери ооруп жатат?`) and real emergency responses. Use `/docs` to see the contract.

**Backend without a frontend:** use Swagger UI at `http://127.0.0.1:8000/docs`, `curl`, and `pytest`.

## Git workflow

```
main          ← always runnable, protected
 ├─ feature/backend-<topic>     (Student 1)
 └─ feature/frontend-<topic>    (Student 2)
```

1. Create a branch per feature: `feature/backend-history-endpoint`, `feature/frontend-dark-mode`.
2. Small commits with clear messages: `backend: add emergency keywords for stroke (ky)`.
3. Open a pull request; the **other** student reviews it (knowledge sharing + second pair of eyes).
4. Before merging: backend → `pytest` passes; frontend → manually tested in Chrome + mobile view.
5. Contract changes (`docs/api.md`) → one PR that changes both sides.

## Suggested timeline (8 weeks)

| Week | Student 1 (Backend) | Student 2 (Frontend) | Together |
|------|---------------------|----------------------|----------|
| 1 | Environment, FastAPI skeleton, `/health` | Wireframes, colour palette, HTML layout | Agree on API contract |
| 2 | `/chat` with mock provider, DB models | Chat UI, message rendering | First integration test |
| 3 | OpenAI integration, system prompt | Loading animation, error handling | — |
| 4 | Emergency detector, output guard | Language selector, i18n | Review safety texts in ky/ru |
| 5 | Language detection, conversation history | Mobile layout, accessibility | — |
| 6 | Tests, logging, error handling | Chat restore after reload, polish | Usability test with 5+ users |
| 7 | Prompt tuning from user feedback | UI fixes from user feedback | Bug fixing |
| 8 | Documentation | Documentation, screenshots | Presentation & demo |

## Definition of done (for any task)

- [ ] Works in both Kyrgyz and Russian
- [ ] Errors are handled and shown to the user
- [ ] No medical content in logs
- [ ] Tests pass (`pytest`) / checked in browser (desktop + mobile)
- [ ] Docs updated if behaviour or contract changed
