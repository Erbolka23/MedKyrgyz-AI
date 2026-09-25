# Medical safety policy

MedKyrgyz AI is an **information** assistant. It is not a medical device and does not replace a doctor.

## Rules

| # | Rule | How it is enforced |
|---|------|--------------------|
| 1 | Never give a diagnosis | System prompt (`backend/app/core/prompts.py`) |
| 2 | Never prescribe medication or dosages | System prompt **+** output guard `AnswerGuard` — answers containing dosages (`500 мг`, `2 таблетки`, …) are replaced with a safe refusal |
| 3 | Recommend a doctor when appropriate | System prompt |
| 4 | Detect emergencies and warn | Input guard `EmergencyDetector` — runs **before** the LLM. On a match the backend returns a fixed, reviewed message with **103 / 112** and the LLM is not called |
| 5 | Only health topics | System prompt |
| 6 | Always visible disclaimer | `disclaimer` field in every response, footer and emergency strip in the UI |

## Why emergencies bypass the LLM

- **Speed** — the warning is instant, even if the AI provider is slow or down.
- **Reliability** — the text cannot be altered, shortened or hallucinated by the model.
- **Auditability** — the message is reviewed once and stored in code.

Keyword lists live in `backend/app/services/safety_service.py`. They are intentionally broad: a false alarm is much cheaper than a missed emergency.

## Emergency numbers (Kyrgyz Republic)

| Number | Service |
|--------|---------|
| **103** | Ambulance (Тез жардам / Скорая помощь) |
| **112** | Unified emergency service |

## Privacy

- Message contents are **never written to logs** — only metadata (length, language, emergency flag).
- No names, phone numbers or IP addresses are stored in the database.
- The OpenAI API key lives only in `backend/.env`, which is git-ignored.

## Changing the safety rules

Any change to prompts, keyword lists or fixed messages must:

1. Be reviewed by both team members.
2. Keep `backend/tests/test_safety.py` passing, with new cases for new keywords.
3. Be tested manually in **both** Kyrgyz and Russian.
