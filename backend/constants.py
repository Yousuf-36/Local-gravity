"""
constants.py — Application-wide constants mapping for business logic and validation.

This file holds global static configurations that do not come from the environment,
such as security allowlists, denylists, model maps, and dangerous patterns.
"""
from typing import Set, List

# ── Allowed Ollama models ─────────────────────────────────────────────────────
ALLOWED_MODELS: Set[str] = {"gpt-oss:20b", "llama3", "deepseek-coder", "qwen2.5-coder", "mistral"}
DEFAULT_MODEL: str = "gpt-oss:20b"

# ── Command allowlist (must exist here to be permitted) ───────────────────────
ALLOWLIST: Set[str] = {
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

# ── Tool definitions exposed to the model ─────────────────────────────────────
AGENT_TOOLS: List[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path from workspace root"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file in the workspace. Creates the file if it does not exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": "Run a terminal command in the workspace. Allowlist enforced server-side.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
            },
        },
    },
]
