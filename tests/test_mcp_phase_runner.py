"""Настоящий MCP-клиент вызывает ограниченную последовательную регрессию."""

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


class _Stream:
    async def read(self, _: int) -> bytes:
        return b""


class _Process:
    def __init__(self):
        self.pid = 918373
        self.stdout = _Stream()
        self.returncode = None

    async def wait(self):
        self.returncode = 0
        return 0

    def kill(self):
        self.returncode = -9


class PhaseMCPContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_tools_call_executes_only_approved_steps(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            work = root / "work"
            work.mkdir()
            exe = root / ("vsim.exe" if os.name == "nt" else "vsim")
            exe.write_bytes(b"public synthetic executable")
            scripts = {}
            for phase in ("default", "compile", "elaboration", "simulation"):
                path = work / (phase + ".do")
                path.write_bytes(phase.encode("utf-8"))
                scripts[phase] = path
            profile = {
                "workspace": str(work), "executable": str(exe),
                "executable_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
                "do_script": "default.do",
                "do_sha256": hashlib.sha256(scripts["default"].read_bytes()).hexdigest(),
                "operator_approved": True, "disposable_workspace": True,
                "checker": {"format": "cocotb-junit-v1", "expected_tests": ["smoke"]},
                "regression_seeds": [123],
                "phase_scripts": {
                    phase: {
                        "do_script": phase + ".do",
                        "do_sha256": hashlib.sha256(scripts[phase].read_bytes()).hexdigest(),
                    }
                    for phase in ("compile", "elaboration", "simulation")
                },
            }
            config = root / "config.json"
            config.write_text(json.dumps({"projects": {"public-smoke": profile}}), encoding="utf-8")
            invoked = []

            async def spawn(*args, **kwargs):
                phase = Path(args[3]).read_text(encoding="utf-8")
                invoked.append((phase, kwargs["env"]["QUESTA_MCP_SEED"]))
                if phase == "simulation":
                    Path(kwargs["env"]["COCOTB_RESULTS_FILE"]).write_bytes(
                        b'<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
                        b'<testcase name="smoke"/></testsuite></testsuites>'
                    )
                return _Process()

            with patch.dict(os.environ, {CONFIG_ENV: str(config)}), patch(
                "questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn
            ):
                async with Client(create_server()) as client:
                    tools = await client.list_tools()
                    self.assertIn("run_approved_regression", {t.name for t in tools.tools})
                    result = await client.call_tool(
                        "run_approved_regression", {"project_id": "public-smoke"}
                    )
                    self.assertFalse(result.is_error)
                    report = result.structured_content
                    self.assertEqual(report["test_count"], 1)
                    self.assertEqual(report["regression_verdict"], "UNKNOWN")
                    self.assertEqual(report["runs"][0]["checker_verdict"], "PASS")
                    self.assertEqual(report["runs"][0]["test_verdict"], "UNKNOWN")
                    denied = await client.call_tool(
                        "run_approved_regression", {"project_id": "../../../etc"}
                    )
                    self.assertFalse(denied.is_error)
                    self.assertEqual(denied.structured_content["status"], "DENIED")
            self.assertEqual(invoked, [
                ("compile", "123"), ("elaboration", "123"), ("simulation", "123")
            ])


if __name__ == "__main__":
    unittest.main()
