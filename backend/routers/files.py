"""
routers/files.py — Workspace file system endpoints.

All paths are validated through safe_resolve() before any fs operation.
File size is capped at settings.max_file_size_mb to prevent memory exhaustion.

Endpoints:
  GET  /files/tree   — workspace directory tree (recursive)
  GET  /files/read   — read a single file's contents
  POST /files/write  — write content to a file (creates dirs as needed)
"""
import os
from pathlib import Path

from fastapi import APIRouter, Query

from config import settings
from models.schemas import FileWriteRequest
from security.terminal import safe_resolve

router = APIRouter()


def _build_tree(root: Path, base: Path) -> dict:
    """Recursively build a JSON-serialisable directory tree."""
    node: dict = {"name": root.name, "path": str(root.relative_to(base))}
    if root.is_dir():
        node["type"] = "directory"
        try:
            children = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            node["children"] = [_build_tree(child, base) for child in children]
        except PermissionError:
            node["children"] = []
    else:
        node["type"] = "file"
        node["size"] = root.stat().st_size
    return node


@router.get("/tree")
async def get_file_tree(workspace: str = Query(..., description="Absolute workspace path")) -> dict:
    """Return the full directory tree for the given workspace."""
    workspace_path = Path(workspace).resolve()
    if not workspace_path.is_dir():
        raise ValueError(f"Workspace path is not a directory: {workspace}")
    return _build_tree(workspace_path, workspace_path)


@router.get("/read")
async def read_file(
    workspace: str = Query(...),
    path: str = Query(..., description="Path relative to workspace root"),
) -> dict:
    """Read a file's contents. Capped at max_file_size_mb."""
    target = safe_resolve(workspace, path)
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    size = target.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"File size ({size / 1024 / 1024:.1f} MB) exceeds limit "
            f"({settings.max_file_size_mb} MB). Open in an external editor."
        )

    content = target.read_text(encoding="utf-8", errors="replace")
    return {
        "path": path,
        "content": content,
        "size": size,
        "language": _infer_language(target.suffix),
    }


@router.post("/write")
async def write_file(req: FileWriteRequest) -> dict:
    """Write content to a file, creating parent directories if needed."""
    target = safe_resolve(req.workspace, req.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(req.content, encoding="utf-8")
    return {"ok": True, "path": req.path, "size": len(req.content.encode())}


# ── Helpers ───────────────────────────────────────────────────────────────────
_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",      ".ts": "typescript",   ".tsx": "typescriptreact",
    ".js": "javascript",  ".jsx": "javascriptreact", ".json": "json",
    ".md": "markdown",    ".html": "html",        ".css": "css",
    ".sh": "shell",       ".yaml": "yaml",        ".yml": "yaml",
    ".toml": "toml",      ".env": "dotenv",       ".sql": "sql",
    ".rs": "rust",        ".go": "go",            ".cpp": "cpp",
    ".c": "c",            ".txt": "plaintext",
}


def _infer_language(suffix: str) -> str:
    return _LANGUAGE_MAP.get(suffix.lower(), "plaintext")
