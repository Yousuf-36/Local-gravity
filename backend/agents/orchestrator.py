"""
agents/orchestrator.py — Agent lifecycle management with write-through persistence.

Agent state machine:
  IDLE → PLANNING → EXECUTING → VERIFYING → DONE
                       ↓                    ↓
                     ERROR ←───────────────┘
                       ↓
               WAITING_APPROVAL  (HITL gate — Phase 2)

Storage strategy (write-through cache):
  - An in-memory OrderedDict is the primary read source (O(1), synchronous).
  - Every mutation (spawn, update_status, kill) fires a background aiosqlite
    write via asyncio.get_running_loop().create_task() — non-blocking.
  - On application startup, load_from_db() populates the in-memory cache from
    the persisted store so tasks survive backend restarts.
  - Callers (routers) remain fully synchronous — no API change needed.

Public API (unchanged from Phase 1):
  registry.spawn(description, workspace, model) → AgentTask
  registry.get(agent_id)                        → AgentTask | None
  registry.list_all()                           → list[AgentTask]
  registry.update_status(agent_id, status, error)
  registry.kill(agent_id)

New Phase 2 methods:
  registry.set_db(db)        — called from lifespan after DB is open
  await registry.load_from_db() — called from lifespan after set_db
"""
import uuid
from collections import OrderedDict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import aiosqlite
from pydantic import BaseModel, model_validator

from db.database import (
    db_insert_task,
    db_load_all_tasks,
    db_update_task_status,
)
from logging_config import get_logger

log = get_logger("orchestrator")


# ── State machine ─────────────────────────────────────────────────────────────


class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    WAITING = "waiting_approval"
    DONE = "done"
    ERROR = "error"


# ── Data model ────────────────────────────────────────────────────────────────


