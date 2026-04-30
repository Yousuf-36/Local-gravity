"""
streamer.py — Ollama streaming client and conversation management.

Responsibilities:
  - stream_ollama(): async generator that yields raw JSON lines from Ollama /api/chat
  - trim_history(): keeps conversation within the context window budget
  - sanitize_file_content_for_prompt(): wraps file content to resist prompt injection
  - build_tool_result_message(): builds the Ollama ``tool`` role message dict
    used by the executor to append tool results to conversation history
"""
import json
from typing import Any, AsyncGenerator

import httpx

from config import settings
from constants import AGENT_SYSTEM_PROMPT, DEFAULT_MODEL


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
        "messages": [{"role": "system", "content": AGENT_SYSTEM_PROMPT}] + messages,
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


def build_tool_result_message(call_id: str, output: str) -> dict[str, Any]:
    """
    Build an Ollama ``tool`` role message for a completed tool call.

    Appended to the conversation history after each tool execution so the
    model can see the result and decide its next action.

    Args:
        call_id: The UUID4 that identifies the originating tool_call.
        output:  The sanitized tool output string (XML-wrapped, capped).

    Returns:
        A dict compatible with the Ollama /api/chat ``messages`` array.
    """
    return {
        "role": "tool",
        "content": output,
        "tool_call_id": call_id,
    }
