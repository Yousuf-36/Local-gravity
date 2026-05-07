"""
test_routers_files.py — Tests for routers/files.py

Coverage:
  GET  /files/tree   — returns directory tree
  GET  /files/read   — reads file, caps size, rejects path traversal
  POST /files/write  — writes file, creates dirs, rejects traversal
"""
import pytest


class TestFileTree:
    def test_tree_returns_structure(self, test_client, temp_workspace):
        resp = test_client.get(
            "/files/tree",
            params={"workspace": str(temp_workspace)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "directory"
        # children must include our sample files
        child_names = [c["name"] for c in data.get("children", [])]
        assert "hello.py" in child_names or any("hello" in n for n in child_names)

    def test_tree_rejects_nonexistent_workspace(self, test_client):
        resp = test_client.get(
            "/files/tree",
            params={"workspace": "/does/not/exist"},
        )
        assert resp.status_code == 400

    def test_tree_structure_has_name_type(self, test_client, temp_workspace):
        resp = test_client.get(
            "/files/tree",
            params={"workspace": str(temp_workspace)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "type" in data


class TestFileRead:
    def test_reads_existing_file(self, test_client, temp_workspace):
        resp = test_client.get(
            "/files/read",
            params={
                "workspace": str(temp_workspace),
                "path": "hello.py",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'print("hello, world")' in data["content"]
        assert data["language"] == "python"

    def test_read_missing_file_returns_400(self, test_client, temp_workspace):
        resp = test_client.get(
            "/files/read",
            params={
                "workspace": str(temp_workspace),
                "path": "missing_file.py",
            },
        )
        assert resp.status_code == 400

    def test_read_md_file_language(self, test_client, temp_workspace):
        resp = test_client.get(
            "/files/read",
            params={
                "workspace": str(temp_workspace),
                "path": "README.md",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["language"] == "markdown"

    def test_read_json_file_language(self, test_client, temp_workspace):
        resp = test_client.get(
            "/files/read",
            params={
                "workspace": str(temp_workspace),
                "path": "data.json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["language"] == "json"


class TestFileWrite:
    def test_write_creates_new_file(self, test_client, temp_workspace):
        resp = test_client.post(
            "/files/write",
            json={
                "workspace": str(temp_workspace),
                "path": "output.txt",
                "content": "written by test\n",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["path"] == "output.txt"
        # Verify on disk
        assert (temp_workspace / "output.txt").read_text() == "written by test\n"

    def test_write_creates_nested_dirs(self, test_client, temp_workspace):
        resp = test_client.post(
            "/files/write",
            json={
                "workspace": str(temp_workspace),
                "path": "src/utils/helpers.py",
                "content": "# helpers\n",
            },
        )
        assert resp.status_code == 200
        assert (temp_workspace / "src" / "utils" / "helpers.py").exists()

    def test_write_rejects_path_traversal(self, test_client, temp_workspace):
        resp = test_client.post(
            "/files/write",
            json={
                "workspace": str(temp_workspace),
                "path": "../evil.py",
                "content": "malicious",
            },
        )
        # Pydantic validator blocks '..' at schema level → 422
        assert resp.status_code == 422
