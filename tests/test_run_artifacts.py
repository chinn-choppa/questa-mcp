"""Run-scoped waveform evidence: mock processes and real MCP calls, no EDA."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from questa_mcp.approved import (
    CONFIG_ENV, list_approved_projects, list_run_artifacts
)
from questa_mcp.phase_runner import run_approved_regression
from questa_mcp.server import create_server


class _Stream:
    async def read(self, _: int) -> bytes:
        return b""


class _Process:
    pid = 12345678
    returncode = None
    stdout = _Stream()

    async def wait(self):
        self.returncode = 0
        return 0

    def kill(self):
        self.returncode = -9


class RunArtifactTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.capture_root = self.workspace / "new-runs"
        self.capture_root.mkdir()
        self.binary = root / ("vsim.exe" if os.name == "nt" else "vsim")
        self.binary.write_bytes(b"public fake simulator")
        scripts = {}
        for stage in ("default", "compile", "elaboration", "simulation"):
            path = self.workspace / (stage + ".do")
            path.write_bytes(stage.encode())
            scripts[stage] = path
        self.entry = {
            "workspace": str(self.workspace), "executable": str(self.binary),
            "executable_sha256": hashlib.sha256(self.binary.read_bytes()).hexdigest(),
            "do_script": "default.do",
            "do_sha256": hashlib.sha256(scripts["default"].read_bytes()).hexdigest(),
            "operator_approved": True, "disposable_workspace": True,
            "regression_seeds": [11, 22],
            "phase_scripts": {
                stage: {"do_script": stage + ".do",
                        "do_sha256": hashlib.sha256(scripts[stage].read_bytes()).hexdigest()}
                for stage in ("compile", "elaboration", "simulation")
            },
            "run_artifacts_dir": "new-runs",
            "run_artifacts": [
                {"id": "clock", "path": "wave.vcd", "format": "vcd",
                 "declared_time_unit": "ns"}
            ],
        }
        self.config = root / "approved.json"
        self.save()
        env = patch.dict(os.environ, {CONFIG_ENV: str(self.config)})
        env.start()
        self.addCleanup(env.stop)

    def save(self):
        self.config.write_text(json.dumps({"projects": {"public": self.entry}}),
                               encoding="utf-8")

    async def test_fresh_per_seed_artifacts_are_observed_not_attested(self):
        paths: list[tuple[str, Path]] = []

        async def spawn(*args, **kwargs):
            phase = Path(args[3]).read_text()
            out = Path(kwargs["env"]["QUESTA_MCP_ARTIFACT_DIR"])
            self.assertTrue(out.is_dir())
            self.assertEqual(out.parent, self.capture_root.resolve())
            if phase == "simulation":
                self.assertFalse((out / "wave.vcd").exists())
                payload = b"$timescale 1ns $end\n" + kwargs["env"]["QUESTA_MCP_SEED"].encode()
                (out / "wave.vcd").write_bytes(payload)
                paths.append((kwargs["env"]["QUESTA_MCP_SEED"], out))
            return _Process()

        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            result = await run_approved_regression("public")

        self.assertEqual(result["regression_verdict"], "UNKNOWN")
        self.assertEqual(len(paths), 2)
        self.assertNotEqual(paths[0][1], paths[1][1])
        for run, (seed, directory) in zip(result["runs"], paths):
            self.assertEqual(str(run["seed"]), seed)
            self.assertEqual(directory.name, run["run_id"])
            self.assertEqual(run["test_verdict"], "UNKNOWN")
            self.assertEqual(run["artifact_origin"],
                             "RUN_SCOPED_DIRECTORY_OBSERVED_NOT_VENDOR_ATTESTED")
            item = run["artifact_manifest"]["items"][0]
            self.assertEqual(item["state"], "HASHED")
            self.assertEqual(item["origin"], "OBSERVED_IN_RUN_DIRECTORY_NOT_VENDOR_ATTESTED")
            self.assertEqual(item["observed_in_run_id"], run["run_id"])
            self.assertIsNone(item["produced_by_run_id"])
            self.assertIsNone(item["local_path"])
            self.assertFalse(item["format_validated"])
            self.assertEqual(item["sha256"], hashlib.sha256(
                (directory / "wave.vcd").read_bytes()).hexdigest())
            self.assertEqual(
                list_run_artifacts("public", run["run_id"])["items"][0]["sha256"],
                item["sha256"],
            )
        self.assertEqual(list_run_artifacts("public", "0" * 24)["state"], "RUN_NOT_FOUND")

    async def test_real_mcp_roundtrip_for_observed_run_directory(self):
        async def spawn(*args, **kwargs):
            phase = Path(args[3]).read_text()
            if phase == "simulation":
                target = Path(kwargs["env"]["QUESTA_MCP_ARTIFACT_DIR"]) / "wave.vcd"
                target.write_bytes(b"$timescale 1ns $end\n#0\n0!\n")
            return _Process()

        self.entry["regression_seeds"] = [7]
        self.save()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            async with Client(create_server()) as client:
                result = await client.call_tool(
                    "run_approved_regression", {"project_id": "public"}
                )
                self.assertFalse(result.is_error)
                run_id = result.structured_content["runs"][0]["run_id"]
                lookup = await client.call_tool(
                    "list_run_artifacts", {"project_id": "public", "run_id": run_id}
                )
                self.assertFalse(lookup.is_error)
                self.assertEqual(lookup.structured_content["count"], 1)
                self.assertEqual(lookup.structured_content["items"][0]["state"], "HASHED")
                denied = await client.call_tool(
                    "list_run_artifacts", {"project_id": "public", "run_id": "../whatever"}
                )
                self.assertEqual(denied.structured_content["state"], "DENIED")

    async def test_invalid_root_and_artifact_configuration_denied(self):
        for root in ("../other", "C:/secret", r"new-runs\evil", "/tmp", ""):
            self.entry["run_artifacts_dir"] = root
            self.save()
            with self.subTest(root=root):
                self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
                self.assertEqual((await run_approved_regression("public"))["status"],
                                 "INVALID_CONFIGURATION")
        self.entry["run_artifacts_dir"] = "new-runs"
        self.entry["run_artifacts"] = []
        self.save()
        self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
        self.entry.pop("run_artifacts")
        self.save()
        self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")

    async def test_root_symlink_and_unknown_run_are_denied(self):
        if os.name == "nt":
            self.skipTest("Windows symlink permissions vary")
        alternate = self.workspace / "alternate"
        alternate.mkdir()
        self.capture_root.rmdir()
        self.capture_root.symlink_to(alternate)
        self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")

    async def test_paths_only_with_explicit_operator_opt_in(self):
        self.entry["expose_artifact_paths"] = True
        self.entry["regression_seeds"] = [1]
        self.save()

        async def spawn(*args, **kwargs):
            if Path(args[3]).read_text() == "simulation":
                (Path(kwargs["env"]["QUESTA_MCP_ARTIFACT_DIR"]) / "wave.vcd").write_bytes(b"synthetic")
            return _Process()

        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            report = await run_approved_regression("public")
        path = report["runs"][0]["artifact_manifest"]["items"][0]["local_path"]
        self.assertEqual(Path(path).parent.name, report["runs"][0]["run_id"])
        self.assertEqual(
            list_run_artifacts("public", report["runs"][0]["run_id"])["items"][0]["local_path"],
            path,
        )


if __name__ == "__main__":
    unittest.main()
