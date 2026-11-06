"""Последовательная регрессия по разрешённым DO-профилям (без shell/Tcl от MCP).

Весь положительный вывод относится только к наблюдённым процессам и cocotb.
Общий PASS не выдаётся без независимых подтверждений assertions.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import tempfile
from dataclasses import replace
from pathlib import Path

from .artifact_handoff import inspect_approved_artifacts
from .approved import (
    CONFIG_ENV,
    _ID,
    _LICENSE,
    _execute,
    _hash_executable,
    _load_approved_profiles,
)
from .diagnostics import parse_diagnostics_text
from .junit_evidence import analyze_junit_bytes, read_junit_artifact

_PHASES = ("compile", "elaboration", "simulation")


def _not_run() -> dict[str, object]:
    return {
        "state": "NOT_RUN", "process_status": "NOT_RUN", "exit_code": None,
        "stdout_sha256": None, "captured_bytes": 0, "diagnostic_count": 0,
        "failure_evidence": [], "checker": None, "checker_verdict": "UNKNOWN",
        "phase_trust": "OPERATOR_DECLARED_DO_PHASE_NOT_VENDOR_ATTESTED",
    }


async def _run_phase(
    profile, phase: tuple[str, Path, str], seed: int, *, artifact_dir: Path | None = None
) -> dict[str, object]:
    phase_name, do_path, digest = phase
    stage_profile = replace(profile, script=do_path, script_sha256=digest)
    with tempfile.TemporaryDirectory(prefix="questa-mcp-phase-") as td:
        report_path = Path(td) / "results.xml" if phase_name == "simulation" and profile.checker_format else None
        status, code, log = await _execute(
            stage_profile, results_file=report_path, seed=seed, artifact_dir=artifact_dir
        )
        checker = None
        if report_path is not None:
            raw, read_status = read_junit_artifact(report_path)
            if raw is None:
                checker = {"state": "UNKNOWN", "reason": read_status, "report_sha256": None}
            else:
                checker = analyze_junit_bytes(raw, profile.expected_tests)

    try:
        decoded = log.decode("utf-8")
        lossless = True
    except UnicodeDecodeError:
        decoded = log.decode("utf-8", errors="replace")
        lossless = False
    try:
        parsed = parse_diagnostics_text(decoded, tool="vsim", limit=32)
        parser_ok = True
    except ValueError:
        parsed = {"items": [], "count": 0, "test_verdict": "UNKNOWN"}
        parser_ok = False
    if status in {"PROCESS_FAILED", "COMPLETED_UNVERIFIED"} and _LICENSE.search(decoded):
        status = "LICENSE_ERROR_EVIDENCE"

    try:
        binary_ok = _hash_executable(profile.executable) == profile.executable_sha256
    except (OSError, ValueError):
        binary_ok = False
    if not binary_ok and status == "COMPLETED_UNVERIFIED":
        status = "EXECUTABLE_CHANGED"

    negative = (
        status in {"PROCESS_FAILED", "LICENSE_ERROR_EVIDENCE"}
        or parsed["test_verdict"] == "FAIL"
        or (checker is not None and checker["state"] == "FAILED")
    )
    if negative:
        state = "FAILED"
    elif status == "TIMEOUT":
        state = "TIMEOUT"
    elif status == "COMPLETED_UNVERIFIED" and code == 0 and parser_ok and lossless and binary_ok:
        state = "COMPLETED"
    else:
        state = "UNKNOWN"

    # Только явно разрешённый оператором журнал может содержать исходные строки.
    evidence = []
    for d in parsed["items"]:
        if d["severity"] in {"error", "fatal"}:
            ev = {
                "severity": d["severity"], "code": d["code"],
                "source_line": d["source_line"],
            }
            if profile.expose_diagnostics:
                ev["raw"] = d["raw"]
            evidence.append(ev)
        if len(evidence) >= 8:
            break

    checker_verdict = "UNKNOWN"
    if checker is not None and checker["state"] == "FAILED":
        checker_verdict = "FAIL"
    elif (
        state == "COMPLETED" and checker is not None
        and checker["state"] == "PASSED"
    ):
        checker_verdict = "PASS"

    return {
        "state": state, "process_status": status, "exit_code": code,
        "stdout_sha256": hashlib.sha256(log).hexdigest(),
        "captured_bytes": len(log), "diagnostic_count": parsed["count"],
        "failure_evidence": evidence, "checker": checker,
        "checker_verdict": checker_verdict,
        "phase_trust": "OPERATOR_DECLARED_DO_PHASE_NOT_VENDOR_ATTESTED",
        "script_sha256": digest, "executable_unchanged": binary_ok,
        "transcript_parser_complete": parser_ok, "transcript_utf8_lossless": lossless,
    }


async def run_approved_regression(project_id: str) -> dict[str, object]:
    """Без входных seeds/DO/команд: только локальный профиль оператора."""
    if not isinstance(project_id, str) or not _ID.fullmatch(project_id):
        return {"status": "DENIED", "regression_verdict": "UNKNOWN", "runs": []}
    if not os.getenv(CONFIG_ENV):
        return {"status": "NOT_CONFIGURED", "regression_verdict": "NOT_RUN", "runs": []}
    try:
        profile = _load_approved_profiles().get(project_id)
        if profile is None:
            return {"status": "DENIED", "regression_verdict": "UNKNOWN", "runs": []}
        if not profile.phase_scripts:
            return {"status": "PHASES_NOT_CONFIGURED", "regression_verdict": "NOT_RUN", "runs": []}
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "INVALID_CONFIGURATION", "regression_verdict": "NOT_RUN", "runs": []}

    try:
        if _hash_executable(profile.executable) != profile.executable_sha256:
            return {"status": "EXECUTABLE_HASH_MISMATCH", "regression_verdict": "NOT_RUN", "runs": []}
    except (OSError, ValueError):
        return {"status": "EXECUTABLE_UNVERIFIED", "regression_verdict": "NOT_RUN", "runs": []}

    runs: list[dict[str, object]] = []
    for seed in profile.regression_seeds:
        run_id = secrets.token_hex(12)
        artifact_dir: Path | None = None
        if profile.run_artifact_root is not None:
            artifact_dir = profile.run_artifact_root / run_id
            try:
                artifact_dir.mkdir(mode=0o700, exist_ok=False)
            except OSError:
                return {
                    "status": "ARTIFACT_DIR_UNAVAILABLE", "regression_verdict": "UNKNOWN",
                    "runs": runs, "vendor_compatibility_verified": False,
                }
        phases = {phase: _not_run() for phase in _PHASES}
        for phase in profile.phase_scripts:
            name = phase[0]
            result = await _run_phase(profile, phase, seed, artifact_dir=artifact_dir)
            phases[name] = result
            if result["state"] != "COMPLETED":
                break

        negative = any(r["state"] == "FAILED" for r in phases.values())
        checker = phases["simulation"].get("checker")
        if negative:
            verdict, reason = "FAIL", "NEGATIVE_PHASE_OR_CHECKER_EVIDENCE"
        elif checker is not None and phases["simulation"]["checker_verdict"] == "PASS":
            verdict, reason = "UNKNOWN", "CHECKER_PASS_ONLY_ASSERTIONS_UNVERIFIED"
        else:
            verdict, reason = "UNKNOWN", "INCOMPLETE_OR_UNVERIFIED_PHASES"
        manifest = None
        origin = "NOT_CONFIGURED"
        if artifact_dir is not None:
            manifest = inspect_approved_artifacts(
                artifact_dir, profile.run_artifact_specs,
                expose_paths=profile.expose_artifact_paths,
            )
            for entry in manifest["items"]:
                entry["origin"] = "OBSERVED_IN_RUN_DIRECTORY_NOT_VENDOR_ATTESTED"
                entry["observed_in_run_id"] = run_id
            origin = "RUN_SCOPED_DIRECTORY_OBSERVED_NOT_VENDOR_ATTESTED"
        runs.append({
            "run_id": run_id, "seed": seed,
            "seed_source": "OPERATOR_CONFIGURED_ENV_NOT_OBSERVED_BY_SIMULATOR",
            "phases": phases, "test_verdict": verdict, "reason": reason,
            "checker_verdict": phases["simulation"]["checker_verdict"],
            "assertions_verdict": "UNKNOWN", "artifact_origin": origin,
            "artifact_manifest": manifest,
        })
    counts = {"FAIL": 0, "UNKNOWN": 0}
    for run in runs:
        counts[run["test_verdict"]] += 1
    return {
        "project_id": project_id, "status": "COMPLETED_WITH_UNVERIFIED_PHASES",
        "regression_verdict": "FAIL" if counts["FAIL"] else "UNKNOWN",
        "test_count": len(runs), "counts": counts, "runs": runs,
        "phase_order": list(_PHASES),
        "vendor_compatibility_verified": False,
        "provenance": {
            "collector": "LOCAL_OPERATOR_APPROVED_SEQUENTIAL_DO",
            "executable_sha256": profile.executable_sha256,
            "regression_seeds_source": "OPERATOR_CONFIGURED_NOT_OBSERVED",
        },
    }
