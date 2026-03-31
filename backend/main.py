"""
main.py — FastAPI application entry point.

Security contract:
  - CORS locked to localhost origins only — no wildcard
  - Bound to 127.0.0.1 exclusively (enforced by uvicorn launch args in root package.json)
  - Ollama health checked on startup; failure is logged but does not crash the app
  - All unhandled PermissionError / ValueError map to structured JSON responses
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers import agent, files, ollama, terminal

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("localgravity")


async def _check_ollama() -> None:
    """Verify Ollama is reachable and log available models on startup."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            log.info("Ollama reachable. Models: %s", models)
    except Exception as exc:  # noqa: BLE001
        log.warning("Ollama unreachable on startup: %s", exc)
        log.warning("Start Ollama with: ollama serve")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await _check_ollama()
    yield
    log.info("LocalGravity backend shutting down.")


app = FastAPI(
    title="LocalGravity API",
    version="0.1.0",
    docs_url="/docs",       # disable in production by setting to None
    redoc_url=None,
    lifespan=lifespan,
)

# CORS — only localhost origins; the renderer communicates via Electron main process
# but FastAPI sees requests originating from these origins during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "app://localhost"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(agent.router,    prefix="/agent",    tags=["agent"])
app.include_router(files.router,    prefix="/files",    tags=["files"])
app.include_router(terminal.router, prefix="/terminal", tags=["terminal"])
app.include_router(ollama.router,   prefix="/ollama",   tags=["ollama"])


# ── Global exception handlers ─────────────────────────────────────────────────
@app.exception_handler(PermissionError)
async def permission_handler(_: Request, exc: PermissionError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"error": str(exc), "type": "security"})


@app.exception_handler(ValueError)
async def value_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": str(exc), "type": "validation"})


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
