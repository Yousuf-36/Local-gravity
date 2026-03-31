"""
streamer.py — Ollama streaming client and conversation management.

Responsibilities:
  - stream_ollama(): async generator that yields raw JSON lines from Ollama /api/chat
  - trim_history(): keeps conversation within the context window budget
  - sanitize_file_content_for_prompt(): wraps file content to resist prompt injection
"""
import json
from typing import AsyncGenerator

import httpx

from config import settings

DEFAULT_MODEL = "gpt-oss:20b"

SYSTEM_PROMPT = """You are LocalGravity's AI agent, running 100% locally on the developer's machine.
You have no internet access and must never attempt external network calls.

When given a coding task:
1. Create a plan as a markdown artifact before touching any file
2. Execute file operations one at a time, explaining each step
3. Report exactly what you changed and why
4. If you need to run a terminal command, state it clearly and wait for approval

You have access to three tools: read_file, write_file, run_terminal.
Always prefer reading a file before modifying it."""

# ── Tool definitions exposed to the model ─────────────────────────────────────
AGENT_TOOLS: list[dict] = [
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


async def stream_ollama(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    tools: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat response from Ollama, yielding raw JSON lines.

    Each yielded string is one NDJSON line from Ollama, suitable for wrapping
    in an SSE `data:` frame by the caller.

    Yields error JSON shapes on connection or timeout failure instead of raising.
    """
    payload: dict = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "stream": True,
        "options": {
            "temperature": 0.2,
            "num_ctx": 8192,
            "num_predict": 4096,
        },
    }
    if tools:
        payload["tools"] = tools

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST", f"{settings.ollama_host}/api/chat", json=payload
            ) as resp:
                if resp.status_code != 200:
                    yield json.dumps({"error": "ollama_error", "message": f"Ollama returned HTTP {resp.status_code}"})
                    return
                async for line in resp.aiter_lines():
                    if line.strip():
                        yield line
    except httpx.ConnectError:
        yield json.dumps({"error": "ollama_unreachable", "message": "Ollama is not running. Start with: ollama serve"})
    except httpx.TimeoutException:
        yield json.dumps({"error": "timeout", "message": "Model took too long to respond (>180s)"})


def trim_history(messages: list[dict], max_tokens: int = 6000) -> list[dict]:
    """
    Trim conversation history to fit within the context window.

    Estimate: 1 token ≈ 4 characters (conservative for mixed code/prose).
    Always keeps the most recent messages; drops oldest first.
    """
    kept: list[dict] = []
    total = 0
    for msg in reversed(messages):
        est = len(msg.get("content", "")) // 4
        if total + est > max_tokens:
            break
        kept.insert(0, msg)
        total += est
    return kept


def sanitize_file_content_for_prompt(content: str, max_chars: int = 4000) -> str:
    """
    Wrap file content in XML-like tags so the model treats it as data, not instructions.
    Truncates large files to prevent context overflow.
    """
    truncated = content[:max_chars]
    if len(content) > max_chars:
        truncated += f"\n[TRUNCATED: {len(content) - max_chars} chars omitted]"
    return f"<file_content>\n{truncated}\n</file_content>"
