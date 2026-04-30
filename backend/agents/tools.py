"""
agents/tools.py — Tool protocol and registry for the agentic loop.

Each tool implements BaseTool and is registered in the global ToolRegistry
singleton. The registry is the single source of truth for:
  - which tools the model may call
  - which tools are destructive (require HITL approval)
  - the JSON Schema passed to Ollama for tool-calling

Threat model:
  - Tool dispatch uses a dict lookup only — no eval/exec anywhere.
  - The ``destructive`` flag drives the HITL gate in executor.py.
  - File tools delegate to safe_resolve() for path validation.
  - Terminal tool delegates to validate_command() for command validation.
  - OllamaQueryTool is read-only and non-destructive.
"""
import asyncio
import shlex
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, final

import httpx

from agents.streamer import sanitize_file_content_for_prompt
from config import settings
from security.terminal import safe_resolve, validate_command


# ── Tool Protocol ─────────────────────────────────────────────────────────────


class BaseTool(ABC):
    """Abstract base class that every agent tool must implement."""

    name: str
    description: str
    input_schema: dict[str, Any]
    destructive: bool = False

    @abstractmethod
    async def execute(self, args: dict[str, str], workspace: str) -> str:
        """
        Execute the tool and return a plain-text result string.

        Args:
            args:      Validated argument dict from the model's tool call.
            workspace: Absolute path to the open workspace root.

        Returns:
            Plain-text result injected back into the conversation history.

        Raises:
            ValueError:      If args are invalid or the operation fails safely.
            PermissionError: If a path escapes the workspace (via safe_resolve).
        """


# ── Concrete Tools ────────────────────────────────────────────────────────────


@final
class ReadFileTool(BaseTool):
    """Read a file from the workspace."""

    name = "read_file"
    description = (
        "Read the contents of a file in the workspace. "
        "Returns the file content as a string, capped at 4 000 characters. "
        "Always read a file before proposing edits to it."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the workspace root.",
            }
        },
        "required": ["path"],
    }
    destructive = False

    async def execute(self, args: dict[str, str], workspace: str) -> str:
        """Read and return file contents via safe_resolve, capped at 4 000 chars."""
        path = args.get("path", "").strip()
        if not path:
            raise ValueError("read_file requires a non-empty 'path' argument.")
        target = safe_resolve(workspace, path)
        if not target.is_file():
            raise ValueError(f"Not a file: {path}")
        max_bytes = settings.max_file_size_mb * 1024 * 1024
        if target.stat().st_size > max_bytes:
            raise ValueError(
                f"File exceeds {settings.max_file_size_mb} MB limit. "
                "Use a more targeted read."
            )
        raw = target.read_text(encoding="utf-8", errors="replace")
        return sanitize_file_content_for_prompt(raw)


@final
class WriteFileTool(BaseTool):
    """Write content to a file in the workspace."""

    name = "write_file"
    description = (
        "Write content to a file in the workspace. "
        "Creates the file and parent directories if they do not exist. "
        "DESTRUCTIVE — requires user approval before execution."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the workspace root.",
            },
            "content": {
                "type": "string",
                "description": "Full content to write to the file.",
            },
        },
        "required": ["path", "content"],
    }
    destructive = True

    async def execute(self, args: dict[str, str], workspace: str) -> str:
        """Write content to the safe-resolved path."""
        path = args.get("path", "").strip()
        content = args.get("content", "")
        if not path:
            raise ValueError("write_file requires a non-empty 'path' argument.")
        if len(content.encode()) > 10 * 1024 * 1024:
            raise ValueError("Content exceeds 10 MB write limit.")
        target = safe_resolve(workspace, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        byte_count = len(content.encode())
        return f"Written {byte_count:,} bytes to {path}."


@final
class RunTerminalTool(BaseTool):
    """Run a sandboxed terminal command in the workspace."""

    name = "run_terminal"
    description = (
        "Run a terminal command in the workspace directory. "
        "The command is validated against an allowlist and denylist server-side. "
        "DESTRUCTIVE — requires user approval before execution."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to run (allowlist enforced).",
            }
        },
        "required": ["command"],
    }
    destructive = True

    async def execute(self, args: dict[str, str], workspace: str) -> str:
        """Validate the command then run via create_subprocess_exec (no shell=True)."""
        command = args.get("command", "").strip()
        if not command:
            raise ValueError("run_terminal requires a non-empty 'command' argument.")
        validated = validate_command(command, workspace)
        parts = shlex.split(validated)
        workspace_path = Path(workspace).resolve()
        try:
            proc = await asyncio.create_subprocess_exec(
                *parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace_path),
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

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        rc = proc.returncode or 0
        lines: list[str] = []
        if stdout:
            lines.append(f"stdout:\n{stdout[:3000]}")
        if stderr:
            lines.append(f"stderr:\n{stderr[:1000]}")
        lines.append(f"returncode: {rc}")
        return "\n".join(lines)


