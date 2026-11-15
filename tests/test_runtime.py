"""Discovery без запуска EDA: изолированные pytest fixtures."""
from pathlib import Path

from questa_mcp.runtime import inspect_tool


TOOL = "vsim"
ENV = "QUESTA_MCP_EXECUTABLE"


def test_empty_override(monkeypatch):
    monkeypatch.setenv(ENV, "")
    result = inspect_tool(TOOL, ENV)
    assert result["state"] == "INVALID_OVERRIDE"
    assert result["executed"] is False
    assert "path" not in result


def test_explicit_existing_executable(monkeypatch, tmp_path: Path):
    path = tmp_path / "fake-tool"
    path.write_text("not a real EDA executable", encoding="utf-8")
    monkeypatch.setenv(ENV, str(path))
    result = inspect_tool(TOOL, ENV)
    assert result["state"] == "DETECTED_UNVERIFIED"
    assert result["configured"] is True
    assert result["executed"] is False


def test_missing_tool_in_path(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.setattr("questa_mcp.runtime.shutil.which", lambda _: None)
    result = inspect_tool(TOOL, ENV)
    assert result["state"] == "NOT_FOUND"
    assert result["configured"] is False


def test_path_tool_discovery(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.setattr("questa_mcp.runtime.shutil.which", lambda _: "/tmp/eda")
    result = inspect_tool(TOOL, ENV)
    assert result["state"] == "DETECTED_UNVERIFIED"
    assert result["executed"] is False
