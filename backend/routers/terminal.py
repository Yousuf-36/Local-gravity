"""
routers/terminal.py — Sandboxed terminal command execution with session management.

Security flow (exec endpoint):
  1. Pydantic schema validates command length at the HTTP boundary
  2. PtyManager.execute() calls validate_command() — ALLOWLIST / DENYLIST / patterns
  3. asyncio.create_subprocess_exec (NOT shell=True) prevents shell injection
  4. Execution is capped at settings.terminal_timeout_seconds
  5. CWD is the session's tracked working_dir (always within workspace)

Session endpoints:
  GET  /terminal/sessions                   — list active PTY sessions
  DELETE /terminal/sessions/{workspace_hash} — evict a session by workspace hash

The exec endpoint returns a plain JSON response (not streaming) so the Electron
IPC handler can call res.json() synchronously.
"""
from fastapi import APIRouter, HTTPException

from agents.pty_manager import PtySession, pty_manager
from models.schemas import TerminalExecRequest, TerminalExecResponse

router = APIRouter()


# ── Exec (wired through PtyManager) ──────────────────────────────────────────


@router.post("/exec", response_model=TerminalExecResponse)
async def exec_command(req: TerminalExecRequest) -> TerminalExecResponse:
    """
    Execute a sandboxed terminal command in the workspace's current working directory.

    CWD is tracked per-workspace across calls — ``cd`` commands update the
    session's working_dir without spawning a shell. All other commands run
    in that directory via create_subprocess_exec.

    Raises:
        ValueError:      If the command fails the allowlist/denylist/pattern check.
        PermissionError: If workspace path validation fails.
        ValueError:      If the command times out.
    """
    stdout, stderr, returncode = await pty_manager.execute(
        workspace=req.workspace,
        command=req.command,
    )
    return TerminalExecResponse(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
    )


# ── Session management ────────────────────────────────────────────────────────


class SessionInfo(TerminalExecResponse.__class__):
    """Not reusing a response model — defining inline for clarity."""


@router.get("/sessions")
async def list_sessions() -> list[dict]:
    """
    List all active PTY sessions and their current working directories.

    Sessions that have exceeded pty_idle_timeout_seconds are automatically
    evicted before this list is compiled.

    Returns:
        List of dicts with workspace, working_dir, workspace_hash, and idle_seconds.
    """
    sessions: list[PtySession] = pty_manager.list_sessions()
    import time

    return [
        {
            "workspace": s.workspace,
            "working_dir": str(s.working_dir),
            "workspace_hash": s.workspace_hash,
            "idle_seconds": round(time.monotonic() - s.last_used_at, 1),
        }
        for s in sessions
    ]


@router.delete("/sessions/{workspace_hash}")
async def delete_session(workspace_hash: str) -> dict:
    """
    Evict an active PTY session by its workspace hash.

    The workspace_hash is the 8-char hex identifier returned by
    GET /terminal/sessions. After deletion, the next command for that
    workspace will start a fresh session at the workspace root.

    Args:
        workspace_hash: 8-char hex hash identifying the session.

    Raises:
        HTTPException(404): If no session exists for the given hash.
    """
    removed = pty_manager.close_by_hash(workspace_hash)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"No active session for workspace_hash={workspace_hash!r}",
        )
    return {"ok": True, "workspace_hash": workspace_hash, "status": "evicted"}
