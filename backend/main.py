"""
main.py — FastAPI application entry point.

Security contract:
  - CORS locked to localhost origins only — no wildcard
  - Bound to 127.0.0.1 exclusively (enforced by uvicorn launch args)
  - Ollama health checked on startup; failure is logged but does not crash
  - All unhandled PermissionError / ValueError map to structured JSON responses
  - Swagger UI disabled in production (settings.production = True)

Phase 2 lifespan additions:
  1. Open aiosqlite connection to settings.db_path
  2. Run idempotent schema migrations
  3. Wire registry.set_db(db) for write-through persistence
  4. Load persisted agent tasks into memory: await registry.load_from_db()
  5. Expose connection as app.state.db for use in dependency injection
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.orchestrator import registry
from config import settings
from db.database import open_db, run_migrations
from routers import agent, files, ollama, terminal
from logging_config import get_logger

log = get_logger("localgravity")



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
    """Application lifespan: open DB, run migrations, wire registry, then serve."""
    await _check_ollama()

    log.info("Opening DB at %s", settings.db_path)
    async with open_db(settings.db_path) as db:
        await run_migrations(db)
        registry.set_db(db)
        await registry.load_from_db()
        app.state.db = db
        log.info("LocalGravity backend ready.")
        yield

    log.info("LocalGravity backend shutting down.")



app = FastAPI(
    title="LocalGravity API",
    version="0.2.0",
    # Swagger UI is disabled in production (Electron IPC is the only client).
    # Set PRODUCTION=true in the environment to disable.
    docs_url=None if settings.production else "/docs",
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
