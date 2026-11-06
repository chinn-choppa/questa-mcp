"""MCP contract test for read-only approved waveform/coverage manifest."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from questa_mcp.approved import CONFIG_ENV
from questa_mcp.server import create_server


class ArtifactMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_call_only_reports_allowlisted_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            script = workspace / "run.do"
            script.write_bytes(b"run -all\nquit -f\n")
            binary = root / ("vsim.exe" if os.name == "nt" else "vsim")
            binary.write_bytes(b"synthetic binary, not an installed Siemens tool")
            wave = workspace / "counter.vcd"
            wave.write_bytes(
                b"$timescale 1ns $end\n$scope module tb $end\n"
                b"$var wire 1 ! clk $end\n$upscope $end\n$enddefinitions $end\n"
                b"#0\n0!\n#10\n1!\n"
            )
            config = root / "projects.json"
            config.write_text(json.dumps({"projects": {"public": {
                "workspace": str(workspace), "executable": str(binary),
                "do_script": "run.do",
                "do_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
                "operator_approved": True, "disposable_workspace": True,
                "artifacts": [{"id": "clock_wave", "path": "counter.vcd", "format": "vcd",
                               "declared_time_unit": "ns"}],
            }}}), encoding="utf-8")
            with patch.dict(os.environ, {CONFIG_ENV: str(config)}):
                async with Client(create_server()) as client:
                    tools = await client.list_tools()
                    self.assertIn("list_approved_artifacts", {t.name for t in tools.tools})
                    result = await client.call_tool(
                        "list_approved_artifacts", {"project_id": "public"}
                    )
                    self.assertFalse(result.is_error)
                    body = result.structured_content
                    self.assertEqual(body["count"], 1)
                    self.assertFalse(body["eda_executed"])
                    artifact = body["items"][0]
                    self.assertEqual(artifact["state"], "HASHED")
                    self.assertEqual(artifact["format"], "VCD")
                    self.assertIsNone(artifact["local_path"])
                    self.assertFalse(artifact["format_validated"])
                    self.assertEqual(artifact["external_execution"], "NOT_RUN")
                    self.assertIsNone(artifact["produced_by_run_id"])
                    self.assertEqual(
                        artifact["sha256"], hashlib.sha256(wave.read_bytes()).hexdigest()
                    )
                    bad = await client.call_tool(
                        "list_approved_artifacts", {"project_id": "../public"}
                    )
                    self.assertFalse(bad.is_error)
                    self.assertEqual(bad.structured_content["state"], "DENIED")
                    self.assertEqual(bad.structured_content["items"], [])


if __name__ == "__main__":
    unittest.main()
