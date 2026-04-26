"""
agents/approval_store.py — HITL approval gate for destructive tool calls.

The executor pauses on an asyncio.Event for every destructive tool call.
The approve/deny HTTP endpoints set the event and record the decision.

Design:
  - (task_id, call_id) is the compound key.
  - call_id is a UUID4 scoped to exactly one tool call.
  - Events are one-shot: resolved entries are removed after consume().
  - cancel_all_for_task() is called by kill_agent to unblock waiting loops.

Thread safety:
  - All dict operations run on the asyncio event loop thread.
  - asyncio.Event is safe when created and awaited on the same loop.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Literal

ApprovalDecision = Literal["approved", "denied", "pending"]


@dataclass
class _ApprovalEntry:
    """Internal state for one pending tool-call approval."""

    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: ApprovalDecision = "pending"


class ApprovalStore:
    """
    Manages asyncio.Event pairs for the HITL approval gate.

    Executor side::

        entry = approval_store.create(task_id, call_id)
        await entry.event.wait()
        decision = approval_store.consume(task_id, call_id)

    HTTP endpoint side::

        approval_store.approve(task_id, call_id)
    """

    def __init__(self) -> None:
        self._pending: dict[tuple[str, str], _ApprovalEntry] = {}

    def create(self, task_id: str, call_id: str) -> _ApprovalEntry:
        """
        Create and store a new pending approval entry.

        Args:
            task_id: The agent task id (short UUID).
            call_id: UUID4 scoped to this specific tool call.

        Returns:
            The new _ApprovalEntry. Caller should ``await entry.event.wait()``.

        Raises:
            RuntimeError: If an entry for (task_id, call_id) already exists.
        """
        key = (task_id, call_id)
        if key in self._pending:
            raise RuntimeError(
                f"Approval entry for ({task_id}, {call_id}) already exists."
            )
        entry = _ApprovalEntry()
        self._pending[key] = entry
        return entry

    def approve(self, task_id: str, call_id: str) -> bool:
        """
        Mark a pending tool call as approved and unblock the executor.

        Args:
            task_id: The agent task id.
            call_id: The specific tool call id.

        Returns:
            True if the entry existed and was resolved. False if not found.
        """
        return self._resolve(task_id, call_id, "approved")

    def deny(self, task_id: str, call_id: str) -> bool:
        """
        Mark a pending tool call as denied and unblock the executor.

        Args:
            task_id: The agent task id.
            call_id: The specific tool call id.

        Returns:
            True if the entry existed and was resolved. False if not found.
        """
        return self._resolve(task_id, call_id, "denied")

    def consume(self, task_id: str, call_id: str) -> ApprovalDecision:
        """
        Read and remove the decision for a resolved entry.

        Should be called by the executor immediately after ``event.wait()``
        returns. Removes the entry to prevent memory leaks.

        Args:
            task_id: The agent task id.
            call_id: The specific tool call id.

        Returns:
            The decision: ``"approved"``, ``"denied"``, or ``"pending"`` if
            the entry was not found (should not happen in normal flow).
        """
        entry = self._pending.pop((task_id, call_id), None)
        if entry is None:
            return "pending"
        return entry.decision

    def cancel_all_for_task(self, task_id: str) -> int:
        """
        Deny and remove all pending approvals for a given task.

        Called when a task is killed to unblock any waiting executor loops.

        Args:
            task_id: The task whose pending approvals should be cancelled.

        Returns:
            Number of entries cancelled.
        """
        to_cancel = [k for k in self._pending if k[0] == task_id]
        for key in to_cancel:
            entry = self._pending.pop(key)
            entry.decision = "denied"
            entry.event.set()
        return len(to_cancel)

    def _resolve(
        self, task_id: str, call_id: str, decision: ApprovalDecision
    ) -> bool:
        """Set the decision and fire the event for a pending entry."""
        entry = self._pending.get((task_id, call_id))
        if entry is None:
            return False
        entry.decision = decision
        entry.event.set()
        return True


# ── Singleton ─────────────────────────────────────────────────────────────────

approval_store = ApprovalStore()
