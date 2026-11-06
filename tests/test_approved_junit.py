"""Свежие cocotb JUnit-свидетельства от разрешённого процесса: только mock EDA."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from questa_mcp.approved import CONFIG_ENV, list_approved_projects, run_approved_project


def junit(case: str = '<testcase name="check_counter"/>', *, tests: int = 1,
          failures: int = 0, errors: int = 0, skipped: int = 0) -> bytes:
    return (
        '<testsuites name="cocotb tests"><testsuite name="tb_counter" '
        f'tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}">'
        f'{case}</testsuite></testsuites>'
    ).encode("utf-8")


class FakeStream:
    def __init__(self, data: bytes):
        self.data = data

    async def read(self, count: int) -> bytes:
        data, self.data = self.data[:count], self.data[count:]
        return data


class FakeProcess:
    pid = 654321

    def __init__(self, data: bytes = b"", return_code: int = 0):
        self.stdout = FakeStream(data)
        self._code = return_code
        self.returncode: int | None = None

    async def wait(self) -> int:
        self.returncode = self._code
        return self._code

    def kill(self) -> None:
        self.returncode = -9


class ApprovedJunitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.workspace = base / "workspace"
        self.workspace.mkdir()
        self.script = self.workspace / "run.do"
        self.script.write_bytes(b"run -all\nquit -f\n")
        self.executable = base / ("vsim.exe" if os.name == "nt" else "vsim")
        self.executable.write_bytes(b"fake mock executable, never launched")
        self.config = base / "config.json"
        self.entry = {
            "workspace": str(self.workspace),
            "executable": str(self.executable),
            "do_script": "run.do",
            "do_sha256": hashlib.sha256(self.script.read_bytes()).hexdigest(),
            "operator_approved": True,
            "disposable_workspace": True,
            "executable_sha256": hashlib.sha256(self.executable.read_bytes()).hexdigest(),
            "checker": {
                "format": "cocotb-junit-v1",
                "expected_tests": ["check_counter"],
            },
        }
        self.save()
        env = patch.dict(os.environ, {CONFIG_ENV: str(self.config)})
        env.start()
        self.addCleanup(env.stop)

    def save(self):
        self.config.write_text(
            json.dumps({"projects": {"smoke": self.entry}}), encoding="utf-8"
        )

    async def call(self, report: bytes | None, log: bytes = b"", code: int = 0) -> dict[str, object]:
        async def spawn(*args, **kwargs):
            self.assertEqual(args[1:3], ("-c", "-do"))
            self.assertNotIn("shell", kwargs)
            self.assertEqual(kwargs["cwd"], str(self.workspace.resolve()))
            env = kwargs["env"]
            path = Path(env["COCOTB_RESULTS_FILE"])
            self.assertNotEqual(path.parent, self.workspace)
            self.assertFalse(path.exists(), "Нельзя использовать старый отчёт")
            if report is not None:
                path.write_bytes(report)
            return FakeProcess(log, code)

        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            return await run_approved_project("smoke")

    async def test_fresh_expected_checker_pass_does_not_claim_assertion_pass(self):
        got = await self.call(junit())
        self.assertEqual(got["test_verdict"], "UNKNOWN")
        self.assertEqual(got["checker_verdict"], "PASS")
        self.assertEqual(got["assertions_verdict"], "UNKNOWN")
        self.assertEqual(got["regression_verdict"], "UNKNOWN")
        self.assertEqual(got["checker"]["state"], "PASSED")
        self.assertEqual(got["checker"]["tests"], 1)
        self.assertEqual(got["verdict_basis"], "FRESH_JUNIT_CHECKER_PASS_ONLY")
        self.assertFalse(got["vendor_compatibility_verified"])
        self.assertEqual(got["run_provenance"]["approved_do_sha256"], self.entry["do_sha256"])
        self.assertEqual(len(got["checker"]["report_sha256"]), 64)
        self.assertEqual(got["diagnostics"], [])

    async def test_without_fresh_report_or_only_stale_workspace_file_is_unknown(self):
        (self.workspace / "results.xml").write_bytes(junit())
        got = await self.call(None)
        self.assertEqual(got["checker"]["reason"], "REPORT_MISSING")
        self.assertEqual(got["test_verdict"], "UNKNOWN")

    async def test_mock_process_exit_nonzero_overrides_fresh_passing_report(self):
        got = await self.call(junit(), code=1)
        self.assertEqual(got["status"], "PROCESS_FAILED")
        self.assertEqual(got["test_verdict"], "FAIL")
        self.assertEqual(got["checker"]["state"], "PASSED")

    async def test_assertion_log_overrides_report(self):
        got = await self.call(junit(), b"** Fatal: (vsim-3825) assertion failed")
        self.assertEqual(got["status"], "COMPLETED_UNVERIFIED")
        self.assertEqual(got["test_verdict"], "FAIL")

    async def test_incomplete_and_skipped_reports_not_pass(self):
        for data in (
            junit(tests=0),
            junit('<testcase name="check_counter"><skipped/></testcase>', skipped=1),
            junit('<testcase name="another"/>'),
            b"<testsuites>truncated",
            b'<!DOCTYPE x [<!ENTITY x "evil">]><testsuites/>',
        ):
            with self.subTest(report=data[:30]):
                got = await self.call(data)
                self.assertEqual(got["test_verdict"], "UNKNOWN")

    async def test_real_checker_failure_is_fail(self):
        got = await self.call(
            junit(
                '<testcase name="check_counter"><failure message="mismatch"/></testcase>',
                failures=1,
            )
        )
        self.assertEqual(got["checker"]["state"], "FAILED")
        self.assertEqual(got["test_verdict"], "FAIL")

    async def test_no_checker_config_does_not_create_pass(self):
        self.entry.pop("checker")
        self.save()
        async def spawn(*args, **kwargs):
            self.assertNotIn("env", kwargs, "Не менять окружение без утверждённого checker")
            return FakeProcess()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            got = await run_approved_project("smoke")
        self.assertEqual(got["test_verdict"], "UNKNOWN")
        self.assertEqual(got["checker"]["state"], "NOT_CONFIGURED")

    async def test_wrong_checker_configuration_is_denied_before_start(self):
        for kind in ("bash", "", "junit", "cocotb-junit-v2"):
            self.entry["checker"]["format"] = kind
            self.save()
            with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
                self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
                got = await run_approved_project("smoke")
                self.assertEqual(got["status"], "INVALID_CONFIGURATION")
                spawn.assert_not_called()

    async def test_empty_or_duplicate_expected_list_denied(self):
        for names in ([], ["check_counter", "check_counter"], ["..\\another"], [42]):
            self.entry["checker"]["expected_tests"] = names
            self.save()
            self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")

    async def test_executable_hash_must_match_before_process_spawn(self):
        self.executable.write_bytes(b"tampered tool")
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
            got = await run_approved_project("smoke")
            spawn.assert_not_called()
        self.assertEqual(got["status"], "EXECUTABLE_HASH_MISMATCH")
        self.assertFalse(got["eda_executed"])

    async def test_checker_requires_pinned_executable_hash(self):
        self.entry.pop("executable_sha256")
        self.save()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
            self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
            got = await run_approved_project("smoke")
            self.assertEqual(got["status"], "INVALID_CONFIGURATION")
            spawn.assert_not_called()

    async def test_executable_modified_during_execution_never_passes(self):
        async def spawn(*args, **kwargs):
            Path(kwargs["env"]["COCOTB_RESULTS_FILE"]).write_bytes(junit())
            self.executable.write_bytes(b"modified while running")
            return FakeProcess()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            got = await run_approved_project("smoke")
        self.assertEqual(got["status"], "EXECUTABLE_CHANGED")
        self.assertEqual(got["test_verdict"], "UNKNOWN")
        self.assertFalse(got["run_provenance"]["executable_unchanged"])

    async def test_undecodable_transcript_never_passes(self):
        got = await self.call(junit(), b"simulator \xff invalid utf8")
        self.assertEqual(got["checker"]["state"], "PASSED")
        self.assertEqual(got["test_verdict"], "UNKNOWN")
        self.assertFalse(got["transcript_utf8_lossless"])

    async def test_unparseable_long_transcript_line_never_passes(self):
        got = await self.call(junit(), b"x" * 9000)
        self.assertEqual(got["checker"]["state"], "PASSED")
        self.assertEqual(got["test_verdict"], "UNKNOWN")
        self.assertFalse(got["transcript_parser_complete"])

    async def test_report_path_unique_per_run(self):
        paths: list[str] = []
        async def spawn(*args, **kwargs):
            path = kwargs["env"]["COCOTB_RESULTS_FILE"]
            paths.append(path)
            Path(path).write_bytes(junit())
            return FakeProcess()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            a = await run_approved_project("smoke")
            b = await run_approved_project("smoke")
        self.assertEqual((a["checker_verdict"], b["checker_verdict"]), ("PASS", "PASS"))
        self.assertEqual((a["test_verdict"], b["test_verdict"]), ("UNKNOWN", "UNKNOWN"))
        self.assertNotEqual(paths[0], paths[1])
        self.assertFalse(Path(paths[0]).exists())
        self.assertFalse(Path(paths[1]).exists())


if __name__ == "__main__":
    unittest.main()
