"""
terminal.py — Terminal command sandbox and path traversal prevention.

This module is the LAST line of defence before any shell/fs operation executes.
It must be called from every endpoint that touches terminal execution or file paths.

Threat model defended:
  1. Command injection    — DANGEROUS_PATTERNS regex rejects shell metacharacters
  2. Path traversal       — safe_resolve() rejects paths escaping workspace root
  3. Privilege escalation — DENYLIST blocks sudo/su/pkexec and shell spawners
  4. Data exfiltration    — DENYLIST blocks curl/wget/nc/ssh
  5. Destructive ops      — DENYLIST blocks rm/dd/mkfs/shutdown
"""
import re
import shlex
from pathlib import Path

# ── Command allowlist (must exist here to be permitted) ───────────────────────
ALLOWLIST: set[str] = {
    # File inspection (read-only)
    "ls", "cat", "head", "tail", "grep", "find", "echo", "pwd", "whoami", "tree",
    # File creation / movement (non-destructive)
    "mkdir", "touch", "cp", "mv",
    # Python ecosystem
    "python", "python3", "pip", "pip3", "pipenv", "poetry",
    # Node ecosystem
    "npm", "npx", "node", "pnpm", "yarn",
    # Git
    "git", "gh",
    # App servers / test runners
    "uvicorn", "gunicorn", "flask",
    "pytest", "unittest", "coverage",
    # Linters / formatters
    "ruff", "black", "mypy", "flake8", "eslint", "prettier",
    # Build tools
    "tsc", "vite", "webpack", "esbuild",
    # Misc safe tools
    "make", "cargo",
}

# ── Command denylist (explicit block, checked before allowlist) ───────────────
DENYLIST: set[str] = {
    # Destructive file ops
    "rm", "rmdir", "dd", "shred", "truncate",
    # Network exfiltration
    "curl", "wget", "nc", "ncat", "netcat", "socat",
    "ssh", "scp", "rsync", "ftp", "sftp",
    # Privilege escalation
    "sudo", "su", "doas", "pkexec", "newgrp", "runuser",
    # System / fs modification
    "chmod", "chown", "chgrp", "umask",
    "mount", "umount", "fdisk", "mkfs", "fsck",
    "systemctl", "service", "launchctl",
    # Destructive process management
    "kill", "killall", "pkill", "renice",
    "shutdown", "reboot", "halt", "poweroff",
    # Shell / eval bypasses
    "bash", "sh", "zsh", "fish", "ksh", "csh", "exec",
    "eval", "source",
    # System package managers
    "apt", "apt-get", "yum", "dnf", "brew", "pacman", "snap",
}

# ── Dangerous shell patterns (reject before parsing) ─────────────────────────
DANGEROUS_PATTERNS: list[str] = [
    r"[;&|`$]",          # shell chaining / subshell injection
    r"\$\(",             # command substitution
    r">\s*/dev/",        # redirect to device file
    r">\s*~/",           # redirect to home directory (sneaky overwrite)
    r"\.\./",            # path traversal in inline paths
    r"\beval\b",
    r"\bexec\b",
    r"\bsource\b",
]


def validate_command(cmd: str, workspace_path: str = "") -> str:  # noqa: ARG001
    """
    Validate a terminal command before execution.

    Args:
        cmd: The raw command string from the client.
        workspace_path: Current workspace (reserved for future per-workspace rules).

    Returns:
        The unchanged command string if validation passes.

    Raises:
        ValueError: With a human-readable reason if the command is blocked.
    """
    # 1. Reject dangerous shell patterns first (before shlex can be tricked)
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            raise ValueError(
                f"Command blocked: dangerous pattern detected ({pattern!r}). "
                "Shell metacharacters and redirects are not permitted."
            )

    # 2. Parse safely — shlex prevents quote-escape tricks
    try:
        parts = shlex.split(cmd)
    except ValueError as exc:
        raise ValueError(f"Malformed command: {exc}") from exc

    if not parts:
        raise ValueError("Empty command.")

    # 3. Extract binary name (strip any path prefix to prevent /bin/rm tricks)
    binary = Path(parts[0]).name

    # 4. Denylist check — explicit block, highest priority
    if binary in DENYLIST:
        raise ValueError(
            f"Command '{binary}' is blocked by the security denylist."
        )

    # 5. Allowlist check — must be explicitly permitted
    if binary not in ALLOWLIST:
        raise ValueError(
            f"Command '{binary}' is not in the allowlist. "
            "To permit it, add it to ALLOWLIST in backend/security/terminal.py."
        )

    return cmd


def safe_resolve(workspace: str, user_path: str) -> Path:
    """
    Resolve user_path relative to workspace and verify it stays inside.

    Args:
        workspace: Absolute path to the open workspace root.
        user_path: Relative (or absolute) path supplied by the client.

    Returns:
        Resolved Path guaranteed to be within workspace.

    Raises:
        PermissionError: If the resolved path escapes the workspace root.
    """
    workspace_root = Path(workspace).resolve()
    candidate = (workspace_root / user_path).resolve()

    try:
        candidate.relative_to(workspace_root)
    except ValueError as exc:
        raise PermissionError(
            f"Path '{user_path}' escapes workspace root. Request blocked."
        ) from exc

    return candidate
