"""Офлайн/макетные проверки разрешённых DO-профилей и безопасного запуска."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from questa_mcp.approved import (
    CONFIG_ENV, _execute, _load_approved_profiles, list_approved_projects,
    run_approved_project,
)


class FakeStream:
    def __init__(self, data: bytes):
        self.data = data

    async def read(self, _: int) -> bytes:
        if self.data:
            data, self.data = self.data, b""
            return data
        return b""


class FakeProcess:
    def __init__(self, output: bytes, code: int = 0):
        self.stdout = FakeStream(output)
        self.returncode = None
        self.code = code
        self.pid = 987654

    async def wait(self) -> int:
        self.returncode = self.code
        return self.code

    def kill(self) -> None:
        self.returncode = -9


class ApprovedProjectsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "workspace"
        self.root.mkdir()
        self.script = self.root / "run.do"
        self.script.write_text("run -all\nquit -f\n", encoding="utf-8")
        self.executable = base / ("vsim.exe" if os.name == "nt" else "vsim")
        self.executable.write_text("mock (never run)", encoding="utf-8")
        self.config = base / "approved.json"
        self.profile = {
            "workspace": str(self.root),
            "executable": str(self.executable),
            "do_script": "run.do",
            "do_sha256": hashlib.sha256(self.script.read_bytes()).hexdigest(),
            "operator_approved": True,
            "disposable_workspace": True,
            "timeout_seconds": 10,
        }
        self.write_config()
        patcher = patch.dict(os.environ, {CONFIG_ENV: str(self.config)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_config(self):
        self.config.write_text(
            json.dumps({"projects": {"smoke": self.profile}}), encoding="utf-8"
        )

    async def test_allowlisted_process_with_no_test_pass(self):
        fake = FakeProcess(b"# ** Warning: (vsim-3020) no checks\n", 0)
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
            spawn.return_value = fake
            result = await run_approved_project("smoke")
        self.assertEqual(result["status"], "COMPLETED_UNVERIFIED")
        self.assertTrue(result["eda_executed"])
        self.assertEqual(result["test_verdict"], "UNKNOWN")
        self.assertEqual(result["diagnostics"], [])
        args, kwargs = spawn.call_args
        self.assertEqual(args[:3], (str(self.executable), "-c", "-do"))
        self.assertEqual(args[3], str(self.script))
        self.assertEqual(kwargs["cwd"], str(self.root))
        self.assertNotIn("shell", kwargs)

    async def test_fatal_failure_and_license_evidence(self):
        fake = FakeProcess(b"** Fatal: (vsim-3825) assertion failed\n", 1)
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
            spawn.return_value = fake
            result = await run_approved_project("smoke")
        self.assertEqual(result["status"], "PROCESS_FAILED")
        self.assertEqual(result["test_verdict"], "FAIL")
        self.assertEqual(result["exit_code"], 1)
        fake = FakeProcess(b"** Error: License checkout failed\n", 1)
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
            spawn.return_value = fake
            result = await run_approved_project("smoke")
        self.assertEqual(result["status"], "LICENSE_ERROR_EVIDENCE")

    async def test_default_deny_and_no_config(self):
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
            for name in ("unapproved", "../smoke", "-do", "", "x" * 100):
                result = await run_approved_project(name)
                self.assertEqual(result["status"], "DENIED")
            spawn.assert_not_called()
        with patch.dict(os.environ, {CONFIG_ENV: ""}):
            result = await run_approved_project("smoke")
            self.assertEqual(result["status"], "NOT_CONFIGURED")
            self.assertFalse(result["eda_executed"])
            self.assertEqual(list_approved_projects()["projects"], [])

    async def test_hash_mismatch_blocks_execution(self):
        self.script.write_text("quit -f\n", encoding="utf-8")
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
            result = await run_approved_project("smoke")
            self.assertEqual(result["status"], "DO_HASH_MISMATCH")
            spawn.assert_not_called()

    async def test_symlink_escape_and_parent_traversal(self):
        self.profile["do_script"] = "../outside.do"
        self.write_config()
        self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
        self.profile["do_script"] = "run.do"
        if (self.root / "linked.do").exists():
            (self.root / "linked.do").unlink()
        try:
            (self.root / "linked.do").symlink_to(self.script)
        except (OSError, NotImplementedError):
            return
        self.profile["do_script"] = "linked.do"
        self.write_config()
        self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")

    async def test_disposable_and_manual_approval_required(self):
        for name in ("operator_approved", "disposable_workspace"):
            self.profile[name] = False
            self.write_config()
            self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
            self.profile[name] = True

    async def test_output_limit_is_bounded_and_process_killed(self):
        self.profile["max_output_bytes"] = 1024
        self.write_config()
        fake = FakeProcess(b"x" * 2048)
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn, patch(
            "questa_mcp.approved._kill_tree", new_callable=AsyncMock
        ) as kill:
            spawn.return_value = fake
            result = await run_approved_project("smoke")
            kill.assert_awaited_once()
        self.assertEqual(result["status"], "OUTPUT_LIMIT")
        self.assertFalse(result["log_complete"])
        self.assertEqual(result["captured_bytes"], 1024)

    async def test_timeout_status_and_kill(self):
        profile = _load_approved_profiles()["smoke"]
        class SlowStream:
            async def read(self, _):
                raise TimeoutError
        fake = FakeProcess(b"")
        fake.stdout = SlowStream()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn, patch(
            "questa_mcp.approved._kill_tree", new_callable=AsyncMock
        ) as kill:
            spawn.return_value = fake
            status, _, _ = await _execute(profile)
            kill.assert_awaited_once()
        self.assertEqual(status, "TIMEOUT")


if __name__ == "__main__":
    unittest.main()
