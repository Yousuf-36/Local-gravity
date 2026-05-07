"""
test_executor.py — Tests for agents/executor.py

Uses the mock_ollama fixture to avoid real Ollama calls.
Covers frame builders, helper functions, and the core loop.
"""
import json
import pytest
import pytest_asyncio
import sys, os

# Ensure backend is on path
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Import canned SSE lines defined in conftest
from tests.conftest import _TOOL_CALL_LINE, _FINAL_ANSWER_LINE


# ── Frame builder unit tests ──────────────────────────────────────────────────

class TestFrameBuilders:
    def test_plan_frame_shape(self):
        from agents.executor import _plan_frame
        f = _plan_frame("task1", "Do the thing")
        assert f["type"] == "plan"
        assert f["task_id"] == "task1"
        assert f["content"] == "Do the thing"

    def test_tool_call_frame_shape(self):
        from agents.executor import _tool_call_frame
        f = _tool_call_frame("t1", "c1", "read_file", {"path": "a.py"}, False)
        assert f["type"] == "tool_call"
        assert f["tool"] == "read_file"
        assert f["destructive"] is False

    def test_tool_result_frame_shape(self):
        from agents.executor import _tool_result_frame
        f = _tool_result_frame("t1", "c1", "output text", 0, False)
        assert f["type"] == "tool_result"
        assert f["output"] == "output text"
        assert f["truncated"] is False
        assert f["returncode"] == 0

    def test_final_answer_frame_shape(self):
        from agents.executor import _final_answer_frame
        f = _final_answer_frame("t1", "The answer", 3)
        assert f["type"] == "final_answer"
        assert f["content"] == "The answer"
        assert f["steps_used"] == 3

    def test_error_frame_shape(self):
        from agents.executor import _error_frame
        f = _error_frame("t1", "step_limit", "Too many steps")
        assert f["type"] == "error"
        assert f["code"] == "step_limit"
        assert "Too many steps" in f["message"]

    def test_waiting_approval_frame_shape(self):
        from agents.executor import _waiting_approval_frame
        f = _waiting_approval_frame("t1", "c1", "write_file", {"path": "x.py"}, "Write 10 bytes to x.py")
        assert f["type"] == "waiting_approval"
        assert f["tool"] == "write_file"
        assert f["summary"] == "Write 10 bytes to x.py"


# ── Helper function tests ─────────────────────────────────────────────────────

class TestSanitizeToolOutput:
    def test_short_output_not_truncated(self):
        from agents.executor import _sanitize_tool_output
        result, truncated = _sanitize_tool_output("hello", "read_file")
        assert not truncated
        assert "hello" in result
        assert '<tool_result name="read_file">' in result

    def test_long_output_is_truncated(self):
        from agents.executor import _sanitize_tool_output, _MAX_TOOL_OUTPUT_CHARS
        big = "x" * (_MAX_TOOL_OUTPUT_CHARS + 100)
        result, truncated = _sanitize_tool_output(big, "read_file")
        assert truncated
        assert "TRUNCATED" in result


class TestParseToolArgs:
    def test_dict_passthrough(self):
        from agents.executor import _parse_tool_args
        result = _parse_tool_args({"path": "a.py", "content": "hello"})
        assert result == {"path": "a.py", "content": "hello"}

    def test_json_string_parsed(self):
        from agents.executor import _parse_tool_args
        result = _parse_tool_args('{"path": "b.py"}')
        assert result == {"path": "b.py"}

    def test_invalid_json_returns_empty(self):
        from agents.executor import _parse_tool_args
        result = _parse_tool_args("not json at all")
        assert result == {}

    def test_none_returns_empty(self):
        from agents.executor import _parse_tool_args
        result = _parse_tool_args(None)
        assert result == {}


class TestBuildApprovalSummary:
    def test_write_file_summary(self):
        from agents.executor import _build_approval_summary
        s = _build_approval_summary("write_file", {"path": "x.py", "content": "abc"})
        assert "x.py" in s
        assert "bytes" in s

    def test_run_terminal_summary(self):
        from agents.executor import _build_approval_summary
        s = _build_approval_summary("run_terminal", {"command": "pytest tests/"})
        assert "pytest tests/" in s

    def test_unknown_tool_summary(self):
        from agents.executor import _build_approval_summary
        s = _build_approval_summary("unknown_tool", {"foo": "bar"})
        assert "unknown_tool" in s


# ── Core loop integration (mocked Ollama) ────────────────────────────────────

class TestRunExecutor:
    @pytest.mark.asyncio
    async def test_final_answer_frame_emitted(self, mock_ollama, temp_workspace):
        """
        When Ollama returns no tool_calls (second canned frame), the executor
        must emit a final_answer. With the mock, the first canned frame has a
        tool_call (read_file — non-destructive), the second has text content.
        We collect all frames and verify at least one final_answer is present.
        """
        import agents.streamer as streamer_mod

        # The mock_ollama fixture already patches stream_ollama to return the
        # canned SSE. We wire a minimal ToolRegistry.
        from agents.tools import ToolRegistry, ReadFileTool
        from agents.executor import run_executor

        reg = ToolRegistry()
        reg.register(ReadFileTool())

        frames = []
        async for frame in run_executor(
            task_id="test-exec",
            messages=[{"role": "user", "content": "analyse hello.py"}],
            model="llama3",
            workspace=str(temp_workspace),
            registry=reg,
        ):
            frames.append(frame)

        types = [f["type"] for f in frames]
        assert "final_answer" in types, f"Expected final_answer in {types}"

    @pytest.mark.asyncio
    async def test_tool_call_frame_emitted(self, temp_workspace, monkeypatch):
        """
        The executor emits a tool_call frame when Ollama returns tool_calls.
        We use a two-phase mock: step 1 → tool_call, step 2 → final_answer.
        """
        import agents.executor as executor_mod

        _call_count = {"n": 0}

        async def _two_phase_stream(messages, *, model, tools=None):
            _call_count["n"] += 1
            if _call_count["n"] == 1:
                yield _TOOL_CALL_LINE
            else:
                yield _FINAL_ANSWER_LINE

        monkeypatch.setattr(executor_mod, "stream_ollama", _two_phase_stream)

        from agents.tools import ToolRegistry, ReadFileTool
        from agents.executor import run_executor

        reg = ToolRegistry()
        reg.register(ReadFileTool())

        frames = []
        async for frame in run_executor(
            task_id="test-tc",
            messages=[{"role": "user", "content": "read file"}],
            model="llama3",
            workspace=str(temp_workspace),
            registry=reg,
        ):
            frames.append(frame)

        types = [f["type"] for f in frames]
        assert "tool_call" in types, f"Expected tool_call in {types}"
