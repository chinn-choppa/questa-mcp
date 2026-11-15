"""Реальный MCP-клиент (in-process и stdio) на нативном pytest."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

from questa_mcp.server import create_server


def test_in_process_real_calls():
    async def scenario():
        async with Client(create_server()) as client:
            listed = await client.list_tools()
            assert {item.name for item in listed.tools} == {
                "server_info", "tool_status", "parse_diagnostics"}
            info = await client.call_tool("server_info", {})
            assert info.is_error is False
            assert info.structured_content["eda_execution_supported"] is False
            parsed = await client.call_tool("parse_diagnostics", {
                "text": "** Fatal: (vsim-3825) tb.sv(17): assertion failure",
                "tool": "vsim",
            })
            assert parsed.is_error is False
            assert parsed.structured_content["test_verdict"] == "FAIL"
            assert parsed.structured_content["items"][0]["line"] == 17
            rejected = await client.call_tool("parse_diagnostics", {"text": "none", "limit": 0})
            assert rejected.is_error is True

    asyncio.run(scenario())


def test_stdio_real_calls():
    async def scenario():
        root = Path(__file__).resolve().parents[1]
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "questa_mcp"],
            env={"PYTHONPATH": str(root / "src")},
        )
        async with Client(params) as client:
            listed = await client.list_tools()
            assert "parse_diagnostics" in {item.name for item in listed.tools}
            parsed = await client.call_tool("parse_diagnostics", {
                "text": "# ** Warning: (vlog-2240) a.sv(5): connection mismatch",
                "tool": "vlog",
            })
            assert parsed.is_error is False
            assert parsed.structured_content["items"][0]["code"] == "vlog-2240"
            assert parsed.structured_content["test_verdict"] == "UNKNOWN"
            rejected = await client.call_tool("parse_diagnostics", {
                "text": "x", "tool": "bash",
            })
            assert rejected.is_error is True

    asyncio.run(scenario())
