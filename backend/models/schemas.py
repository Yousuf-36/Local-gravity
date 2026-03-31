"""
schemas.py — All Pydantic request/response models for the LocalGravity API.

Every endpoint uses these models for input validation and output serialisation.
Field validators block path traversal and model-name injection at the boundary.
"""
import os
from typing import Literal

from pydantic import BaseModel, field_validator

# ── Allowed Ollama models ─────────────────────────────────────────────────────
ALLOWED_MODELS: set[str] = {"gpt-oss:20b", "llama3", "deepseek-coder", "qwen2.5-coder", "mistral"}


# ── Agent ─────────────────────────────────────────────────────────────────────
class AgentRequest(BaseModel):
    message: str
    model: str = "gpt-oss:20b"
    workspace_path: str
    session_id: str = "default"

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be empty")
        if len(v) > 32_000:
            raise ValueError("message exceeds 32 000 character limit")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v not in ALLOWED_MODELS:
            raise ValueError(f"Model '{v}' not in allowlist: {ALLOWED_MODELS}")
        return v

    @field_validator("workspace_path")
    @classmethod
    def validate_workspace_path(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("workspace_path must not contain '..'")
        resolved = os.path.realpath(v)
        if not os.path.isdir(resolved):
            raise ValueError(f"workspace_path is not a directory: {resolved}")
        return resolved


class AgentStreamChunk(BaseModel):
    content: str = ""
    done: bool = False
    error: str | None = None


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
    model: str

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v not in ALLOWED_MODELS:
            raise ValueError(f"Model '{v}' not in allowlist: {ALLOWED_MODELS}")
        return v


class OllamaStatusResponse(BaseModel):
    ok: bool
    models: list[str]
    active_model: str
    error: str | None = None
