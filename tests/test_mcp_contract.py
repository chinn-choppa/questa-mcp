"""Контрактные тесты настоящего MCP-клиента: in-process и stdio."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mcp import Client, StdioServerParameters

from questa_mcp.server import create_server


class MCPContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_in_process_real_calls(self):
        async with Client(create_server()) as client:
            listed = await client.list_tools()
            names = {item.name for item in listed.tools}
            self.assertEqual(names, {"server_info", "tool_status", "parse_diagnostics",
                             "list_approved_projects", "run_approved_project"})
            info = await client.call_tool("server_info", {})
            self.assertFalse(info.is_error)
            self.assertFalse(info.structured_content["eda_execution_supported"])
            parsed = await client.call_tool("parse_diagnostics", {
                "text": "** Fatal: (vsim-3825) tb.sv(17): assertion failure",
                "tool": "vsim",
            })
            self.assertFalse(parsed.is_error)
            self.assertEqual(parsed.structured_content["test_verdict"], "FAIL")
            self.assertEqual(parsed.structured_content["items"][0]["line"], 17)
            denied = await client.call_tool("run_approved_project", {"project_id": "missing"})
            self.assertFalse(denied.is_error)
            self.assertIn(denied.structured_content["status"], {"NOT_CONFIGURED", "DENIED"})
            rejected = await client.call_tool("parse_diagnostics", {
                "text": "none", "limit": 0,
            })
            self.assertTrue(rejected.is_error)

    async def test_stdio_real_calls(self):
        root = Path(__file__).resolve().parents[1]
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "questa_mcp"],
            env={"PYTHONPATH": str(root / "src")},
        )
        async with Client(params) as client:
            listed = await client.list_tools()
            self.assertIn("parse_diagnostics", {item.name for item in listed.tools})
            parsed = await client.call_tool("parse_diagnostics", {
                "text": "# ** Warning: (vlog-2240) a.sv(5): connection mismatch",
                "tool": "vlog",
            })
            self.assertFalse(parsed.is_error)
            self.assertEqual(parsed.structured_content["items"][0]["code"], "vlog-2240")
            self.assertEqual(parsed.structured_content["test_verdict"], "UNKNOWN")
            rejected = await client.call_tool("parse_diagnostics", {
                "text": "x", "tool": "bash",
            })
            self.assertTrue(rejected.is_error)
