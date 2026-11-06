"""Real Wavepeek VCD/FST smoke over mocked approved Questa regression artifacts.

Run only in dedicated GitHub Actions. No licensed EDA and no MCP shell executor.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from questa_mcp.approved import CONFIG_ENV
from questa_mcp.server import create_server


class FakeStream:
    async def read(self, _: int) -> bytes:
        return b""


class FakeProcess:
    pid = 123456
    returncode = None

    def __init__(self):
        self.stdout = FakeStream()

    async def wait(self) -> int:
        self.returncode = 0
        return 0


async def approved_mcp_handoff(base: Path, waveform: Path) -> tuple[dict, dict]:
    workspace = base / "workspace"
    workspace.mkdir()
    (workspace / "run-results").mkdir()
    scripts: dict[str, Path] = {}
    for stage in ("default", "compile", "elaboration", "simulation"):
        p = workspace / f"{stage}.do"
        p.write_bytes(stage.encode("ascii"))
        scripts[stage] = p
    executable = base / ("vsim.exe" if os.name == "nt" else "vsim")
    executable.write_bytes(b"synthetic mocked vsim, never started")
    config = base / "approved.json"
    config.write_text(json.dumps({"projects": {"public": {
        "workspace": str(workspace),
        "executable": str(executable),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "do_script": "default.do",
        "do_sha256": hashlib.sha256(scripts["default"].read_bytes()).hexdigest(),
        "operator_approved": True,
        "disposable_workspace": True,
        "regression_seeds": [7],
        "phase_scripts": {
            stage: {
                "do_script": f"{stage}.do",
                "do_sha256": hashlib.sha256(scripts[stage].read_bytes()).hexdigest(),
            }
            for stage in ("compile", "elaboration", "simulation")
        },
        "run_artifacts_dir": "run-results",
        "run_artifacts": [
            {"id": "clock", "path": "clock" + waveform.suffix,
             "format": waveform.suffix.lstrip(".")}
        ],
        "expose_artifact_paths": True,
    }}}), encoding="utf-8")

    async def fake_spawn(*args, **kwargs):
        stage = Path(args[3]).read_text(encoding="ascii")
        env = kwargs["env"]
        assert env["QUESTA_MCP_SEED"] == "7"
        fresh = Path(env["QUESTA_MCP_ARTIFACT_DIR"])
        assert fresh.parent == (workspace / "run-results").resolve()
        assert fresh.is_dir()
        if stage == "simulation":
            target = fresh / ("clock" + waveform.suffix)
            assert not target.exists()
            target.write_bytes(waveform.read_bytes())
        return FakeProcess()

    with patch.dict(os.environ, {CONFIG_ENV: str(config)}), patch(
        "questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=fake_spawn
    ):
        async with Client(create_server()) as client:
            run_call = await client.call_tool("run_approved_regression", {"project_id": "public"})
            assert not run_call.is_error, "MCP phase runner returned an error"
            result = run_call.structured_content
            assert result["regression_verdict"] == "UNKNOWN"
            assert result["test_count"] == 1
            record = result["runs"][0]
            assert record["test_verdict"] == "UNKNOWN"
            assert len(record["run_id"]) == 24
            for phase in ("compile", "elaboration", "simulation"):
                assert record["phases"][phase]["state"] == "COMPLETED"
            result_handoff = await client.call_tool("prepare_run_handoff", {
                "project_id": "public",
                "run_id": record["run_id"],
                "artifact_id": "clock",
                "consumer": "wavepeek",
            })
            assert not result_handoff.is_error
            handoff = result_handoff.structured_content
            assert handoff["status"] == "READY_FOR_EXTERNAL_CLIENT"
            assert handoff["external_execution"] == "NOT_RUN"
            assert handoff["format_validated"] is False
            assert handoff["vendor_attested"] is False
            assert handoff["run_id"] == record["run_id"]
            return record, handoff


def verify_wavepeek_samples(record: dict, handoff: dict, source: Path,
                            wavepeek: Path, label: str) -> None:
    artifact = record["artifact_manifest"]["items"][0]
    assert artifact["state"] == "HASHED"
    assert artifact["observed_in_run_id"] == record["run_id"]
    assert artifact["produced_by_run_id"] is None
    local = Path(handoff["local_path"])
    assert local.is_file()
    assert artifact["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    output = subprocess.run(
        [str(wavepeek), "value", "--waves", str(local), "--at", "0ns,5ns",
         "--signals", "tb.clk"],
        capture_output=True, text=True, timeout=20, check=True,
    )
    print(output.stdout)
    samples = re.findall(r"@([05]ns)\s+tb\.clk=(\S+)", output.stdout)
    assert len(samples) == 2, f"Expected 2 decoded samples: {output.stdout!r}"
    assert [t for t, _ in samples] == ["0ns", "5ns"], samples
    assert samples[0][1] != samples[1][1], "Expected a toggling clock"
    print(f"WAVEPEEK_PUBLIC_{label}=PASS")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: wavepeek_handoff_smoke.py /path/wavepeek /path/vcd2fst")
    wavepeek = Path(sys.argv[1]).resolve(strict=True)
    converter = Path(sys.argv[2]).resolve(strict=True)
    fixture = Path(__file__).parents[1] / "fixtures" / "clock_wave.vcd"
    with tempfile.TemporaryDirectory(prefix="questa-wavepeek-verified-") as tmp:
        base = Path(tmp)
        vcdcase = base / "vcd"
        vcdcase.mkdir()
        vcd_record, vcd_handoff = asyncio.run(approved_mcp_handoff(vcdcase, fixture))
        verify_wavepeek_samples(vcd_record, vcd_handoff, fixture, wavepeek, "VCD")

        fst = base / "clock_wave.fst"
        subprocess.run(
            [str(converter), str(fixture), str(fst)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        assert fst.stat().st_size > 0
        fstcase = base / "fst"
        fstcase.mkdir()
        fst_record, fst_handoff = asyncio.run(approved_mcp_handoff(fstcase, fst))
        verify_wavepeek_samples(fst_record, fst_handoff, fst, wavepeek, "FST")

    print("QUESTA_LICENSED_EDA=NOT_RUN")
    print("WLF_CONVERSION=NOT_RUN")
    print("FULL_RTL_VERIFICATION=UNKNOWN")


if __name__ == "__main__":
    main()
