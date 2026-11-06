"""Интеграционные mock-проверки пофазного запуска без Siemens/лицензии."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from questa_mcp.approved import CONFIG_ENV, list_approved_projects
from questa_mcp.phase_runner import run_approved_regression


class Stream:
    def __init__(self, contents: bytes):
        self.contents = contents

    async def read(self, count: int) -> bytes:
        part = self.contents[:count]
        self.contents = self.contents[count:]
        return part


class FakeProcess:
    def __init__(self, text=b"", exit_code=0):
        self.pid = 123456
        self.stdout = Stream(text)
        self.exit_code = exit_code
        self.returncode = None

    async def wait(self):
        self.returncode = self.exit_code
        return self.returncode

    def kill(self):
        self.returncode = -9


class PhaseRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        self.workspace = base / "workspace"
        self.workspace.mkdir()
        self.exe = base / ("vsim.exe" if os.name == "nt" else "vsim")
        self.exe.write_bytes(b"synthetic fake vendor")
        self.scripts = {}
        for name in ("default", "compile", "elaboration", "simulation"):
            path = self.workspace / (name + ".do")
            path.write_bytes(name.encode("ascii") + b"\n")
            self.scripts[name] = path
        self.entry = {
            "operator_approved": True, "disposable_workspace": True,
            "workspace": str(self.workspace), "executable": str(self.exe),
            "executable_sha256": hashlib.sha256(self.exe.read_bytes()).hexdigest(),
            "do_script": "default.do",
            "do_sha256": hashlib.sha256(self.scripts["default"].read_bytes()).hexdigest(),
            "checker": {"format": "cocotb-junit-v1", "expected_tests": ["check_counter"]},
            "phase_scripts": {
                name: {
                    "do_script": name + ".do",
                    "do_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for name, path in self.scripts.items() if name != "default"
            },
            "regression_seeds": [3, 7],
        }
        self.config = base / "approved.json"
        self.write_config()
        env = patch.dict(os.environ, {CONFIG_ENV: str(self.config)})
        env.start()
        self.addCleanup(env.stop)

    def write_config(self):
        self.config.write_text(json.dumps({"projects": {"smoke": self.entry}}), encoding="utf-8")

    @staticmethod
    def junit():
        return (
            b'<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
            b'<testcase name="check_counter"/></testsuite></testsuites>'
        )

    async def _execute(self, *, failing: str | None = None):
        observed = []

        async def spawn(*args, **kwargs):
            self.assertEqual(args[1:3], ("-c", "-do"))
            self.assertNotIn("shell", kwargs)
            self.assertTrue(Path(args[3]).is_file())
            label = Path(args[3]).read_text(encoding="ascii").strip()
            seed = kwargs["env"]["QUESTA_MCP_SEED"]
            self.assertIn(seed, ("3", "7"))
            observed.append((label, seed))
            if label == "simulation":
                result = Path(kwargs["env"]["COCOTB_RESULTS_FILE"])
                self.assertFalse(result.exists())
                result.write_bytes(self.junit())
            else:
                self.assertNotIn("COCOTB_RESULTS_FILE", kwargs["env"])
            if label == failing:
                return FakeProcess(b"** Error: (vsim-3825) synthetic failure", 1)
            return FakeProcess(b"# phase completed", 0)

        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            result = await run_approved_regression("smoke")
        return result, observed

    async def test_successful_stage_exits_do_not_claim_full_pass(self):
        report, observed = await self._execute()
        self.assertEqual(observed, [
            ("compile", "3"), ("elaboration", "3"), ("simulation", "3"),
            ("compile", "7"), ("elaboration", "7"), ("simulation", "7"),
        ])
        self.assertEqual(report["regression_verdict"], "UNKNOWN")
        self.assertEqual(report["test_count"], 2)
        self.assertEqual(report["counts"]["UNKNOWN"], 2)
        for run in report["runs"]:
            self.assertEqual(run["test_verdict"], "UNKNOWN")
            self.assertEqual(run["checker_verdict"], "PASS")
            self.assertEqual(run["assertions_verdict"], "UNKNOWN")
            self.assertEqual(run["seed_source"], "OPERATOR_CONFIGURED_ENV_NOT_OBSERVED_BY_SIMULATOR")
            self.assertEqual([p["state"] for p in run["phases"].values()], ["COMPLETED"] * 3)
            self.assertEqual(len(run["run_id"]), 24)
        self.assertNotEqual(report["runs"][0]["run_id"], report["runs"][1]["run_id"])

    async def test_compile_error_prevents_elaboration_and_simulation(self):
        report, observed = await self._execute(failing="compile")
        self.assertEqual(observed, [("compile", "3"), ("compile", "7")])
        self.assertEqual(report["regression_verdict"], "FAIL")
        for run in report["runs"]:
            self.assertEqual(run["phases"]["compile"]["state"], "FAILED")
            self.assertEqual(run["phases"]["elaboration"]["state"], "NOT_RUN")
            self.assertEqual(run["phases"]["simulation"]["state"], "NOT_RUN")
            self.assertEqual(run["test_verdict"], "FAIL")
            self.assertEqual(run["phases"]["compile"]["failure_evidence"][0]["code"], "vsim-3825")
            self.assertNotIn("raw", run["phases"]["compile"]["failure_evidence"][0])

    async def test_elaboration_failure_prevents_simulation(self):
        report, observed = await self._execute(failing="elaboration")
        self.assertEqual(observed, [
            ("compile", "3"), ("elaboration", "3"),
            ("compile", "7"), ("elaboration", "7")
        ])
        self.assertEqual(report["regression_verdict"], "FAIL")
        self.assertEqual(report["runs"][0]["phases"]["simulation"]["state"], "NOT_RUN")

    async def test_invalid_seeds_or_phase_digest_fail_closed(self):
        for seeds in ([1, 1], [], [True], [-1], [2**32], list(range(9)), ["42"]):
            self.entry["regression_seeds"] = seeds
            self.write_config()
            with self.subTest(seeds=seeds):
                self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
                self.assertEqual((await run_approved_regression("smoke"))["status"],
                                 "INVALID_CONFIGURATION")
        self.entry["regression_seeds"] = [3, 7]
        self.entry["phase_scripts"]["compile"]["do_sha256"] = "bad"
        self.write_config()
        self.assertEqual((await run_approved_regression("smoke"))["status"],
                         "INVALID_CONFIGURATION")

    async def test_missing_phase_configuration_is_not_run(self):
        self.entry.pop("phase_scripts")
        self.entry.pop("regression_seeds")
        self.write_config()
        report = await run_approved_regression("smoke")
        self.assertEqual(report["status"], "PHASES_NOT_CONFIGURED")
        self.assertEqual(report["regression_verdict"], "NOT_RUN")

    async def test_binary_change_blocks_pipeline_before_spawn(self):
        self.exe.write_bytes(b"changed executable")
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec") as spawn:
            report = await run_approved_regression("smoke")
            spawn.assert_not_called()
        self.assertEqual(report["status"], "EXECUTABLE_HASH_MISMATCH")
        self.assertEqual(report["regression_verdict"], "NOT_RUN")

    async def test_missing_project_does_not_run(self):
        result = await run_approved_regression("../smoke")
        self.assertEqual(result["status"], "DENIED")
        self.assertEqual(result["runs"], [])


if __name__ == "__main__":
    unittest.main()
