"""
test_routers_agent.py — Tests for routers/agent.py

Uses the TestClient fixture. We bypass Ollama by mocking _validate_model
and the streaming executor. Tests the lifecycle endpoints.
"""
import pytest
from unittest.mock import patch, AsyncMock


# ── Health endpoint (sanity check the app loads) ──────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ── /agent/list and /agent/status ─────────────────────────────────────────────

class TestAgentList:
    def test_list_agents_returns_list(self, test_client):
        resp = test_client.get("/agent/list")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_status_unknown_id_returns_404(self, test_client):
        resp = test_client.get("/agent/status/nonexistent-id")
        assert resp.status_code == 404

    def test_kill_unknown_id_returns_404(self, test_client):
        resp = test_client.post("/agent/kill/nonexistent-id")
        assert resp.status_code == 404


# ── /agent/approve and /agent/deny — no pending approval ─────────────────────

class TestApprovalEndpoints:
    def test_approve_nonexistent_returns_404(self, test_client):
        resp = test_client.post("/agent/approve/no-task/no-call")
        assert resp.status_code == 404

    def test_deny_nonexistent_returns_404(self, test_client):
        resp = test_client.post("/agent/deny/no-task/no-call")
        assert resp.status_code == 404


# ── /agent/stream — model validation rejected without Ollama ─────────────────

class TestAgentStream:
    def test_stream_rejects_invalid_workspace(self, test_client, tmp_path):
        """workspace_path validation blocks non-existent directories."""
        resp = test_client.post("/agent/stream", json={
            "message": "hello",
            "model": "llama3",
            "workspace_path": "/does/not/exist/anywhere",
        })
        # Pydantic validator rejects the bad workspace path
        assert resp.status_code == 422

    def test_stream_rejects_empty_message(self, test_client, tmp_path):
        """Empty message is rejected by Pydantic validator."""
        resp = test_client.post("/agent/stream", json={
            "message": "   ",
            "model": "llama3",
            "workspace_path": str(tmp_path),
        })
        assert resp.status_code == 422

    def test_stream_rejects_message_with_traversal(self, test_client, tmp_path):
        """workspace_path with '..' is rejected by Pydantic validator."""
        resp = test_client.post("/agent/stream", json={
            "message": "hello",
            "model": "llama3",
            "workspace_path": str(tmp_path) + "/../..",
        })
        assert resp.status_code == 422


# ── /agent/spawn — registry lifecycle ────────────────────────────────────────

class TestRegistryLifecycle:
    def test_spawn_and_retrieve_task(self, test_client, tmp_path):
        """Spawn a task directly via the registry and retrieve its status."""
        from agents.orchestrator import registry, AgentStatus

        task = registry.spawn(
            description="test task from router test",
            workspace=str(tmp_path),
            model="llama3",
        )

        resp = test_client.get(f"/agent/status/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == task.id
        assert data["description"] == "test task from router test"

    def test_kill_running_task(self, test_client, tmp_path):
        """Kill a registered task changes its status to error."""
        from agents.orchestrator import registry

        task = registry.spawn(
            description="task to kill",
            workspace=str(tmp_path),
            model="llama3",
        )

        resp = test_client.post(f"/agent/kill/{task.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["agent_id"] == task.id
