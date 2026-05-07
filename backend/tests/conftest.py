"""
conftest.py — Shared pytest fixtures for the LocalGravity backend test suite.

Fixtures:
  test_client     — HTTPX AsyncClient (or httpx TestClient) wired to the FastAPI app
  mock_db         — In-memory aiosqlite connection with migrations applied
  mock_ollama     — httpx respx mock returning canned SSE: one tool_call + one final_answer
  temp_workspace  — tmp_path with hello.py, README.md, data.json pre-created
"""
import json
import sys
import os
import asyncio

import aiosqlite
import pytest
import pytest_asyncio

# ── Make backend the importable root ─────────────────────────────────────────
# Tests run from the backend/ directory (pytest -s tests/) so backend/ must
# be on sys.path so that `import config`, `import agents.tools` etc. resolve.
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))  # …/backend
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient

# ── pytest-asyncio config ─────────────────────────────────────────────────────
# Use asyncio mode "auto" so all async tests/fixtures work without decoration.
pytest_plugins = ("pytest_asyncio",)


# ── test_client ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_client():
    """
    Synchronous HTTPX TestClient wrapping the full FastAPI app.

    We avoid the lifespan (DB open/migrations/Ollama check) by not using
    ``with`` — the app is started in its default state. Endpoints that require
    app.state.db will raise AttributeError if exercised directly; those tests
    should use mock_db instead.
    """
    from main import app

    # Bypass lifespan for isolated unit testing
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# ── mock_db ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def mock_db():
    """
    In-memory aiosqlite connection with the full schema applied.

    Uses `:memory:` so tests never touch the filesystem.  Each test gets a
    fresh database — the fixture is function-scoped by default.
    """
    from db.database import run_migrations

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")
    await run_migrations(db)
    yield db
    await db.close()


# ── mock_ollama ───────────────────────────────────────────────────────────────

# Canned SSE payload:
#   frame 1 — tool_call (read_file)
#   frame 2 — final_answer text response
_TOOL_CALL_LINE = json.dumps({
    "done": True,
    "message": {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "function": {
                    "name": "read_file",
                    "arguments": {"path": "hello.py"},
                }
            }
        ],
    },
})

_FINAL_ANSWER_LINE = json.dumps({
    "done": True,
    "message": {
        "role": "assistant",
        "content": "Here is the analysis of hello.py.",
        "tool_calls": [],
    },
})

CANNED_SSE_STREAM = f"{_TOOL_CALL_LINE}\n{_FINAL_ANSWER_LINE}\n"


@pytest.fixture
def mock_ollama(monkeypatch):
    """
    Monkeypatch stream_ollama in agents.executor (where it is imported into)
    to yield the two canned SSE lines without hitting a real Ollama process.

    The executor uses ``from agents.streamer import stream_ollama`` so we must
    patch the name in the executor's namespace, not in the streamer module.
    """
    import agents.executor as executor_mod

    async def _fake_stream(messages, *, model, tools=None):
        for line in CANNED_SSE_STREAM.splitlines():
            if line.strip():
                yield line

    monkeypatch.setattr(executor_mod, "stream_ollama", _fake_stream)
    return CANNED_SSE_STREAM


# ── temp_workspace ────────────────────────────────────────────────────────────

@pytest.fixture
def temp_workspace(tmp_path):
    """
    Temporary directory pre-populated with three sample files.

    Structure:
      hello.py    — simple Python hello-world
      README.md   — minimal markdown readme
      data.json   — small JSON object
    """
    (tmp_path / "hello.py").write_text('print("hello, world")\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test Workspace\nSample project.\n", encoding="utf-8")
    (tmp_path / "data.json").write_text('{"key": "value", "count": 42}\n', encoding="utf-8")
    return tmp_path
