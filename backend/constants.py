"""
constants.py — Application-wide constants for business logic and validation.

This file holds static configurations that do not come from the environment:
  - Security allowlists and denylists for terminal command sandboxing
  - Dangerous shell patterns
  - Agentic loop limits
  - System prompt for the agent

NOTE: ALLOWED_MODELS was removed — model validation now happens at request
time against Ollama /api/tags so any locally-installed model is permitted.

NOTE: AGENT_TOOLS was removed — tool schemas are now owned by agents/tools.py.
"""
from typing import FrozenSet, List, Set

# ── Executor limits ──────────────────────────────────────────────────────────
MAX_EXECUTOR_STEPS: int = 20
"""Hard cap on agentic loop steps. Prevents runaway LLM loops."""

DESTRUCTIVE_TOOLS: FrozenSet[str] = frozenset({"write_file", "run_terminal"})
"""Tool names that require HITL approval before execution."""

DEFAULT_MODEL: str = "llama3"
"""Fallback model name used when no model is specified."""


# ── Command allowlist (must exist here to be permitted) ───────────────────────
ALLOWLIST: Set[str] = {
    # File inspection (read-only)
    # NOTE: "ls" removed — does not exist on Windows (use "dir" instead)
    "dir", "cat", "head", "tail", "grep", "find", "echo", "pwd", "whoami", "tree", "type",
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
DENYLIST: Set[str] = {
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
DANGEROUS_PATTERNS: List[str] = [
    r"[;&|`$]",          # shell chaining / subshell injection
    r"\$\(",             # command substitution
    r">\s*/dev/",        # redirect to device file
    r">\s*~/",           # redirect to home directory (sneaky overwrite)
    r"\.\./",            # path traversal in inline paths
    r"\beval\b",
    r"\bexec\b",
    r"\bsource\b",
]

# ── Agent Execution Prompt ───────────────────────────────────────────────────
AGENT_SYSTEM_PROMPT: str = """You are LocalGravity's AI agent, running 100% locally on the developer's machine.
You have no internet access and must never attempt external network calls.

When given a coding task:
1. Create a plan as a markdown artifact before touching any file
2. Execute file operations one at a time, explaining each step
3. Report exactly what you changed and why
4. If you need to run a terminal command, state it clearly and wait for approval

You have access to three tools: read_file, write_file, run_terminal.
Always prefer reading a file before modifying it."""
