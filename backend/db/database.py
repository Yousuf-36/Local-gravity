"""
db/database.py — aiosqlite connection manager and schema migration runner.

Usage (from main.py lifespan):
    async with open_db(settings.db_path) as db:
        await run_migrations(db)
        app.state.db = db
        registry.set_db(db)
        await registry.load_from_db()
        yield

Schema (v1):
  agent_tasks         — persistent record of every AgentTask spawned
  conversation_history — per-task message history (role / content pairs)

Security:
  - All writes use parameterised queries (? placeholders). No f-string SQL.
  - DB file created in ~/.localgravity/ (user-owned directory).
  - WAL mode enabled for safe concurrent reads during streaming.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

log = logging.getLogger("localgravity.db")

# ── DDL ───────────────────────────────────────────────────────────────────────

_CREATE_AGENT_TASKS = """
CREATE TABLE IF NOT EXISTS agent_tasks (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL,
    description TEXT NOT NULL,
    model       TEXT NOT NULL,
    workspace   TEXT NOT NULL,
    artifacts   TEXT NOT NULL DEFAULT '[]',
    log_path    TEXT NOT NULL DEFAULT '',
    error       TEXT
);
"""

_CREATE_CONVERSATION_HISTORY = """
CREATE TABLE IF NOT EXISTS conversation_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    TEXT    NOT NULL,
    role       TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    FOREIGN KEY (task_id) REFERENCES agent_tasks (id) ON DELETE CASCADE
);
"""

_CREATE_HISTORY_IDX = """
CREATE INDEX IF NOT EXISTS idx_conv_task_id ON conversation_history (task_id);
"""

_MIGRATIONS: list[str] = [
    _CREATE_AGENT_TASKS,
    _CREATE_CONVERSATION_HISTORY,
    _CREATE_HISTORY_IDX,
]


# ── Connection manager ────────────────────────────────────────────────────────


@asynccontextmanager
async def open_db(db_path: str) -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Open an aiosqlite connection to the given path, enable WAL mode, and yield it.

    Creates the parent directory if it does not exist.

    Args:
        db_path: Absolute path to the SQLite database file.

    Yields:
        An open aiosqlite.Connection.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(db_path)
    try:
        # Row factory so columns are accessible by name
        db.row_factory = aiosqlite.Row
        # WAL mode: safe concurrent reads while the executor writes
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        yield db
    finally:
        await db.close()
        log.info("DB connection closed.")


# ── Migration runner ──────────────────────────────────────────────────────────


async def run_migrations(db: aiosqlite.Connection) -> None:
    """
    Execute all DDL migrations idempotently (CREATE IF NOT EXISTS).

    Args:
        db: An open aiosqlite connection.
    """
    for stmt in _MIGRATIONS:
        await db.execute(stmt)
    await db.commit()
    log.info("DB migrations applied.")


# ── Agent task helpers ────────────────────────────────────────────────────────


async def db_insert_task(db: aiosqlite.Connection, task_row: dict) -> None:
    """
    Insert a new agent task row.

    Args:
        db:       Open aiosqlite connection.
        task_row: Dict with keys matching the agent_tasks columns.
    """
    await db.execute(
        """
        INSERT OR IGNORE INTO agent_tasks
            (id, created_at, status, description, model, workspace, artifacts, log_path, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_row["id"],
            task_row["created_at"],
            task_row["status"],
            task_row["description"],
            task_row["model"],
            task_row["workspace"],
            json.dumps(task_row.get("artifacts", [])),
            task_row.get("log_path", ""),
            task_row.get("error"),
        ),
    )
    await db.commit()


async def db_update_task_status(
    db: aiosqlite.Connection,
    task_id: str,
    status: str,
    error: str | None = None,
) -> None:
    """
    Update the status (and optionally error) of a task row.

    Args:
        db:      Open aiosqlite connection.
        task_id: The task's short UUID.
        status:  New AgentStatus string value.
        error:   Optional error message (written when status is 'error').
    """
    await db.execute(
        "UPDATE agent_tasks SET status = ?, error = ? WHERE id = ?",
        (status, error, task_id),
    )
    await db.commit()


async def db_load_all_tasks(db: aiosqlite.Connection) -> list[dict]:
    """
    Load all agent_tasks rows ordered by created_at DESC (most recent first).

    Returns at most 200 rows to avoid unbounded memory use after long operation.

    Args:
        db: Open aiosqlite connection.

    Returns:
        List of row dicts with all agent_tasks columns.
    """
    async with db.execute(
        "SELECT * FROM agent_tasks ORDER BY created_at DESC LIMIT 200"
    ) as cursor:
        rows = await cursor.fetchall()
    result: list[dict] = []
    for row in rows:
        d = dict(row)
        # Deserialise the JSON artifacts list
        try:
            d["artifacts"] = json.loads(d.get("artifacts", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["artifacts"] = []
        result.append(d)
    return result


# ── Conversation history helpers ──────────────────────────────────────────────


async def db_append_message(
    db: aiosqlite.Connection,
    task_id: str,
    role: str,
    content: str,
    created_at: str,
) -> None:
    """
    Append a conversation message for a task.

    Args:
        db:         Open aiosqlite connection.
        task_id:    The parent task id.
        role:       Message role: 'user', 'assistant', or 'tool'.
        content:    Message content string.
        created_at: ISO-8601 timestamp string.
    """
    await db.execute(
        """
        INSERT INTO conversation_history (task_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (task_id, role, content, created_at),
    )
    await db.commit()


async def db_load_history(
    db: aiosqlite.Connection,
    task_id: str,
    limit: int = 100,
) -> list[dict]:
    """
    Load conversation history for a task, oldest first.

    Args:
        db:      Open aiosqlite connection.
        task_id: The task whose history to load.
        limit:   Max messages to return (prevents unbounded context).

    Returns:
        List of dicts with keys: role, content, created_at.
    """
    async with db.execute(
        """
        SELECT role, content, created_at FROM conversation_history
        WHERE task_id = ?
        ORDER BY id ASC
        LIMIT ?
        """,
        (task_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]
