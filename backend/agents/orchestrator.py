"""
orchestrator.py — Agent lifecycle management.

Phase 1 uses an in-memory registry (OrderedDict). This is intentional —
no database dependency in the shell phase. A persistent store can be added later.

Agent state machine:
  IDLE → PLANNING → EXECUTING → VERIFYING → DONE
                        ↓                    ↓
                      ERROR ←───────────────┘
                        ↓
                  WAITING_APPROVAL  (review-driven mode, future)
"""
import uuid
from collections import OrderedDict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, model_validator


class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    WAITING = "waiting_approval"
    DONE = "done"
    ERROR = "error"


class AgentTask(BaseModel):
    id: str = ""
    created_at: Optional[datetime] = None
    status: AgentStatus = AgentStatus.IDLE
    description: str
    model: str = "gpt-oss:20b"
    workspace: str
    artifacts: list[str] = []
    log_path: str = ""
    error: Optional[str] = None

    @model_validator(mode="after")
    def set_defaults(self) -> "AgentTask":
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if self.created_at is None:
            self.created_at = datetime.now()
        return self


class AgentRegistry:
    """In-memory registry of agent tasks with a concurrency cap."""

    def __init__(self, max_concurrent: int = 5) -> None:
        self._agents: OrderedDict[str, AgentTask] = OrderedDict()
        self.max_concurrent = max_concurrent

    def spawn(self, description: str, workspace: str, model: str = "gpt-oss:20b") -> AgentTask:
        running = sum(
            1 for a in self._agents.values()
            if a.status in (AgentStatus.PLANNING, AgentStatus.EXECUTING, AgentStatus.VERIFYING)
        )
        if running >= self.max_concurrent:
            raise RuntimeError(f"Max concurrent agents ({self.max_concurrent}) reached.")
        task = AgentTask(description=description, workspace=workspace, model=model)
        self._agents[task.id] = task
        return task

    def get(self, agent_id: str) -> Optional[AgentTask]:
        return self._agents.get(agent_id)

    def list_all(self) -> list[AgentTask]:
        return list(self._agents.values())

    def update_status(self, agent_id: str, status: AgentStatus, error: str | None = None) -> None:
        if task := self._agents.get(agent_id):
            task.status = status
            if error:
                task.error = error

    def kill(self, agent_id: str) -> None:
        if task := self._agents.get(agent_id):
            task.status = AgentStatus.ERROR
            task.error = "Killed by user"


def generate_plan_artifact(task: AgentTask, plan_text: str, workspace: str) -> tuple[str, str]:
    """
    Generate a plan markdown artifact for the given task.

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
