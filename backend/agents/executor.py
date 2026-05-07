"""
agents/executor.py — Core agentic loop for LocalGravity.

Flow per step:
  1. Call Ollama with the current message history and tool schemas.
  2. Accumulate all streamed tokens into one complete response.
  3. If the response contains tool_calls:
       a. Emit ToolCallFrame for each call.
       b. If tool is destructive → emit WaitingApprovalFrame, block on HITL event.
       c. Approved → execute, emit ToolResultFrame, append to history, continue.
       d. Denied → emit ErrorFrame(tool_blocked), return.
  4. No tool_calls in response → emit FinalAnswerFrame, return.
  5. steps >= MAX_EXECUTOR_STEPS → emit ErrorFrame(step_limit), return.

SSE frame types yielded (plain dicts; router JSON-serialises and wraps in data:):
  plan | tool_call | tool_result | final_answer | error | waiting_approval

Security properties:
  - Tool dispatch is a dict lookup only — no eval/exec.
  - Destructive tools are hard-blocked until an approval asyncio.Event fires.
  - Tool output is XML-wrapped and capped at _MAX_TOOL_OUTPUT_CHARS before
    re-injection, mitigating prompt injection via tool results.
  - Step cap prevents infinite loops from runaway models.
  - Approval events are one-shot UUID4-keyed — cannot be replayed.

Persistence (Phase 2 fix):
  - Every message appended to the in-memory history is also written to the
    conversation_history table via db_append_message.
  - On startup the router passes a pre-loaded history from db_load_history
    so the executor resumes from where it left off after a restart.
  - db is optional: if None (tests without a DB fixture) persistence is skipped.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import aiosqlite

from agents.approval_store import approval_store
from agents.streamer import stream_ollama, trim_history
from agents.tools import ToolRegistry
from db.database import db_append_message
from logging_config import get_logger

log = get_logger("executor")

# Hard cap — prevents runaway LLM loops
MAX_EXECUTOR_STEPS: int = 20

# Characters of tool output re-injected into context per call
_MAX_TOOL_OUTPUT_CHARS: int = 4_000


# ── SSE Frame Builders ────────────────────────────────────────────────────────


def _plan_frame(task_id: str, content: str) -> dict[str, Any]:
    """Build a plan SSE frame."""
    return {"type": "plan", "task_id": task_id, "content": content}


def _tool_call_frame(
    task_id: str,
    call_id: str,
    tool: str,
    args: dict[str, str],
    destructive: bool,
) -> dict[str, Any]:
    """Build a tool_call SSE frame."""
    return {
        "type": "tool_call",
        "task_id": task_id,
        "call_id": call_id,
        "tool": tool,
        "args": args,
        "destructive": destructive,
    }


def _tool_result_frame(
    task_id: str,
    call_id: str,
    output: str,
    returncode: int | None,
    truncated: bool,
) -> dict[str, Any]:
    """Build a tool_result SSE frame."""
    frame: dict[str, Any] = {
        "type": "tool_result",
        "task_id": task_id,
        "call_id": call_id,
        "output": output,
        "truncated": truncated,
    }
    if returncode is not None:
        frame["returncode"] = returncode
    return frame


def _final_answer_frame(
    task_id: str, content: str, steps_used: int
) -> dict[str, Any]:
    """Build a final_answer SSE frame."""
    return {
        "type": "final_answer",
        "task_id": task_id,
        "content": content,
        "steps_used": steps_used,
    }


def _error_frame(task_id: str, code: str, message: str) -> dict[str, Any]:
    """Build an error SSE frame."""
    return {"type": "error", "task_id": task_id, "code": code, "message": message}


def _waiting_approval_frame(
    task_id: str,
    call_id: str,
    tool: str,
    args: dict[str, str],
    summary: str,
) -> dict[str, Any]:
    """Build a waiting_approval SSE frame."""
    return {
        "type": "waiting_approval",
        "task_id": task_id,
        "call_id": call_id,
        "tool": tool,
        "args": args,
        "summary": summary,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _sanitize_tool_output(output: str, tool_name: str) -> tuple[str, bool]:
    """
    Wrap tool output in XML tags and cap at _MAX_TOOL_OUTPUT_CHARS.

    The XML wrapper signals to the model that this is data, not instructions,
    mitigating prompt injection via crafted file contents or command output.

    Args:
        output:    Raw string returned by the tool's execute() method.
        tool_name: Injected into the XML tag for model-side traceability.

    Returns:
        (sanitized_string, was_truncated) tuple.
    """
    truncated = len(output) > _MAX_TOOL_OUTPUT_CHARS
    body = output[:_MAX_TOOL_OUTPUT_CHARS]
    if truncated:
        omitted = len(output) - _MAX_TOOL_OUTPUT_CHARS
        body += f"\n[TRUNCATED: {omitted} chars omitted]"
    return f'<tool_result name="{tool_name}">\n{body}\n</tool_result>', truncated


def _build_approval_summary(tool_name: str, args: dict[str, str]) -> str:
    """
    Build a human-readable one-line summary shown in the ApprovalCard UI.

    Args:
        tool_name: Name of the tool to be executed.
        args:      Arguments the model provided for the call.

    Returns:
        A short English sentence describing the pending action.
    """
    if tool_name == "write_file":
        path = args.get("path", "?")
        size = len(args.get("content", "").encode())
        return f"Write {size:,} bytes to {path}"
    if tool_name == "run_terminal":
        cmd = args.get("command", "?")
        return f"Run terminal command: {cmd}"
    return f"Execute {tool_name} with args: {list(args.keys())}"


def _parse_tool_args(raw_args: Any) -> dict[str, str]:
    """
    Coerce Ollama tool_call arguments to a plain string dict.

    Ollama may deliver arguments as a JSON string or as a pre-parsed dict.

    Args:
        raw_args: The ``arguments`` value from an Ollama tool_call object.

    Returns:
        A best-effort string-keyed dict, falling back to {} on parse failure.
    """
    if isinstance(raw_args, dict):
        return {str(k): str(v) for k, v in raw_args.items()}
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            pass
    return {}


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


async def _persist(
    db: aiosqlite.Connection | None,
    task_id: str,
    role: str,
    content: str,
) -> None:
    """
    Write one message to conversation_history. No-op if db is None.

    Args:
        db:      Open aiosqlite connection, or None (test / no-DB mode).
        task_id: Parent task id.
        role:    'user', 'assistant', or 'tool'.
        content: Message content string.
    """
    if db is None:
        return
    try:
        await db_append_message(db, task_id, role, content, _now_iso())
    except Exception as exc:  # noqa: BLE001
        # Persistence failure must never crash the executor loop.
        log.warning("db_append_message failed task=%s role=%s: %s", task_id, role, exc)


# ── Core Loop ─────────────────────────────────────────────────────────────────


async def run_executor(
    task_id: str,
    messages: list[dict[str, Any]],
    model: str,
    workspace: str,
    registry: ToolRegistry,
    db: aiosqlite.Connection | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Run the agentic loop for a single task and yield typed SSE frame dicts.

    This is an async generator. The router wraps each yielded dict in
    ``data: {json}\\n\\n`` for SSE delivery to the frontend.

    Args:
        task_id:   Short task UUID from the registry.
        messages:  Conversation history (at minimum one user message).
                   Loaded from DB by the router on restart so the executor
                   picks up where it left off.
        model:     Ollama model name (validated against /api/tags by the router).
        workspace: Absolute workspace root path (pre-validated by the router).
        registry:  ToolRegistry instance — provides tool schemas and dispatch.
        db:        Optional open aiosqlite connection for history persistence.
                   Pass None to skip persistence (used by unit tests).

    Yields:
        Typed frame dicts matching the SSE schema defined in the plan:
        plan | tool_call | tool_result | final_answer | error | waiting_approval
    """
    # ── Persist the initial user message(s) ──────────────────────────────────
    # Only persist if these messages haven't been stored yet (i.e. the first
    # turn). On restart the messages are loaded from DB so they already exist.
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user",) and content:
            await _persist(db, task_id, role, content)

    history: list[dict[str, Any]] = trim_history(list(messages))
    steps = 0

    while steps < MAX_EXECUTOR_STEPS:
        steps += 1
        log.info("executor step=%d task=%s model=%s", steps, task_id, model)

        # ── Accumulate one complete Ollama response ───────────────────────────
        accumulated_content = ""
        accumulated_tool_calls: list[dict[str, Any]] = []
        ollama_error: str | None = None

        async for line in stream_ollama(
            history, model=model, tools=registry.to_ollama_schema()
        ):
            try:
                data: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "error" in data:
                err_val = data["error"]
                msg_obj_err = data.get("message", str(err_val))
                ollama_error = msg_obj_err
                break

            msg_obj: dict[str, Any] = data.get("message", {})

            # Accumulate streamed text tokens
            chunk = msg_obj.get("content", "")
            if chunk:
                accumulated_content += chunk

            # Ollama delivers tool_calls on the terminal message (done=True)
            if data.get("done"):
                raw_calls = msg_obj.get("tool_calls") or []
                accumulated_tool_calls = raw_calls

        if ollama_error is not None:
            code = (
                "ollama_unreachable"
                if "not running" in ollama_error.lower()
                else "agent_error"
            )
            yield _error_frame(task_id, code=code, message=ollama_error)
            return

        # ── Route: tool calls vs. final answer ───────────────────────────────
        if not accumulated_tool_calls:
            # No tool calls → this is the final answer
            # Persist the assistant's final response
            if accumulated_content:
                await _persist(db, task_id, "assistant", accumulated_content)
            yield _final_answer_frame(
                task_id,
                content=accumulated_content,
                steps_used=steps,
            )
            return

        # Append the assistant turn (may include text + tool_calls) to memory
        assistant_msg = {
            "role": "assistant",
            "content": accumulated_content,
            "tool_calls": accumulated_tool_calls,
        }
        history.append(assistant_msg)

        # Persist assistant turn — store content; tool_calls stored as JSON
        assistant_content = accumulated_content
        if accumulated_tool_calls:
            assistant_content += (
                "\n[tool_calls]" + json.dumps(accumulated_tool_calls)
                if accumulated_content
                else "[tool_calls]" + json.dumps(accumulated_tool_calls)
            )
        await _persist(db, task_id, "assistant", assistant_content)

        # ── Process each tool call in order ──────────────────────────────────
        for tc in accumulated_tool_calls:
            fn: dict[str, Any] = tc.get("function", {})
            tool_name: str = fn.get("name", "")
            args = _parse_tool_args(fn.get("arguments", {}))
            call_id = str(uuid.uuid4())
            destructive = registry.is_destructive(tool_name)

            yield _tool_call_frame(task_id, call_id, tool_name, args, destructive)

            # ── HITL gate for destructive tools ──────────────────────────────
            if destructive:
                summary = _build_approval_summary(tool_name, args)
                yield _waiting_approval_frame(
                    task_id, call_id, tool_name, args, summary
                )
                entry = approval_store.create(task_id, call_id)
                await entry.event.wait()
                decision = approval_store.consume(task_id, call_id)

                if decision != "approved":
                    yield _error_frame(
                        task_id,
                        code="tool_blocked",
                        message=(
                            f"User denied execution of '{tool_name}' "
                            f"(call_id={call_id})."
                        ),
                    )
                    return

            # ── Execute the tool ──────────────────────────────────────────────
            try:
                tool = registry.get(tool_name)
                raw_output = await tool.execute(args, workspace)
            except KeyError:
                yield _error_frame(
                    task_id,
                    code="tool_blocked",
                    message=f"Unknown tool '{tool_name}'. Execution blocked.",
                )
                return
            except (ValueError, PermissionError) as exc:
                raw_output = f"Tool error ({tool_name}): {exc}"
                log.warning("tool=%s error=%s task=%s", tool_name, exc, task_id)

            sanitized, truncated = _sanitize_tool_output(raw_output, tool_name)

            # Extract returncode for terminal tool for the frame
            returncode: int | None = None
            if tool_name == "run_terminal":
                for part in raw_output.splitlines():
                    if part.startswith("returncode:"):
                        try:
                            returncode = int(part.split(":", 1)[1].strip())
                        except ValueError:
                            pass

            yield _tool_result_frame(
                task_id, call_id, sanitized, returncode, truncated
            )

            # Append the tool result as a ``tool`` role message for Ollama
            tool_msg = {
                "role": "tool",
                "content": sanitized,
            }
            history.append(tool_msg)

            # Persist tool result
            await _persist(db, task_id, "tool", sanitized)

    # ── Step limit reached ────────────────────────────────────────────────────
    yield _error_frame(
        task_id,
        code="step_limit",
        message=(
            f"Agent reached the {MAX_EXECUTOR_STEPS}-step limit without "
            "producing a final answer. Task stopped."
        ),
    )
