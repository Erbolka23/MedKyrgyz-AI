# MedKyrgyz AI
### Кыргыз тилиндеги интеллектуалдык медициналык жардамчы

A web-based AI medical **information** assistant for Kyrgyz and Russian speakers.
It explains health topics in simple language, asks clarifying questions, recommends a doctor when appropriate, and immediately warns about emergency symptoms.

> ⚠️ MedKyrgyz AI **does not diagnose** and **does not prescribe medication**. It is a university project, not a medical device.

---

## Features

| | |
|---|---|
| 🗣 **Bilingual** | Kyrgyz and Russian; automatic language detection |
| 🩺 **Safe by design** | No diagnoses, no prescriptions — enforced by prompt **and** an output guard |
| 🚨 **Emergency detection** | Life-threatening symptoms → instant warning with **103 / 112**, without waiting for the AI |
| 💬 **Conversation memory** | Follow-up questions keep context; chat restored after page reload |
| 🔌 **Pluggable AI** | OpenAI or any OpenAI-compatible API; offline mock mode for development |
| 📱 **Responsive UI** | Works on phones and desktops, light & dark mode |

---

## Folder structure

```
MedKyrgyz AI/
├── backend/                     FastAPI application (Student 1)
│   ├── app/
│   │   ├── api/                 HTTP layer: routes + dependency wiring
│   │   │   ├── routes/          chat.py, health.py
│   │   │   ├── deps.py
│   │   │   └── router.py
│   │   ├── core/                config, logging, exceptions, prompts
│   │   ├── database/            engine/session, repositories
│   │   ├── models/              SQLAlchemy tables
│   │   ├── schemas/             Pydantic API contract
│   │   └── services/            chat orchestration, LLM, safety, language
│   ├── tests/                   pytest suite
│   ├── main.py                  application entry point
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── frontend/                    Static web client (Student 2)
│   ├── index.html
│   ├── css/style.css
│   ├── js/
│   │   ├── config.js            backend URL & limits
│   │   ├── i18n.js              Kyrgyz / Russian UI texts
│   │   ├── api.js               backend client (integration point)
│   │   └── app.js               chat UI controller
│   └── assets/                  logo, favicon
├── database/                    SQLite file (git-ignored) + schema.sql
├── docs/
│   ├── api.md                   API contract
│   ├── developer-workflow.md    team process & integration points
│   └── safety-policy.md         medical safety rules
├── architecture.md              system design
├── README.md
└── .gitignore
```

---

## Installation

### Requirements
- Python **3.12+**
- A modern browser
- (optional) an OpenAI API key — without it the backend runs in offline **mock** mode

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
# edit .env → OPENAI_API_KEY=sk-...
```

### 2. Frontend

No build step. It is plain HTML/CSS/JS.

---

## How to run locally

**Terminal 1 — backend**

```bash
cd backend
uvicorn main:app --reload
# → http://127.0.0.1:8000        API
# → http://127.0.0.1:8000/docs   Swagger UI
```

**Terminal 2 — frontend**

```bash
cd frontend
python -m http.server 5500
# → open http://localhost:5500
```

> Serve the frontend over HTTP (as above or with VS Code *Live Server*) rather than opening `index.html` as a file, so that CORS works.

**Tests**

```bash
cd backend
pytest
```

**Quick API check**

```bash
curl -X POST http://127.0.0.1:8000/chat \
     -H "Content-Type: application/json" \
     -d "{\"message\": \"Башым ооруп жатат\"}"
```

---

## How the frontend communicates with the backend

```
Browser (frontend/js/api.js)                 FastAPI (backend)
──────────────────────────                   ─────────────────
POST /chat  {message, language, conversation_id?}  ──▶  validate (Pydantic)
                                                        detect language
                                                        emergency check ──▶ fixed 103/112 answer
                                                        LLM call + output guard
            {answer, conversation_id, language,  ◀──    save to SQLite
             is_emergency, disclaimer}
```

- Transport: JSON over HTTP, `fetch()` with a 45 s timeout.
- The backend URL is configured in `frontend/js/config.js`; allowed origins in `backend/.env → CORS_ORIGINS`.
- `conversation_id` is kept in `sessionStorage` and sent with each message so the AI remembers context.
- Errors always come as `{detail, code}` with an HTTP status; the UI shows a translated message and a **Retry** button.

Full contract: [docs/api.md](docs/api.md).

---

## Team responsibilities

| Student 1 — Backend & AI | Student 2 — Frontend & UX |
|---|---|
| FastAPI endpoints | Page layout, visual design |
| OpenAI integration, prompt engineering | Chat window, message rendering |
| Emergency detection & output guard | Loading animation, error handling |
| Language detection | Language selector, Kyrgyz/Russian UI texts |
| SQLite models, repositories | Responsive / mobile layout, accessibility |
| Backend tests | Usability testing |

Both: API contract, safety wording review, documentation, final presentation.
Details, integration points and Git workflow: [docs/developer-workflow.md](docs/developer-workflow.md).

---

## Configuration

All backend settings are in `backend/.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | API key; empty → mock mode |
| `LLM_PROVIDER` | `auto` | `auto` \| `openai` \| `mock` |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |
| `OPENAI_BASE_URL` | — | Any OpenAI-compatible endpoint |
| `DATABASE_URL` | `sqlite:///database/medkyrgyz.db` | Relative to project root |
| `CORS_ORIGINS` | localhost:5500, :3000 | Allowed frontend origins |
| `DEFAULT_LANGUAGE` | `ky` | Used when detection is unsure |
| `HISTORY_LIMIT` | `10` | Previous messages sent as context |

---

## Documentation

- [architecture.md](architecture.md) — system architecture, component diagram, data flow, future work
- [docs/api.md](docs/api.md) — API specification
- [docs/safety-policy.md](docs/safety-policy.md) — medical safety rules
- [docs/developer-workflow.md](docs/developer-workflow.md) — how the team works
