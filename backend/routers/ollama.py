"""
routers/ollama.py — Ollama model discovery and active-model management.

Endpoints:
  GET  /ollama/models  — list installed models from Ollama /api/tags
  POST /ollama/switch  — change the active model (allowlist enforced by schema)
  GET  /ollama/health  — connectivity check (used by the frontend status badge)
"""
import httpx
from fastapi import APIRouter

from config import settings
from models.schemas import OllamaModel, OllamaSwitchRequest, OllamaStatusResponse

router = APIRouter()

# Runtime-mutable active model (starts at the default from config)
_active_model: str = settings.default_model


@router.get("/health", response_model=OllamaStatusResponse)
async def ollama_health() -> OllamaStatusResponse:
    """Check Ollama connectivity and return available models."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            return OllamaStatusResponse(ok=True, models=models, active_model=_active_model)
    except Exception as exc:  # noqa: BLE001
        return OllamaStatusResponse(
            ok=False,
            models=[],
            active_model=_active_model,
            error=str(exc),
        )


@router.get("/models")
async def list_models() -> list[OllamaModel]:
    """Return the list of installed Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            r.raise_for_status()
            raw_models = r.json().get("models", [])
            return [
                OllamaModel(
                    name=m["name"],
                    size=m.get("size"),
                    modified_at=m.get("modified_at"),
                )
                for m in raw_models
            ]
    except httpx.ConnectError as exc:
        raise ValueError(
            "Ollama is not running. Start it with: ollama serve"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"Ollama API error: {exc.response.status_code}") from exc


@router.post("/switch")
async def switch_model(req: OllamaSwitchRequest) -> dict:
    """
    Switch the active model. Validated against ALLOWED_MODELS in the schema.
    The new model will be used for all subsequent /agent/stream calls.
    """
    global _active_model  # noqa: PLW0603
    _active_model = req.model
    return {"ok": True, "active_model": _active_model}
