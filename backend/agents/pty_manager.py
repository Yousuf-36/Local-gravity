"""
agents/pty_manager.py — Per-workspace terminal session manager.

Phase 2 implementation: stateless create_subprocess_exec with per-workspace
working directory (cwd) tracking. Each "session" is a lightweight record that
remembers the current working directory between command invocations, making
``cd`` semantics work across sequential tool calls within the same task.

TODO(Phase 3): Replace stateless exec with persistent PTY using pywinpty
  (Windows) or asyncio.openpty (POSIX). This would give the agent a real
  interactive shell — readline, environment variables, background processes.
  See: https://pypi.org/project/pywinpty/
  Blocked on: adding pywinpty to requirements.txt and testing on Windows.

Sessions expire after settings.pty_idle_timeout_seconds of inactivity and
are cleaned up by _reap_idle_sessions() called on every access.

Thread safety:
  All access to _sessions is from the asyncio event loop thread.
"""
import asyncio
import hashlib
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import settings
from security.terminal import safe_resolve, validate_command
from logging_config import get_logger

log = get_logger("pty_manager")


# ── Session data ──────────────────────────────────────────────────────────────


@dataclass
class PtySession:
    """
    Lightweight session record for one workspace.

    Attributes:
        workspace:    Absolute workspace root path (source of truth for
                      path validation via safe_resolve).
        working_dir:  Current working directory within the workspace.
                      Updated after each successful ``cd`` command.
        last_used_at: Unix timestamp of the last command execution.
                      Used for idle-timeout eviction.
        workspace_hash: Short hash used as the URL segment in the sessions API.
    """

    workspace: str
    working_dir: Path
    last_used_at: float = field(default_factory=time.monotonic)
    workspace_hash: str = ""

    def __post_init__(self) -> None:
        if not self.workspace_hash:
            self.workspace_hash = _hash_workspace(self.workspace)

    @property
    def is_idle(self) -> bool:
        """Return True if the session has exceeded the idle timeout."""
        elapsed = time.monotonic() - self.last_used_at
        return elapsed > settings.pty_idle_timeout_seconds

    def touch(self) -> None:
        """Update last_used_at to the current monotonic time."""
        self.last_used_at = time.monotonic()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _hash_workspace(workspace: str) -> str:
    """
    Return an 8-char hex hash of the workspace path for use as a URL segment.

    Args:
        workspace: Absolute workspace path string.

    Returns:
        8-character lowercase hex string.
    """
    return hashlib.md5(workspace.encode("utf-8")).hexdigest()[:8]


def _resolve_cd(session: PtySession, args: list[str]) -> Optional[Path]:
    """
    If the command is a bare ``cd <path>``, return the resolved target dir.

    Returns None if the command is not a ``cd``, or if the target does not
    resolve to a valid directory within the workspace.

    Args:
        session: The current PtySession (for workspace root).
        args:    Pre-split command parts.

    Returns:
        Resolved Path if this is a valid cd, else None.
    """
    if not args or args[0] != "cd":
        return None
    if len(args) < 2:
        # bare ``cd`` → return to workspace root
        return Path(session.workspace).resolve()
    target = args[1]
    try:
        # Resolve relative to current working_dir, then validate within workspace
        candidate = (session.working_dir / target).resolve()
        candidate.relative_to(Path(session.workspace).resolve())
        if candidate.is_dir():
            return candidate
    except (ValueError, OSError):
        pass
    return None


# ── Manager ───────────────────────────────────────────────────────────────────


