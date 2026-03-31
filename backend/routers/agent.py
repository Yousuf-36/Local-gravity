"""
routers/agent.py — Agent streaming and lifecycle endpoints.

Primary endpoint: POST /agent/stream
  - Accepts an AgentRequest
  - Streams Ollama responses as Server-Sent Events (text/event-stream)
  - Returns typed error SSE events instead of raising HTTP exceptions
    so the renderer always gets a parseable message

Supporting endpoints:
  - GET  /agent/list         — list all tasks in the registry
  - GET  /agent/status/{id} — get a specific task's status
  - POST /agent/kill/{id}   — signal a task to stop
"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agents.orchestrator import AgentStatus, AgentTask, registry
from agents.streamer import AGENT_TOOLS, stream_ollama, trim_history
from config import settings
from models.schemas import AgentRequest

router = APIRouter()


@router.post("/stream")
async def stream_agent(req: AgentRequest) -> StreamingResponse:
    """
    Main SSE streaming endpoint.
    Each event: `data: {json}\\n\\n`
    """
    # Spawn a task in the registry
    task = registry.spawn(
        description=req.message[:80],
        workspace=req.workspace_path,
        model=req.model,
    )
    registry.update_status(task.id, AgentStatus.PLANNING)

    messages = [{"role": "user", "content": req.message}]
    trimmed = trim_history(messages, max_tokens=settings.max_context_tokens)

    async def generate():
        registry.update_status(task.id, AgentStatus.EXECUTING)
        try:
            async for line in stream_ollama(trimmed, model=req.model, tools=AGENT_TOOLS):
                yield f"data: {line}\n\n"
            registry.update_status(task.id, AgentStatus.DONE)
        except Exception as exc:  # noqa: BLE001
            error_payload = json.dumps({"error": "agent_error", "message": str(exc)})
            yield f"data: {error_payload}\n\n"
            registry.update_status(task.id, AgentStatus.ERROR, error=str(exc))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/list")
async def list_agents() -> list[AgentTask]:
    return registry.list_all()


@router.get("/status/{agent_id}")
async def agent_status(agent_id: str) -> AgentTask:
    task = registry.get(agent_id)
    if task is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return task


@router.post("/kill/{agent_id}")
async def kill_agent(agent_id: str) -> dict:
    task = registry.get(agent_id)
    if task is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    registry.kill(agent_id)
    return {"ok": True, "agent_id": agent_id, "status": "error"}
