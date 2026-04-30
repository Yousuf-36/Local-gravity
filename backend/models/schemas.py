"""
schemas.py — All Pydantic request/response models for the LocalGravity API.

Every endpoint uses these models for input validation and output serialisation.
Field validators block path traversal and oversized inputs at the HTTP boundary.

NOTE: Model name validation (formerly against ALLOWED_MODELS) was removed.
Model availability is now checked at request time against Ollama /api/tags,
allowing any locally-installed model to be used without a code change.
"""
import os
from typing import Literal

from pydantic import BaseModel, field_validator


# ── Agent ─────────────────────────────────────────────────────────────────────
class AgentRequest(BaseModel):
    """Request body for POST /agent/stream."""

    message: str
    model: str = "llama3"
    workspace_path: str
    session_id: str = "default"

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        """Reject empty messages and messages exceeding the 32 000 char limit."""
        if not v.strip():
            raise ValueError("message must not be empty")
        if len(v) > 32_000:
            raise ValueError("message exceeds 32 000 character limit")
        return v

    @field_validator("workspace_path")
    @classmethod
    def validate_workspace_path(cls, v: str) -> str:
        """Reject path traversal and non-directory workspace paths."""
        if ".." in v:
            raise ValueError("workspace_path must not contain '..'")
        resolved = os.path.realpath(v)
        if not os.path.isdir(resolved):
            raise ValueError(f"workspace_path is not a directory: {resolved}")
        return resolved


class AgentStreamChunk(BaseModel):
    """Legacy schema kept for backward compatibility. Superseded by typed SSE frames."""

    content: str = ""
    done: bool = False
    error: str | None = None


# ── HITL Approval ─────────────────────────────────────────────────────
class ApprovalRequest(BaseModel):
    """Request body for explicit approve/deny (unused by HTTP path — kept for SDK use)."""

    decision: Literal["approved", "denied"]


class AgentApprovalResponse(BaseModel):
    """Response body for POST /agent/approve and POST /agent/deny."""

    ok: bool
    task_id: str
    call_id: str
    decision: str



# ── Files ─────────────────────────────────────────────────────────────────────
class FileReadRequest(BaseModel):
    workspace: str
    path: str

    @field_validator("path")
    @classmethod
    def no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("path must not contain '..'")
        return v


class FileWriteRequest(BaseModel):
    workspace: str
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def no_traversal(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("path must not contain '..'")
        return v

    @field_validator("content")
    @classmethod
    def content_size(cls, v: str) -> str:
        max_bytes = 10 * 1024 * 1024  # 10 MB
        if len(v.encode()) > max_bytes:
            raise ValueError("content exceeds 10 MB limit")
        return v


# ── Terminal ──────────────────────────────────────────────────────────────────
class TerminalExecRequest(BaseModel):
    command: str
    workspace: str

    @field_validator("command")
    @classmethod
    def command_length(cls, v: str) -> str:
        if len(v) > 2000:
            raise ValueError("command exceeds 2 000 character limit")
        return v


class TerminalExecResponse(BaseModel):
    stdout: str
    stderr: str
    returncode: int


# ── Ollama ────────────────────────────────────────────────────────────────────
class OllamaModel(BaseModel):
    name: str
    size: int | None = None
    modified_at: str | None = None


class OllamaSwitchRequest(BaseModel):
    """Request body for POST /ollama/switch."""

    model: str


class OllamaStatusResponse(BaseModel):
    """Response body for GET /ollama/health."""

    ok: bool
    models: list[str]
    active_model: str
    error: str | None = None
