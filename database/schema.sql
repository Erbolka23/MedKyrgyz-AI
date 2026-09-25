-- ============================================================
-- MedKyrgyz AI — SQLite schema (reference)
--
-- The backend creates these tables automatically on start-up
-- (SQLAlchemy `Base.metadata.create_all`). This file documents the
-- schema and can be used to create the database manually:
--
--     sqlite3 database/medkyrgyz.db < database/schema.sql
--
-- Source of truth: backend/app/models/conversation.py
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS conversations (
    id          VARCHAR(36) PRIMARY KEY,           -- UUID4
    language    VARCHAR(2)  NOT NULL,              -- 'ky' | 'ru' (last used)
    created_at  DATETIME,
    updated_at  DATETIME
);

CREATE TABLE IF NOT EXISTS messages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id  VARCHAR(36) NOT NULL
                     REFERENCES conversations (id) ON DELETE CASCADE,
    role             VARCHAR(9)  NOT NULL CHECK (role IN ('user', 'assistant')),
    content          TEXT        NOT NULL,
    language         VARCHAR(2)  NOT NULL,
    is_emergency     BOOLEAN     NOT NULL DEFAULT 0,
    created_at       DATETIME
);

CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages (conversation_id);

-- Useful queries ------------------------------------------------------------
-- Emergency statistics:
--   SELECT language, COUNT(*) FROM messages
--   WHERE role = 'user' AND is_emergency = 1 GROUP BY language;
--
-- Conversation transcript:
--   SELECT role, content, created_at FROM messages
--   WHERE conversation_id = ? ORDER BY id;
