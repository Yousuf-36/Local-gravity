"""
routers/terminal.py — Sandboxed terminal command execution.

Security flow:
  1. Pydantic schema validates command length at the HTTP boundary
  2. validate_command() checks ALLOWLIST, DENYLIST, and dangerous patterns
  3. asyncio.create_subprocess_exec (NOT shell=True) prevents shell injection
  4. Execution is capped at settings.terminal_timeout_seconds
  5. Working directory is always the validated workspace root

The endpoint returns a plain JSON response (not streaming) so the Electron
IPC handler can call res.json() synchronously.
"""
import asyncio

from fastapi import APIRouter

from config import settings
from models.schemas import TerminalExecRequest, TerminalExecResponse
from security.terminal import safe_resolve, validate_command

router = APIRouter()


@router.post("/exec", response_model=TerminalExecResponse)
async def exec_command(req: TerminalExecRequest) -> TerminalExecResponse:
    """
    Execute a sandboxed terminal command in the workspace directory.

    Raises:
        ValueError: if the command fails the allowlist/denylist/pattern check.
        PermissionError: if workspace path validation fails.
        TimeoutError: if the command exceeds terminal_timeout_seconds.
    """
    # 1. Security: validate the command string
    validated_cmd = validate_command(req.command, req.workspace)

    # 2. Security: resolve workspace path  
    workspace_path = safe_resolve(req.workspace, ".")

    # 3. Split into args for create_subprocess_exec (avoids shell=True)
    import shlex
    args = shlex.split(validated_cmd)

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_path),
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=settings.terminal_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise ValueError(
            f"Command timed out after {settings.terminal_timeout_seconds}s: {req.command}"
        ) from exc
    except FileNotFoundError as exc:
        raise ValueError(f"Command not found: {args[0]}") from exc

    return TerminalExecResponse(
        stdout=stdout_bytes.decode("utf-8", errors="replace"),
        stderr=stderr_bytes.decode("utf-8", errors="replace"),
        returncode=proc.returncode or 0,
    )
