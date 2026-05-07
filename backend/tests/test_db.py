"""
test_db.py — Tests for db/database.py

Coverage:
  Migrations run without error on fresh db
  agent_tasks table exists after migration
  conversation_history table exists after migration
  Insert and retrieve an AgentTask
  Insert and retrieve a conversation message
  Task status update persists correctly
"""
import pytest
import pytest_asyncio
from datetime import datetime


# ── Migration and schema ──────────────────────────────────────────────────────

class TestMigrations:
    @pytest.mark.asyncio
    async def test_migrations_run_without_error(self, mock_db):
        """Migrations are idempotent — running them a second time must not raise."""
        from db.database import run_migrations
        # Second call — CREATE IF NOT EXISTS must be a no-op
        await run_migrations(mock_db)

    @pytest.mark.asyncio
    async def test_agent_tasks_table_exists(self, mock_db):
        """agent_tasks must be present after migrations."""
        async with mock_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_tasks'"
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None, "agent_tasks table was not created by migrations"

    @pytest.mark.asyncio
    async def test_conversation_history_table_exists(self, mock_db):
        """conversation_history must be present after migrations."""
        async with mock_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversation_history'"
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None, "conversation_history table was not created by migrations"


# ── CRUD — agent_tasks ────────────────────────────────────────────────────────

class TestAgentTaskCRUD:
    _TASK_ROW = {
        "id": "test1234",
        "created_at": datetime.now().isoformat(),
        "status": "idle",
        "description": "Unit test task",
        "model": "llama3",
        "workspace": "/tmp/test_workspace",
        "artifacts": [],
        "log_path": "",
        "error": None,
    }

    @pytest.mark.asyncio
    async def test_insert_and_retrieve_agent_task(self, mock_db):
        from db.database import db_insert_task, db_load_all_tasks

        await db_insert_task(mock_db, self._TASK_ROW)
        rows = await db_load_all_tasks(mock_db)

        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "test1234"
        assert row["description"] == "Unit test task"
        assert row["model"] == "llama3"
        assert row["status"] == "idle"

    @pytest.mark.asyncio
    async def test_task_status_update_persists(self, mock_db):
        from db.database import db_insert_task, db_update_task_status, db_load_all_tasks

        await db_insert_task(mock_db, self._TASK_ROW)
        await db_update_task_status(mock_db, "test1234", "executing", None)

        rows = await db_load_all_tasks(mock_db)
        assert rows[0]["status"] == "executing"

    @pytest.mark.asyncio
    async def test_task_error_persists_on_status_update(self, mock_db):
        from db.database import db_insert_task, db_update_task_status, db_load_all_tasks

        await db_insert_task(mock_db, self._TASK_ROW)
        await db_update_task_status(mock_db, "test1234", "error", "Something went wrong")

        rows = await db_load_all_tasks(mock_db)
        assert rows[0]["status"] == "error"
        assert rows[0]["error"] == "Something went wrong"


# ── CRUD — conversation_history ───────────────────────────────────────────────

class TestConversationHistoryCRUD:
    @pytest.mark.asyncio
    async def test_insert_and_retrieve_conversation_message(self, mock_db):
        from db.database import db_insert_task, db_append_message, db_load_history

        # Insert parent task first (FK constraint)
        await db_insert_task(mock_db, {
            "id": "task-conv",
            "created_at": datetime.now().isoformat(),
            "status": "idle",
            "description": "Conversation test",
            "model": "llama3",
            "workspace": "/tmp/ws",
            "artifacts": [],
            "log_path": "",
            "error": None,
        })

        await db_append_message(
            mock_db,
            task_id="task-conv",
            role="user",
            content="Hello agent",
            created_at=datetime.now().isoformat(),
        )

        messages = await db_load_history(mock_db, "task-conv")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello agent"

    @pytest.mark.asyncio
    async def test_multiple_messages_ordered_asc(self, mock_db):
        from db.database import db_insert_task, db_append_message, db_load_history

        await db_insert_task(mock_db, {
            "id": "task-order",
            "created_at": datetime.now().isoformat(),
            "status": "idle",
            "description": "Order test",
            "model": "llama3",
            "workspace": "/tmp/ws",
            "artifacts": [],
            "log_path": "",
            "error": None,
        })

        ts = datetime.now().isoformat()
        await db_append_message(mock_db, "task-order", "user", "First", ts)
        await db_append_message(mock_db, "task-order", "assistant", "Second", ts)
        await db_append_message(mock_db, "task-order", "user", "Third", ts)

        messages = await db_load_history(mock_db, "task-order")
        assert len(messages) == 3
        assert [m["content"] for m in messages] == ["First", "Second", "Third"]
