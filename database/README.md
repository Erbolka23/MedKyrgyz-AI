# database/

Storage for the SQLite database used by the backend.

| File | Tracked in git | Purpose |
|------|:---:|---------|
| `schema.sql` | ✅ | Reference schema (mirrors `backend/app/models/conversation.py`) |
| `medkyrgyz.db` | ❌ | Created automatically on first backend start |

## Tables

```
conversations 1 ──── * messages
```

- **conversations** — one row per browser chat session (`id` is a UUID returned to the frontend as `conversation_id`).
- **messages** — every user question and assistant answer, with the detected language and an `is_emergency` flag.

No personal identifiers (names, phone numbers, IP addresses) are stored.

## Common tasks

```bash
# Reset the database (the backend recreates it on next start)
rm database/medkyrgyz.db

# Inspect
sqlite3 database/medkyrgyz.db ".tables"
sqlite3 database/medkyrgyz.db "SELECT role, substr(content,1,60) FROM messages ORDER BY id DESC LIMIT 10;"
```

## Changing the schema

1. Edit the model in `backend/app/models/`.
2. Update `schema.sql` to match.
3. During development, delete `medkyrgyz.db` to recreate it.
   For a real deployment, introduce Alembic migrations (see `architecture.md → Future improvements`).