class AgentTask(BaseModel):
    """Represents one agent task — stored in DB and held in memory."""

    id: str = ""
    created_at: Optional[datetime] = None
    status: AgentStatus = AgentStatus.IDLE
    description: str
    model: str = "llama3"
    workspace: str
    artifacts: list[str] = []
    log_path: str = ""
    error: Optional[str] = None

    @model_validator(mode="after")
    def set_defaults(self) -> "AgentTask":
        """Assign id and created_at on first creation if not provided."""
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if self.created_at is None:
            self.created_at = datetime.now()
        return self

    def to_db_row(self) -> dict:
        """Serialise to a flat dict suitable for db_insert_task()."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else datetime.now().isoformat(),
            "status": self.status.value,
            "description": self.description,
            "model": self.model,
            "workspace": self.workspace,
            "artifacts": self.artifacts,
            "log_path": self.log_path,
            "error": self.error,
        }


# ── Registry ──────────────────────────────────────────────────────────────────


class AgentRegistry:
    """
    Write-through cached registry of agent tasks.

    Reads hit the in-memory OrderedDict (fast, sync).
    Writes update memory first, then schedule a background DB persist
    via asyncio.create_task() — so callers never block on I/O.
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        self._agents: OrderedDict[str, AgentTask] = OrderedDict()
        self.max_concurrent = max_concurrent
        self._db: aiosqlite.Connection | None = None

    # ── DB integration ────────────────────────────────────────────────────────

    def set_db(self, db: aiosqlite.Connection) -> None:
        """
        Attach an open aiosqlite connection for background persistence.

        Must be called from the application lifespan before any requests
        are served so that spawned tasks are durably written.

        Args:
            db: Open aiosqlite connection managed by the lifespan context.
        """
        self._db = db

    async def load_from_db(self) -> None:
        """
        Populate the in-memory cache from persisted agent_tasks rows.

        Called once from the lifespan after the DB is open and migrations
        have run. Tasks already in memory are skipped (idempotent).
        """
        if self._db is None:
            log.warning("load_from_db called before set_db — skipping")
            return
        rows = await db_load_all_tasks(self._db)
        loaded = 0
        for row in rows:
            if row["id"] in self._agents:
                continue
            try:
                task = AgentTask(
                    id=row["id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    status=AgentStatus(row["status"]),
                    description=row["description"],
                    model=row["model"],
                    workspace=row["workspace"],
                    artifacts=row.get("artifacts", []),
                    log_path=row.get("log_path", ""),
                    error=row.get("error"),
                )
                self._agents[task.id] = task
                loaded += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("Skipping malformed task row id=%s: %s", row.get("id"), exc)
        log.info("Loaded %d tasks from DB into memory.", loaded)

    def _schedule_db_insert(self, task: AgentTask) -> None:
        """Fire-and-forget: persist a new task row to the DB."""
        if self._db is None:
            return
        try:
            import asyncio
            asyncio.get_running_loop().create_task(
                db_insert_task(self._db, task.to_db_row())
            )
        except RuntimeError:
            pass  # No running loop (e.g. unit tests)

    def _schedule_db_status_update(
        self, task_id: str, status: str, error: str | None
    ) -> None:
        """Fire-and-forget: update task status in the DB."""
        if self._db is None:
            return
        try:
            import asyncio
            asyncio.get_running_loop().create_task(
                db_update_task_status(self._db, task_id, status, error)
            )
        except RuntimeError:
            pass

    # ── Public API (sync — unchanged from Phase 1) ────────────────────────────

    def spawn(
        self,
        description: str,
        workspace: str,
        model: str = "llama3",
    ) -> AgentTask:
        """
        Spawn a new agent task and register it.

        Checks the concurrent task cap, inserts into memory, and schedules
        a background DB insert.

        Args:
            description: Short description of the task (first 80 chars of prompt).
            workspace:   Absolute path to the workspace root.
            model:       Ollama model name validated by the caller.

        Returns:
            The newly created AgentTask.

        Raises:
            RuntimeError: If the concurrent task cap is reached.
        """
        running = sum(
            1
            for a in self._agents.values()
            if a.status in (AgentStatus.PLANNING, AgentStatus.EXECUTING, AgentStatus.VERIFYING)
        )
        if running >= self.max_concurrent:
            raise RuntimeError(f"Max concurrent agents ({self.max_concurrent}) reached.")
        task = AgentTask(description=description, workspace=workspace, model=model)
        self._agents[task.id] = task
        self._schedule_db_insert(task)
        return task

    def get(self, agent_id: str) -> Optional[AgentTask]:
        """
        Return the task with the given id, or None if not found.

        Args:
            agent_id: The short UUID of the task.
        """
        return self._agents.get(agent_id)

    def list_all(self) -> list[AgentTask]:
        """Return all tasks in reverse insertion order (most recent first)."""
        return list(reversed(list(self._agents.values())))

    def update_status(
        self,
        agent_id: str,
        status: AgentStatus,
        error: str | None = None,
    ) -> None:
        """
        Update the in-memory status of a task and schedule a DB write.

        Args:
            agent_id: The task to update.
            status:   New AgentStatus value.
            error:    Optional error message (set when status is ERROR).
        """
        task = self._agents.get(agent_id)
        if task is None:
            return
        task.status = status
        if error:
            task.error = error
        self._schedule_db_status_update(agent_id, status.value, task.error)

    def kill(self, agent_id: str) -> None:
        """
        Mark a task as errored with 'Killed by user' and persist.

        Args:
            agent_id: The task to kill.
        """
        task = self._agents.get(agent_id)
        if task is None:
            return
        task.status = AgentStatus.ERROR
        task.error = "Killed by user"
        self._schedule_db_status_update(agent_id, AgentStatus.ERROR.value, task.error)


# ── Plan artifact helper (unchanged) ─────────────────────────────────────────


def generate_plan_artifact(task: AgentTask, plan_text: str, workspace: str) -> tuple[str, str]:
    """
    Generate a plan markdown artifact for the given task.

    Args:
        task:      The AgentTask this plan belongs to.
        plan_text: Markdown plan content from the model.
        workspace: Absolute workspace path (unused — reserved for future use).

    Returns:
        (artifact_path, content) tuple. The caller is responsible for writing the file.
    """
    slug = task.description[:20].replace(" ", "_").lower()
    rel_path = f"artifacts/plan_{task.id}_{slug}.md"
    content = f"""# Agent Plan — {task.id}

**Task**: {task.description}
**Model**: {task.model}
**Created**: {task.created_at.isoformat() if task.created_at else "unknown"}
**Status**: {task.status}

---

## Plan

{plan_text}

---

## Files to Modify
<!-- Agent will fill this in during PLANNING phase -->

## Security Considerations
<!-- Agent must list any terminal commands or file writes here -->

## Estimated Steps
<!-- Agent fills in step count -->
"""
    return rel_path, content


# ── Singleton registry used by all routers ────────────────────────────────────
registry = AgentRegistry()
