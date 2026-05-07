"""
test_tools.py — Tests for agents/tools.py

Coverage:
  ReadFileTool  — reads file correctly, fails gracefully on missing file
  WriteFileTool — destructive=True, writes content, blocks path traversal
  RunTerminalTool — destructive=True, executes ls, blocks rm from denylist
  ListFilesTool — returns tree structure
  All tools have name, description, input_schema defined
"""
import pytest
import pytest_asyncio


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def registry():
    """Return a fresh ToolRegistry (not the global singleton) for isolation."""
    from agents.tools import (
        ReadFileTool,
        WriteFileTool,
        RunTerminalTool,
        ListFilesTool,
        ToolRegistry,
    )
    reg = ToolRegistry()
    reg.register(ReadFileTool())
    reg.register(WriteFileTool())
    reg.register(RunTerminalTool())
    reg.register(ListFilesTool())
    return reg


@pytest.fixture
def workspace(tmp_path):
    """Temp workspace with hello.py, README.md, data.json."""
    (tmp_path / "hello.py").write_text('print("hello")\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    (tmp_path / "data.json").write_text('{"x": 1}\n', encoding="utf-8")
    return tmp_path


# ── Tool metadata invariants ──────────────────────────────────────────────────

class TestToolMetadata:
    """Every tool must expose name, description, and input_schema."""

    def test_read_file_has_metadata(self):
        from agents.tools import ReadFileTool
        t = ReadFileTool()
        assert isinstance(t.name, str) and t.name
        assert isinstance(t.description, str) and t.description
        assert isinstance(t.input_schema, dict)

    def test_write_file_has_metadata(self):
        from agents.tools import WriteFileTool
        t = WriteFileTool()
        assert isinstance(t.name, str) and t.name
        assert isinstance(t.description, str) and t.description
        assert isinstance(t.input_schema, dict)

    def test_run_terminal_has_metadata(self):
        from agents.tools import RunTerminalTool
        t = RunTerminalTool()
        assert isinstance(t.name, str) and t.name
        assert isinstance(t.description, str) and t.description
        assert isinstance(t.input_schema, dict)

    def test_list_files_has_metadata(self):
        from agents.tools import ListFilesTool
        t = ListFilesTool()
        assert isinstance(t.name, str) and t.name
        assert isinstance(t.description, str) and t.description
        assert isinstance(t.input_schema, dict)


# ── ReadFileTool ──────────────────────────────────────────────────────────────

class TestReadFileTool:
    @pytest.mark.asyncio
    async def test_reads_file_correctly(self, workspace):
        from agents.tools import ReadFileTool
        tool = ReadFileTool()
        result = await tool.execute({"path": "hello.py"}, str(workspace))
        assert 'print("hello")' in result

    @pytest.mark.asyncio
    async def test_fails_gracefully_on_missing_file(self, workspace):
        from agents.tools import ReadFileTool
        tool = ReadFileTool()
        with pytest.raises(ValueError, match="Not a file"):
            await tool.execute({"path": "nonexistent.py"}, str(workspace))

    def test_not_destructive(self):
        from agents.tools import ReadFileTool
        assert ReadFileTool.destructive is False


# ── WriteFileTool ─────────────────────────────────────────────────────────────

class TestWriteFileTool:
    def test_flagged_destructive(self):
        from agents.tools import WriteFileTool
        assert WriteFileTool.destructive is True

    @pytest.mark.asyncio
    async def test_writes_content_and_persists(self, workspace):
        from agents.tools import WriteFileTool
        tool = WriteFileTool()
        content = "x = 42\n"
        result = await tool.execute({"path": "new_file.py", "content": content}, str(workspace))
        assert "new_file.py" in result
        assert (workspace / "new_file.py").read_text() == content

    @pytest.mark.asyncio
    async def test_blocks_path_traversal(self, workspace):
        from agents.tools import WriteFileTool
        tool = WriteFileTool()
        with pytest.raises(PermissionError, match="escapes workspace root"):
            await tool.execute(
                {"path": "../evil.py", "content": "malicious"},
                str(workspace),
            )


# ── RunTerminalTool ───────────────────────────────────────────────────────────

class TestRunTerminalTool:
    def test_flagged_destructive(self):
        from agents.tools import RunTerminalTool
        assert RunTerminalTool.destructive is True

    @pytest.mark.asyncio
    async def test_executes_allowlisted_command_returns_output(self, workspace):
        from agents.tools import RunTerminalTool
        tool = RunTerminalTool()
        # `python3` is allowlisted and available cross-platform; `ls` does not
        # exist as a standalone binary on Windows.
        result = await tool.execute({"command": "python3 --version"}, str(workspace))
        # At minimum returncode should be present in the output
        assert "returncode" in result

    @pytest.mark.asyncio
    async def test_blocks_rm_from_denylist(self, workspace):
        from agents.tools import RunTerminalTool
        tool = RunTerminalTool()
        with pytest.raises(ValueError, match="denylist"):
            await tool.execute({"command": "rm -rf ."}, str(workspace))


# ── ListFilesTool ─────────────────────────────────────────────────────────────

class TestListFilesTool:
    @pytest.mark.asyncio
    async def test_returns_tree_structure(self, workspace):
        from agents.tools import ListFilesTool
        tool = ListFilesTool()
        result = await tool.execute({}, str(workspace))
        # Should include the workspace root path
        assert str(workspace) in result
        # Should include one of our sample files
        assert "hello.py" in result

    @pytest.mark.asyncio
    async def test_lists_known_files(self, workspace):
        from agents.tools import ListFilesTool
        tool = ListFilesTool()
        result = await tool.execute({}, str(workspace))
        assert "README.md" in result
        assert "data.json" in result