@final
class ListFilesTool(BaseTool):
    """List files and directories in the workspace (max 2 levels deep)."""

    name = "list_files"
    description = (
        "Return a compact directory listing of the workspace, up to 2 levels deep. "
        "Use this to understand project structure before reading or writing files."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "subpath": {
                "type": "string",
                "description": (
                    "Optional subdirectory relative to the workspace root. "
                    "Defaults to the workspace root if omitted."
                ),
            }
        },
        "required": [],
    }
    destructive = False

    async def execute(self, args: dict[str, str], workspace: str) -> str:
        """Return a compact two-level directory listing."""
        subpath = args.get("subpath", "").strip()
        root = (
            safe_resolve(workspace, subpath)
            if subpath
            else Path(workspace).resolve()
        )
        if not root.is_dir():
            raise ValueError(f"Not a directory: {subpath or workspace}")
        lines: list[str] = [str(root)]
        self._collect(root, lines, depth=0, max_depth=2)
        return "\n".join(lines)

    @staticmethod
    def _collect(
        directory: Path, lines: list[str], depth: int, max_depth: int
    ) -> None:
        """Recursively collect entries up to max_depth."""
        if depth >= max_depth:
            return
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda p: (p.is_file(), p.name.lower()),
            )
        except PermissionError:
            return
        for entry in entries:
            indent = "  " * (depth + 1)
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{indent}{entry.name}{suffix}")
            if entry.is_dir():
                ListFilesTool._collect(entry, lines, depth + 1, max_depth)


@final
class OllamaQueryTool(BaseTool):
    """Send a focused sub-query to the local Ollama model."""

    name = "ollama_query"
    description = (
        "Ask the local Ollama model a focused sub-question without continuing the main loop. "
        "Useful for classification, summarisation, or translation tasks mid-plan."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The prompt to send to Ollama.",
            },
            "model": {
                "type": "string",
                "description": "Ollama model name. Defaults to the active model if omitted.",
            },
        },
        "required": ["prompt"],
    }
    destructive = False

    async def execute(self, args: dict[str, str], workspace: str) -> str:  # noqa: ARG002
        """Send a single-turn prompt to Ollama and return the response text."""
        prompt = args.get("prompt", "").strip()
        if not prompt:
            raise ValueError("ollama_query requires a non-empty 'prompt' argument.")
        model = args.get("model", "").strip() or settings.default_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 1024},
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    f"{settings.ollama_host}/api/chat", json=payload
                )
                r.raise_for_status()
                data: dict[str, Any] = r.json()
                return data.get("message", {}).get("content", "")
        except httpx.ConnectError as exc:
            raise ValueError("Ollama is not running.") from exc
        except httpx.HTTPStatusError as exc:
            raise ValueError(
                f"Ollama API error: {exc.response.status_code}"
            ) from exc


# ── Registry ──────────────────────────────────────────────────────────────────


class ToolRegistry:
    """
    Registry of all tools available to the agent executor.

    Tools are registered at module load time. The executor calls
    ``to_ollama_schema()`` to inject the full tool list into each Ollama
    request, and ``get()`` to dispatch tool calls by name.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool instance.

        Raises:
            RuntimeError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise RuntimeError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """
        Return the tool with the given name.

        Raises:
            KeyError: If no tool with that name is registered.
        """
        if name not in self._tools:
            raise KeyError(
                f"Unknown tool '{name}'. Registered: {list(self._tools)}"
            )
        return self._tools[name]

    def all_tools(self) -> list[BaseTool]:
        """Return all registered tools in registration order."""
        return list(self._tools.values())

    def to_ollama_schema(self) -> list[dict[str, Any]]:
        """
        Return the tool list in Ollama's native tool-calling schema format.

        Each entry is compatible with the ``tools`` field of ``/api/chat``.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in self._tools.values()
        ]

    def is_destructive(self, name: str) -> bool:
        """
        Return True if the named tool is flagged as destructive.

        Returns False (safe default) for unknown tool names.
        """
        try:
            return self.get(name).destructive
        except KeyError:
            return False


# ── Singleton ─────────────────────────────────────────────────────────────────

tool_registry = ToolRegistry()
tool_registry.register(ReadFileTool())
tool_registry.register(WriteFileTool())
tool_registry.register(RunTerminalTool())
tool_registry.register(ListFilesTool())
tool_registry.register(OllamaQueryTool())
