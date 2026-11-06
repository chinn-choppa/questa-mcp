"""Настоящий MCP tools/call с макетом процесса и новым JUnit XML."""

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


class FakeStream:
    async def read(self, _: int) -> bytes:
        return b""


class FakeProcess:
    pid = 54321
    stdout = FakeStream()
    returncode = None

    async def wait(self) -> int:
        self.returncode = 0
        return 0


class JunitMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_tools_call_returns_only_checker_pass(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            workspace = root / "workspace"
            workspace.mkdir()
            script = workspace / "run.do"
            script.write_bytes(b"run -all\nquit -f\n")
            binary = root / ("vsim.exe" if os.name == "nt" else "vsim")
            binary.write_bytes(b"public synthetic mock")
            config = root / "config.json"
            config.write_text(json.dumps({"projects": {"smoke": {
                "workspace": str(workspace),
                "executable": str(binary),
                "do_script": "run.do",
                "do_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
                "executable_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "operator_approved": True,
                "disposable_workspace": True,
                "checker": {"format": "cocotb-junit-v1", "expected_tests": ["check_counter"]}
            }}}), encoding="utf-8")

            async def spawn(*args, **kwargs):
                dest = Path(kwargs["env"]["COCOTB_RESULTS_FILE"])
                dest.write_bytes(
                    b'<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
                    b'<testcase name="check_counter"/></testsuite></testsuites>'
                )
                return FakeProcess()

            with patch.dict(os.environ, {CONFIG_ENV: str(config)}), patch(
                "questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn
            ):
                async with Client(create_server()) as client:
                    listed = await client.list_tools()
                    self.assertIn("run_approved_project", {x.name for x in listed.tools})
                    good = await client.call_tool("run_approved_project", {"project_id": "smoke"})
                    self.assertFalse(good.is_error)
                    self.assertEqual(good.structured_content["checker_verdict"], "PASS")
                    self.assertEqual(good.structured_content["test_verdict"], "UNKNOWN")
                    self.assertFalse(good.structured_content["vendor_compatibility_verified"])
                    self.assertEqual(good.structured_content["diagnostics"], [])
                    rejected = await client.call_tool(
                        "run_approved_project", {"project_id": "../smoke"}
                    )
                    self.assertFalse(rejected.is_error)
                    self.assertEqual(rejected.structured_content["status"], "DENIED")
                    self.assertFalse(rejected.structured_content["eda_executed"])


if __name__ == "__main__":
    unittest.main()
