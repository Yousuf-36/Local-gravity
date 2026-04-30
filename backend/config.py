"""
config.py — Application settings loaded from environment / .env file.
No secrets are hardcoded here. All values have safe localhost-only defaults.
"""
from pathlib import Path

from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    # Ollama API — must remain on localhost; never expose externally
    ollama_host: str = "http://127.0.0.1:11434"

    # Default model — exact name from `ollama list`
    default_model: str = "gpt-oss:20b"

    # Absolute path to the workspace root (set by Electron when user opens a folder)
    workspace_root: str = ""

    # Maximum file size the backend will read into memory (MB)
    max_file_size_mb: int = 10

    # Seconds before a sandboxed terminal command is force-killed
    terminal_timeout_seconds: int = 30

    # Maximum tokens kept in conversation history before trimming
    max_context_tokens: int = 6000

    # ── Phase 2 additions ────────────────────────────────────────────────────

    # Absolute path to the SQLite database file.
    # Defaults to ~/.localgravity/localgravity.db (created on first run).
    db_path: str = str(Path.home() / ".localgravity" / "localgravity.db")

    # Set to True in production builds to disable Swagger UI (/docs, /redoc).
    # Electron IPC is the only intended client — docs are a security surface.
    production: bool = False

    # Seconds of inactivity before a PTY session is evicted from memory.
    # Lower values conserve memory; higher values preserve cd state longer.
    pty_idle_timeout_seconds: int = 1800  # 30 minutes


    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