class PtyManager:
    """
    Manages lightweight terminal sessions keyed by workspace path.

    Each session tracks the current working directory so that sequential
    tool calls can ``cd`` into subdirectories and have subsequent commands
    run there — without a persistent shell process.

    Public interface:
        get_or_create(workspace)    → PtySession
        execute(workspace, command) → (stdout, stderr, returncode)
        close(workspace)            → None
        list_sessions()             → list[PtySession]
    """

    def __init__(self) -> None:
        self._sessions: dict[str, PtySession] = {}

    def _reap_idle_sessions(self) -> int:
        """
        Remove sessions that have exceeded the idle timeout.

        Called on every public method to keep the session map clean without
        a background timer.

        Returns:
            Number of sessions reaped.
        """
        expired = [k for k, s in self._sessions.items() if s.is_idle]
        for k in expired:
            log.info("Reaping idle PTY session workspace_hash=%s", k)
            del self._sessions[k]
        return len(expired)

    def get_or_create(self, workspace: str) -> PtySession:
        """
        Return the existing session for a workspace, or create a new one.

        Also reaps idle sessions on every call.

        Args:
            workspace: Absolute workspace path.

        Returns:
            The active PtySession for this workspace.
        """
        self._reap_idle_sessions()
        key = _hash_workspace(workspace)
        if key not in self._sessions:
            log.info("Creating PTY session workspace_hash=%s", key)
            self._sessions[key] = PtySession(
                workspace=workspace,
                working_dir=Path(workspace).resolve(),
            )
        return self._sessions[key]

    async def execute(
        self, workspace: str, command: str
    ) -> tuple[str, str, int]:
        """
        Validate and execute a command in the session's working directory.

        If the command is a bare ``cd <path>``, updates the session's
        working_dir without running a subprocess, then returns an empty result.

        Args:
            workspace: Absolute workspace path.
            command:   Raw command string (validated via validate_command).

        Returns:
            (stdout, stderr, returncode) strings and int.

        Raises:
            ValueError:      If the command is blocked or malformed.
            PermissionError: If the path would escape the workspace.
        """
        session = self.get_or_create(workspace)
        session.touch()

        # Validate the raw command against the allowlist/denylist
        validated = validate_command(command, workspace)
        parts = shlex.split(validated)

        # Handle ``cd`` without spawning a process
        target_dir = _resolve_cd(session, parts)
        if target_dir is not None:
            session.working_dir = target_dir
            return f"Changed directory to {target_dir}", "", 0
        if parts and parts[0] == "cd":
            # cd with a bad target — return an error without modifying cwd
            return "", f"cd: no such directory: {parts[1] if len(parts) > 1 else ''}", 1

        workspace_root = Path(workspace).resolve()
        # Ensure session.working_dir is still inside the workspace
        try:
            session.working_dir.relative_to(workspace_root)
        except ValueError:
            session.working_dir = workspace_root

        try:
            proc = await asyncio.create_subprocess_exec(
                *parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(session.working_dir),
            )
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=settings.terminal_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise ValueError(
                f"Command timed out after {settings.terminal_timeout_seconds}s."
            ) from exc
        except FileNotFoundError as exc:
            raise ValueError(f"Command not found: {parts[0]}") from exc

        return (
            stdout_b.decode("utf-8", errors="replace"),
            stderr_b.decode("utf-8", errors="replace"),
            proc.returncode or 0,
        )

    def close(self, workspace: str) -> bool:
        """
        Remove the session for a workspace.

        Args:
            workspace: Absolute workspace path.

        Returns:
            True if a session was found and removed, False otherwise.
        """
        key = _hash_workspace(workspace)
        if key in self._sessions:
            del self._sessions[key]
            log.info("Closed PTY session workspace_hash=%s", key)
            return True
        return False

    def close_by_hash(self, workspace_hash: str) -> bool:
        """
        Remove the session identified by its workspace hash.

        Used by the DELETE /terminal/sessions/{workspace_hash} endpoint.

        Args:
            workspace_hash: 8-char hex hash from the sessions list API.

        Returns:
            True if found and removed, False otherwise.
        """
        if workspace_hash in self._sessions:
            del self._sessions[workspace_hash]
            log.info("Closed PTY session workspace_hash=%s (by hash)", workspace_hash)
            return True
        return False

    def list_sessions(self) -> list[PtySession]:
        """
        Return all active sessions after reaping idle ones.

        Returns:
            List of PtySession objects, ordered by workspace path.
        """
        self._reap_idle_sessions()
        return sorted(self._sessions.values(), key=lambda s: s.workspace)


# ── Singleton ─────────────────────────────────────────────────────────────────

pty_manager = PtyManager()
