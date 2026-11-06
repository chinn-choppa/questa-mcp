"""Реальный Wavepeek CLI над VCD из утверждённого mock-run контекста.

Вызывается только отдельным CI job. Не выполняет коммерческий Siemens.
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

from questa_mcp.approved import CONFIG_ENV, run_approved_project


class _Stream:
    async def read(self, _: int) -> bytes:
        return b""


class _Process:
    pid = 12345
    returncode = None

    def __init__(self):
        self.stdout = _Stream()

    async def wait(self) -> int:
        self.returncode = 0
        return 0


async def _mock_allowed_run(base: Path, fixture: Path) -> dict:
    workspace = base / "workspace"
    workspace.mkdir()
    store = base / "output-store"
    store.mkdir()
    script = workspace / "run.do"
    script.write_bytes(b"run -all\nquit -f\n")
    binary = base / ("vsim.exe" if os.name == "nt" else "vsim")
    binary.write_bytes(b"mock only -- no commercial tool")
    config = base / "approved.json"
    config.write_text(json.dumps({"projects": {"public-clock": {
        "workspace": str(workspace),
        "executable": str(binary),
        "executable_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "do_script": "run.do",
        "do_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "operator_approved": True,
        "disposable_workspace": True,
        "capture_run_artifacts": True,
        "run_artifact_store": str(store),
        "expose_artifact_paths": True,
        "artifacts": [{"id": "clock", "path": "clock" + fixture.suffix,
                       "format": fixture.suffix.removeprefix(".")}],
    }}}), encoding="utf-8")

    async def fake_subprocess(*args, **kwargs):
        path = Path(kwargs["env"]["QUESTA_MCP_ARTIFACT_DIR"]) / ("clock" + fixture.suffix)
        assert not path.exists(), "Fresh directory was not empty"
        path.write_bytes(fixture.read_bytes())
        return _Process()

    with patch.dict(os.environ, {CONFIG_ENV: str(config)}), patch(
        "questa_mcp.approved.asyncio.create_subprocess_exec", side_effect=fake_subprocess
    ):
        return await run_approved_project("public-clock")


def _check_query(result: dict, fixture: Path, wavepeek: Path, kind: str) -> None:
    manifest = result["run_artifacts"]
    assert result["test_verdict"] == "UNKNOWN", "No global verification PASS"
    assert result["checker_verdict"] == "UNKNOWN", "No testbench checker invoked"
    assert manifest["retained"] is True
    assert manifest["observed_count"] == 1
    item = manifest["items"][0]
    assert item["observed_under_run_id"] == manifest["run_id"]
    assert item["produced_by_run_id"] is None
    assert item["production_verified"] is False
    assert item["format_validated"] is False
    local = Path(item["local_path"])
    assert local.is_file()
    assert item["sha256"] == hashlib.sha256(fixture.read_bytes()).hexdigest()
    output = subprocess.run(
        [str(wavepeek), "value", "--waves", str(local), "--at", "0ns,5ns",
         "--signals", "tb.clk"],
        capture_output=True, text=True, timeout=20, check=True,
    )
    print(output.stdout)
    samples = re.findall(r"@([05]ns)\s+tb\.clk=(\S+)", output.stdout)
    assert len(samples) == 2, f"Expected 2 decoded clock samples: {output.stdout!r}"
    assert [time for time, _ in samples] == ["0ns", "5ns"], samples
    assert samples[0][1] != samples[1][1], "Clock must toggle"
    print(f"WAVEPEEK_PUBLIC_{kind}=PASS")


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: wavepeek_handoff_smoke.py /path/to/wavepeek /path/to/vcd2fst"
        )
    wavepeek = Path(sys.argv[1]).resolve(strict=True)
    converter = Path(sys.argv[2]).resolve(strict=True)
    fixture = Path(__file__).parents[1] / "fixtures" / "clock_wave.vcd"
    with tempfile.TemporaryDirectory(prefix="questa-wavepeek-integration-") as temp:
        base = Path(temp)
        vcd_root = base / "vcd"
        vcd_root.mkdir()
        vcd = asyncio.run(_mock_allowed_run(vcd_root, fixture))
        _check_query(vcd, fixture, wavepeek, "VCD")

        # vcd2fst — независимый открытый конвертер GTKWave в CI, не часть MCP.
        fst_file = base / "clock_wave.fst"
        subprocess.run(
            [str(converter), str(fixture), str(fst_file)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        assert fst_file.is_file() and fst_file.stat().st_size > 0
        fst_root = base / "fst"
        fst_root.mkdir()
        fst = asyncio.run(_mock_allowed_run(fst_root, fst_file))
        _check_query(fst, fst_file, wavepeek, "FST")
        assert fst["run_artifacts"]["run_id"] != vcd["run_artifacts"]["run_id"]
        print("QUESTA_LICENSED_EDA=NOT_RUN")
        print("WLF_CONVERSION=NOT_RUN")
        print("FULL_RTL_VERIFICATION=UNKNOWN")


if __name__ == "__main__":
    main()
