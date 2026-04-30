"""
routers/agent.py — Agent streaming and lifecycle endpoints.

Primary endpoint: POST /agent/stream
  - Accepts an AgentRequest
  - Validates the requested model against Ollama /api/tags at request time
    (no hardcoded allowlist — any locally-installed model is permitted)
  - Runs run_executor() and streams every yielded frame as typed SSE:
      data: {json}\n\n
  - Frame types: plan | tool_call | tool_result | final_answer | error |
                 waiting_approval

HITL approval endpoints:
  - POST /agent/approve/{task_id}/{call_id} — unblock a destructive tool call
  - POST /agent/deny/{task_id}/{call_id}   — reject a destructive tool call

Supporting endpoints:
  - GET  /agent/list         — list all tasks in the registry
  - GET  /agent/status/{id} — get a specific task's status
  - POST /agent/kill/{id}   — signal a task to stop + cancel pending approvals
"""
import json

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agents.approval_store import approval_store
from agents.executor import run_executor
from agents.orchestrator import AgentStatus, AgentTask, registry
from agents.tools import tool_registry
from config import settings
from models.schemas import AgentApprovalResponse, AgentRequest

router = APIRouter()


async def _validate_model(model: str) -> None:
    """
    Verify the requested model is available in Ollama /api/tags.

    Args:
        model: The model name string from the request.

    Raises:
        HTTPException(400): If Ollama is unreachable or the model is not installed.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            r.raise_for_status()
            available = [m["name"] for m in r.json().get("models", [])]
    except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reach Ollama to validate model '{model}': {exc}",
        ) from exc
    if model not in available:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Model '{model}' is not installed in Ollama. "
                f"Available: {available}. Run: ollama pull {model}"
            ),
        )


@router.post("/stream")
async def stream_agent(req: AgentRequest) -> StreamingResponse:
    """
    Main SSE streaming endpoint.

    Validates the model against Ollama /api/tags, spawns a task in the
    registry, then runs run_executor() streaming every frame as:
        data: {json}\n\n

    Errors inside the executor are emitted as typed error frames so the
    renderer always receives a parseable message and never sees a broken stream.
    """
    await _validate_model(req.model)

    task = registry.spawn(
        description=req.message[:80],
        workspace=req.workspace_path,
        model=req.model,
    )
    registry.update_status(task.id, AgentStatus.PLANNING)
    messages: list[dict] = [{"role": "user", "content": req.message}]

    async def generate():
        registry.update_status(task.id, AgentStatus.EXECUTING)
        try:
            async for frame in run_executor(
                task_id=task.id,
                messages=messages,
                model=req.model,
                workspace=req.workspace_path,
                registry=tool_registry,
            ):
                yield f"data: {json.dumps(frame)}\n\n"
                frame_type = frame.get("type")
                if frame_type == "final_answer":
                    registry.update_status(task.id, AgentStatus.DONE)
                elif frame_type == "error":
                    registry.update_status(
                        task.id, AgentStatus.ERROR, error=frame.get("message")
                    )
                elif frame_type == "waiting_approval":
                    registry.update_status(task.id, AgentStatus.WAITING)
        except Exception as exc:  # noqa: BLE001
            error_frame = {
                "type": "error",
                "task_id": task.id,
                "code": "agent_error",
                "message": str(exc),
            }
            yield f"data: {json.dumps(error_frame)}\n\n"
            registry.update_status(task.id, AgentStatus.ERROR, error=str(exc))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/approve/{task_id}/{call_id}", response_model=AgentApprovalResponse)
async def approve_tool_call(task_id: str, call_id: str) -> AgentApprovalResponse:
    """
    Approve a pending destructive tool call.

    The executor is blocking on an asyncio.Event keyed by (task_id, call_id).
    This endpoint sets that event, allowing execution to proceed.

    Raises:
        HTTPException(404): If no pending approval exists for the given ids.
    """
    resolved = approval_store.approve(task_id, call_id)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval for task={task_id} call={call_id}",
        )
    return AgentApprovalResponse(
        ok=True, task_id=task_id, call_id=call_id, decision="approved"
    )


@router.post("/deny/{task_id}/{call_id}", response_model=AgentApprovalResponse)
async def deny_tool_call(task_id: str, call_id: str) -> AgentApprovalResponse:
    """
    Deny a pending destructive tool call.

    Sets the asyncio.Event with a 'denied' decision, causing the executor
    to emit an error frame and halt the loop without touching the filesystem.

    Raises:
        HTTPException(404): If no pending approval exists for the given ids.
    """
    resolved = approval_store.deny(task_id, call_id)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval for task={task_id} call={call_id}",
        )
    return AgentApprovalResponse(
        ok=True, task_id=task_id, call_id=call_id, decision="denied"
    )


@router.get("/list")
async def list_agents() -> list[AgentTask]:
    """Return all tasks in the registry."""
    return registry.list_all()


@router.get("/status/{agent_id}")
async def agent_status(agent_id: str) -> AgentTask:
    """
    Return the current status of a specific task.

    Raises:
        HTTPException(404): If the task id is not in the registry.
    """
    task = registry.get(agent_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return task


@router.post("/kill/{agent_id}")
async def kill_agent(agent_id: str) -> dict:
    """
    Kill a running task and cancel any pending HITL approvals.

    Cancelling pending approvals unblocks any executor coroutine waiting on
    a destructive tool call, allowing it to terminate cleanly.

    Raises:
        HTTPException(404): If the task id is not in the registry.
    """
    task = registry.get(agent_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    registry.kill(agent_id)
    cancelled = approval_store.cancel_all_for_task(agent_id)
    return {
        "ok": True,
        "agent_id": agent_id,
        "status": "error",
        "approvals_cancelled": cancelled,
    }
