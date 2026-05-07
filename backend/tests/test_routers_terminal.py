"""
test_routers_terminal.py — Tests for routers/terminal.py

Coverage:
  POST /terminal/exec — allowed command executes, denylist command blocked,
                        dangerous pattern blocked, empty workspace rejected
  GET  /terminal/sessions — returns list of sessions
  DELETE /terminal/sessions/{hash} — 404 for unknown hash
"""
import pytest


class TestTerminalExec:
    def test_exec_allowlisted_command(self, test_client, temp_workspace):
        """git --version is allowlisted and available cross-platform."""
        resp = test_client.post(
            "/terminal/exec",
            json={
                "workspace": str(temp_workspace),
                "command": "git --version",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # returncode 0 means success
        assert data["returncode"] == 0

    def test_exec_denylist_blocked(self, test_client, temp_workspace):
        """rm is on the denylist and must return 400."""
        resp = test_client.post(
            "/terminal/exec",
            json={
                "workspace": str(temp_workspace),
                "command": "rm -rf .",
            },
        )
        assert resp.status_code == 400
        assert "denylist" in resp.json()["error"].lower()

    def test_exec_dangerous_pattern_blocked(self, test_client, temp_workspace):
        """Shell injection via semicolon must be blocked."""
        resp = test_client.post(
            "/terminal/exec",
            json={
                "workspace": str(temp_workspace),
                "command": "git status; rm -rf .",
            },
        )
        assert resp.status_code == 400

    def test_exec_command_too_long(self, test_client, temp_workspace):
        """Commands over 2000 chars fail Pydantic validation → 422."""
        resp = test_client.post(
            "/terminal/exec",
            json={
                "workspace": str(temp_workspace),
                "command": "git " + "a" * 2001,
            },
        )
        assert resp.status_code == 422

    def test_exec_unknown_command_not_allowlisted(self, test_client, temp_workspace):
        """Commands not in the allowlist are rejected with 400."""
        resp = test_client.post(
            "/terminal/exec",
            json={
                "workspace": str(temp_workspace),
                "command": "nmap -sV localhost",
            },
        )
        assert resp.status_code == 400


class TestTerminalSessions:
    def test_list_sessions_returns_list(self, test_client):
        resp = test_client.get("/terminal/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_delete_unknown_session_returns_404(self, test_client):
        resp = test_client.delete("/terminal/sessions/deadbeef")
        assert resp.status_code == 404
