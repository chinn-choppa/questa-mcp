"""Проверки новых артефактов, привязанных к конкретному разрешённому запуску."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from mcp import Client

from questa_mcp.approved import (
    CONFIG_ENV,
    list_approved_projects,
    run_approved_project,
)
from questa_mcp.server import create_server


class FakeStream:
    async def read(self, _: int) -> bytes:
        return b""


class FakeProcess:
    pid = 867531

    def __init__(self, code: int = 0):
        self.stdout = FakeStream()
        self.returncode = None
        self.code = code

    async def wait(self) -> int:
        self.returncode = self.code
        return self.code

    def kill(self):
        self.returncode = -9


VCD = (
    b"$timescale 1ns $end\n"
    b"$scope module tb $end\n"
    b"$var wire 1 ! clk $end\n"
    b"$upscope $end\n$enddefinitions $end\n"
    b"#0\n0!\n#5\n1!\n"
)


class FreshArtifactCaptureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        self.binary = self.base / ("vsim.exe" if os.name == "nt" else "vsim")
        self.binary.write_bytes(b"public synthetic mocked vsim")
        self.do = self.workspace / "run.do"
        self.do.write_bytes(b"run -all\nquit -f\n")
        self.config = self.base / "projects.json"
        self.entry = {
            "workspace": str(self.workspace),
            "executable": str(self.binary),
            "executable_sha256": hashlib.sha256(self.binary.read_bytes()).hexdigest(),
            "do_script": "run.do",
            "do_sha256": hashlib.sha256(self.do.read_bytes()).hexdigest(),
            "operator_approved": True,
            "disposable_workspace": True,
            "capture_run_artifacts": True,
            "artifacts": [
                {"id": "clock", "path": "waves/clock.vcd", "format": "vcd",
                 "declared_time_unit": "ns"}
            ],
        }
        self.save()
        patcher = patch.dict(os.environ, {CONFIG_ENV: str(self.config)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def save(self):
        self.config.write_text(
            json.dumps({"projects": {"smoke": self.entry}}),
            encoding="utf-8",
        )

    async def _run(self, write_wave=True, return_code=0):
        paths = []

        async def spawn(*args, **kwargs):
            self.assertNotIn("shell", kwargs)
            self.assertEqual(args[1:3], ("-c", "-do"))
            env = kwargs["env"]
            self.assertNotIn("COCOTB_RESULTS_FILE", env)
            fresh_root = Path(env["QUESTA_MCP_ARTIFACT_DIR"])
            paths.append(fresh_root)
            self.assertTrue(fresh_root.is_dir())
            self.assertEqual(list(fresh_root.iterdir()), [])
            if write_wave:
                (fresh_root / "waves").mkdir()
                (fresh_root / "waves" / "clock.vcd").write_bytes(VCD)
            return FakeProcess(return_code)

        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            result = await run_approved_project("smoke")
        return result, paths[0]

    async def test_fresh_file_is_observed_but_not_declared_produced(self):
        result, root = await self._run()
        manifest = result["run_artifacts"]
        self.assertEqual(result["status"], "COMPLETED_UNVERIFIED")
        self.assertEqual(result["test_verdict"], "UNKNOWN")
        self.assertEqual(manifest["state"], "OBSERVED")
        self.assertEqual(manifest["observed_count"], 1)
        self.assertEqual(len(manifest["run_id"]), 32)
        self.assertFalse(manifest["retained"])
        self.assertEqual(manifest["capture_mode"], "EPHEMERAL_REMOVED_AFTER_CALL")
        item = manifest["items"][0]
        self.assertEqual(item["state"], "HASHED")
        self.assertEqual(item["sha256"], hashlib.sha256(VCD).hexdigest())
        self.assertEqual(item["observed_under_run_id"], manifest["run_id"])
        self.assertEqual(item["origin"], "FRESH_RUN_DIRECTORY_OBSERVED")
        self.assertIsNone(item["produced_by_run_id"])
        self.assertFalse(item["production_verified"])
        self.assertFalse(item["format_validated"])
        self.assertIsNone(item["local_path"])
        self.assertEqual(result["run_provenance"]["run_id"], manifest["run_id"])
        self.assertFalse(root.exists())

    async def test_stale_workspace_artifact_is_not_linked(self):
        (self.workspace / "waves").mkdir()
        (self.workspace / "waves" / "clock.vcd").write_bytes(VCD)
        result, _ = await self._run(write_wave=False)
        manifest = result["run_artifacts"]
        self.assertEqual(manifest["observed_count"], 0)
        item = manifest["items"][0]
        self.assertEqual(item["state"], "MISSING_OR_UNSAFE_PATH")
        self.assertEqual(item["origin"], "NO_RUN_ASSOCIATION")
        self.assertIsNone(item["observed_under_run_id"])
        self.assertEqual(result["test_verdict"], "UNKNOWN")

    async def test_every_run_gets_a_new_id_and_empty_directory(self):
        a, first = await self._run()
        b, second = await self._run()
        self.assertNotEqual(a["run_artifacts"]["run_id"], b["run_artifacts"]["run_id"])
        self.assertNotEqual(first, second)
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())

    async def test_persistent_store_is_opt_in_and_paths_are_hidden(self):
        store = self.base / "approved-artifacts"
        store.mkdir()
        self.entry["run_artifact_store"] = str(store)
        self.save()
        result, root = await self._run()
        manifest = result["run_artifacts"]
        self.assertEqual(manifest["capture_mode"], "PERSISTENT_OPERATOR_APPROVED")
        self.assertTrue(manifest["retained"])
        self.assertTrue(root.exists())
        self.assertEqual((root / "waves" / "clock.vcd").read_bytes(), VCD)
        self.assertIsNone(manifest["items"][0]["local_path"])

        self.entry["expose_artifact_paths"] = True
        self.save()
        visible, second = await self._run()
        item = visible["run_artifacts"]["items"][0]
        self.assertEqual(item["local_path"], str(second / "waves" / "clock.vcd"))
        self.assertTrue(item["paths_disclosed"])

    async def test_persistent_store_requires_trusted_root_outside_workspace(self):
        for invalid in (
            str(self.workspace),
            str(self.workspace / "missing"),
            "relative/directory",
            False,
        ):
            with self.subTest(invalid=invalid):
                self.entry["run_artifact_store"] = invalid
                self.save()
                with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
                    self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
                    response = await run_approved_project("smoke")
                    self.assertEqual(response["status"], "INVALID_CONFIGURATION")
                    spawn.assert_not_called()

    async def test_capture_requires_allowlisted_spec_and_pinned_executable(self):
        for field, value in (("artifacts", []), ("executable_sha256", None)):
            entry = dict(self.entry)
            entry[field] = value
            self.config.write_text(json.dumps({"projects": {"smoke": entry}}), encoding="utf-8")
            with patch("questa_mcp.approved.asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
                self.assertEqual(list_approved_projects()["state"], "INVALID_CONFIGURATION")
                result = await run_approved_project("smoke")
                self.assertEqual(result["status"], "INVALID_CONFIGURATION")
                spawn.assert_not_called()

    async def test_mock_process_failure_does_not_turn_artifacts_into_test_pass(self):
        result, root = await self._run(return_code=4)
        self.assertEqual(result["status"], "PROCESS_FAILED")
        self.assertEqual(result["test_verdict"], "FAIL")
        self.assertEqual(result["run_artifacts"]["observed_count"], 1)
        self.assertFalse(root.exists())

    async def test_capture_disabled_keeps_legacy_workspace_artifacts_unattested(self):
        self.entry["capture_run_artifacts"] = False
        self.save()
        async def spawn(*args, **kwargs):
            self.assertNotIn("env", kwargs)
            return FakeProcess()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            result = await run_approved_project("smoke")
        self.assertEqual(result["run_artifacts"]["state"], "NOT_CONFIGURED")
        self.assertIsNone(result["run_artifacts"]["run_id"])


    async def test_inherited_environment_cannot_redirect_capture(self):
        with patch.dict(os.environ, {
            "QUESTA_MCP_ARTIFACT_DIR": str(self.workspace),
            "COCOTB_RESULTS_FILE": str(self.workspace / "old.xml"),
        }):
            # Профиль без checker не должен наследовать чужой results.xml.
            result, output = await self._run()
        self.assertEqual(result["run_artifacts"]["observed_count"], 1)
        self.assertFalse(output.exists())

    async def test_timed_out_process_does_not_claim_run_association(self):
        from unittest.mock import AsyncMock
        async def fake_execute(profile, *, results_file=None, artifact_dir=None):
            wave = artifact_dir / "waves" / "clock.vcd"
            wave.parent.mkdir()
            wave.write_bytes(VCD)
            return "TIMEOUT", -9, b""
        with patch("questa_mcp.approved._execute", side_effect=fake_execute):
            result = await run_approved_project("smoke")
        self.assertEqual(result["status"], "TIMEOUT")
        self.assertEqual(result["run_artifacts"]["observed_count"], 0)
        self.assertIsNone(result["run_artifacts"]["items"][0]["observed_under_run_id"])

    async def test_binary_mutated_during_run_revokes_artifact_association(self):
        async def spawn(*args, **kwargs):
            root = Path(kwargs["env"]["QUESTA_MCP_ARTIFACT_DIR"])
            (root / "waves").mkdir()
            (root / "waves" / "clock.vcd").write_bytes(VCD)
            self.binary.write_bytes(b"binary replaced")
            return FakeProcess()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            result = await run_approved_project("smoke")
        self.assertEqual(result["status"], "EXECUTABLE_CHANGED")
        self.assertEqual(result["run_artifacts"]["state"], "BINARY_INTEGRITY_FAILED")
        self.assertEqual(result["run_artifacts"]["observed_count"], 0)
        self.assertIsNone(result["run_artifacts"]["items"][0]["observed_under_run_id"])
        self.assertEqual(result["test_verdict"], "UNKNOWN")

    async def test_true_mcp_tool_call_links_observation_not_production(self):
        async def spawn(*args, **kwargs):
            root = Path(kwargs["env"]["QUESTA_MCP_ARTIFACT_DIR"])
            (root / "waves").mkdir()
            (root / "waves" / "clock.vcd").write_bytes(VCD)
            return FakeProcess()
        with patch("questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=spawn):
            async with Client(create_server()) as client:
                listed = await client.list_tools()
                self.assertIn("run_approved_project", {tool.name for tool in listed.tools})
                response = await client.call_tool(
                    "run_approved_project", {"project_id": "smoke"}
                )
                self.assertFalse(response.is_error)
                body = response.structured_content
                self.assertEqual(body["run_artifacts"]["observed_count"], 1)
                self.assertEqual(body["test_verdict"], "UNKNOWN")
                self.assertIsNone(body["run_artifacts"]["items"][0]["produced_by_run_id"])


if __name__ == "__main__":
    unittest.main()
