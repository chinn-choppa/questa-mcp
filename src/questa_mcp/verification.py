"""Модель свидетельств верификации: процесс != пройденный тест.

Данные MCP-запроса недоверенные. Только внутренний коллектор может выставить
attested=True после подтверждённого локального выполнения.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .diagnostics import parse_diagnostics_text

MAX_REPORT_BYTES = 1_048_576
MAX_RUNS = 32
_PHASES = ("compile", "elaboration", "simulation")
_TEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _integer(value: object, name: str, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= maximum:
        raise ValueError(f"INVALID_{name.upper()}")
    return value


def _bounded_text(value: object, name: str, maximum: int = 128) -> str:
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise ValueError(f"INVALID_{name.upper()}")
    return value


def _bounded_request(value: object) -> None:
    try:
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise ValueError("INVALID_JSON_REPORT") from exc
    if size > MAX_REPORT_BYTES:
        raise ValueError("REPORT_TOO_LARGE")


def _line_evidence(evidence: object, name: str) -> dict[str, object] | None:
    if evidence is None:
        return None
    if not isinstance(evidence, dict):
        raise ValueError(f"INVALID_{name.upper()}_EVIDENCE")
    if set(evidence) != {"source_line", "raw"}:
        raise ValueError(f"INVALID_{name.upper()}_EVIDENCE")
    line = _integer(evidence["source_line"], "source_line", 1_000_000)
    if line == 0:
        raise ValueError("INVALID_SOURCE_LINE")
    raw = _bounded_text(evidence["raw"], "raw", 4096)
    if not raw:
        raise ValueError("INVALID_RAW")
    return {"source_line": line, "raw": raw}


def _phase_result(phase: str, value: object) -> dict[str, object]:
    if value is None:
        return {
            "state": "NOT_RUN", "exit_code": None, "diagnostic_failures": 0,
            "failure_evidence": [], "log_sha256": None,
        }
    if not isinstance(value, dict):
        raise ValueError("INVALID_PHASE")
    allowed = {"started", "completed", "exit_code", "timed_out", "cancelled", "log", "tool"}
    if set(value) - allowed:
        raise ValueError("INVALID_PHASE_KEYS")
    started = value.get("started", False)
    completed = value.get("completed", False)
    timed_out = value.get("timed_out", False)
    cancelled = value.get("cancelled", False)
    if any(not isinstance(x, bool) for x in (started, completed, timed_out, cancelled)):
        raise ValueError("INVALID_PHASE_FLAGS")
    if timed_out and cancelled or completed and (timed_out or cancelled):
        raise ValueError("CONTRADICTORY_PHASE_FLAGS")
    if not started and (completed or timed_out or cancelled):
        raise ValueError("CONTRADICTORY_PHASE_FLAGS")
    exit_code = value.get("exit_code")
    if exit_code is not None and (
        not isinstance(exit_code, int) or isinstance(exit_code, bool) or not -(2**31) <= exit_code <= 2**31 - 1
    ):
        raise ValueError("INVALID_EXIT_CODE")
    if exit_code is not None and not started:
        raise ValueError("CONTRADICTORY_PHASE_FLAGS")
    if completed and exit_code is None:
        raise ValueError("MISSING_EXIT_CODE")
    log = _bounded_text(value.get("log", ""), "log", MAX_REPORT_BYTES)
    tool = value.get("tool", "vlog" if phase == "compile" else "vsim")
    if tool not in ("vlog", "vcom", "vsim"):
        raise ValueError("INVALID_PHASE_TOOL")
    found = parse_diagnostics_text(log, tool, limit=32)
    evidence = [
        {"source_line": item["source_line"], "raw": item["raw"], "code": item["code"]}
        for item in found["items"] if item["severity"] in ("fatal", "error")
    ][:8]
    failures = found["failure_evidence_count"]
    if not started:
        state = "NOT_RUN"
    elif failures:
        state = "FAILED"
    elif cancelled:
        state = "CANCELLED"
    elif timed_out:
        state = "TIMEOUT"
    elif exit_code is not None and exit_code != 0:
        state = "FAILED"
    elif completed and exit_code == 0:
        state = "COMPLETED"
    else:
        state = "UNKNOWN"
    return {
        "state": state,
        "exit_code": exit_code,
        "diagnostic_failures": failures,
        "failure_evidence": evidence,
        "log_sha256": hashlib.sha256(log.encode("utf-8")).hexdigest() if started else None,
    }


def _checker_result(value: object) -> dict[str, object]:
    if value is None:
        return {"state": "NOT_RUN", "checks_run": 0, "failures": 0, "evidence": None}
    if not isinstance(value, dict) or set(value) - {
        "executed", "completed", "checks_run", "failures", "success_evidence", "failure_evidence"
    }:
        raise ValueError("INVALID_CHECKER")
    executed, completed = value.get("executed", False), value.get("completed", False)
    if not isinstance(executed, bool) or not isinstance(completed, bool):
        raise ValueError("INVALID_CHECKER_FLAGS")
    if completed and not executed:
        raise ValueError("CONTRADICTORY_CHECKER_FLAGS")
    checks = _integer(value.get("checks_run", 0), "checks_run", 1_000_000)
    failures = _integer(value.get("failures", 0), "failures", 1_000_000)
    if failures > checks or (not executed and (checks or failures)):
        raise ValueError("CONTRADICTORY_CHECKER_COUNTS")
    success = _line_evidence(value.get("success_evidence"), "success")
    failure = _line_evidence(value.get("failure_evidence"), "failure")
    if not executed:
        state, evidence = "NOT_RUN", None
    elif failures > 0 and failure:
        state, evidence = "FAILED", failure
    elif completed and checks > 0 and failures == 0 and success:
        state, evidence = "REPORTED_COMPLETE", success
    else:
        state, evidence = "UNKNOWN", failure
    return {"state": state, "checks_run": checks, "failures": failures, "evidence": evidence}


def assess_run(record: object, *, attested: bool = False) -> dict[str, object]:
    """Оценить фазовую картину; клиент MCP никогда не может указать attested."""
    _bounded_request(record)
    if not isinstance(record, dict):
        raise ValueError("INVALID_RECORD")
    if set(record) - {"test_id", "seed", "tool", "tool_version", "os", "artifacts", "phases", "checker"}:
        raise ValueError("INVALID_RECORD_KEYS")
    test_id = record.get("test_id")
    if not isinstance(test_id, str) or not _TEST_ID.fullmatch(test_id):
        raise ValueError("INVALID_TEST_ID")
    seed = record.get("seed")
    if seed is not None:
        seed = _integer(seed, "seed", 2**32 - 1)
    tool = _bounded_text(record.get("tool", ""), "tool")
    if tool not in {"questa", "modelsim"}:
        raise ValueError("INVALID_TOOL")
    version = _bounded_text(record.get("tool_version", ""), "tool_version")
    platform = _bounded_text(record.get("os", ""), "os")
    artifacts = record.get("artifacts", {})
    if not isinstance(artifacts, dict) or len(artifacts) > 16:
        raise ValueError("INVALID_ARTIFACTS")
    for key, digest in artifacts.items():
        if not isinstance(key, str) or not _TEST_ID.fullmatch(key) or (
            not isinstance(digest, str) or not _SHA256.fullmatch(digest)
        ):
            raise ValueError("INVALID_ARTIFACT_HASH")

    supplied = record.get("phases", {})
    if not isinstance(supplied, dict) or set(supplied) - set(_PHASES):
        raise ValueError("INVALID_PHASES")
    phases = {phase: _phase_result(phase, supplied.get(phase)) for phase in _PHASES}
    checker = _checker_result(record.get("checker"))
    failures = [phase for phase, summary in phases.items() if summary["state"] == "FAILED"]
    if checker["state"] == "FAILED":
        failures.append("checker")
    all_completed = all(summary["state"] == "COMPLETED" for summary in phases.values())
    checker_positive = checker["state"] == "REPORTED_COMPLETE"
    if failures:
        verdict, reason = "FAIL", f"FAILURE_IN_{failures[0].upper()}"
    elif all_completed and checker_positive and attested:
        verdict, reason = "PASS", "ATTESTED_CHECKER_COMPLETED"
    elif not any(phase["state"] != "NOT_RUN" for phase in phases.values()) and checker["state"] == "NOT_RUN":
        verdict, reason = "NOT_RUN", "NO_EXECUTION_EVIDENCE"
    else:
        verdict, reason = "UNKNOWN", (
            "UNVERIFIED_POSITIVE_EVIDENCE" if all_completed and checker_positive and not attested
            else "INCOMPLETE_OR_MISSING_CHECKER"
        )
    return {
        "test_id": test_id, "seed": seed,
        "tool": tool, "tool_version": version, "os": platform,
        "artifacts": dict(artifacts),
        "phases": phases, "checker": checker,
        "test_verdict": verdict, "reason": reason,
        "failure_source": failures[0] if failures else None,
        "provenance": "ATTESTED_INTERNAL" if attested else "CALLER_SUPPLIED_UNVERIFIED",
        "reported_checker_pass": checker_positive,
    }


def assess_regression(records: object, *, attested: bool = False) -> dict[str, object]:
    """Сводка тестов с независимыми verdict; непроверенные PASS не повышаются."""
    _bounded_request(records)
    if not isinstance(records, list) or len(records) > MAX_RUNS:
        raise ValueError("INVALID_REGRESSION_SIZE")
    runs = [assess_run(record, attested=attested) for record in records]
    keys = [(r["test_id"], r["seed"]) for r in runs]
    if len(set(keys)) != len(keys):
        raise ValueError("DUPLICATE_TEST_AND_SEED")
    summary = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0, "NOT_RUN": 0}
    for run in runs:
        summary[run["test_verdict"]] += 1
    if summary["FAIL"]:
        verdict = "FAIL"
    elif not runs or summary["NOT_RUN"] == len(runs):
        verdict = "NOT_RUN"
    elif summary["PASS"] == len(runs):
        verdict = "PASS"
    else:
        verdict = "UNKNOWN"
    return {
        "regression_verdict": verdict, "test_count": len(runs), "counts": summary,
        "runs": runs, "provenance": "ATTESTED_INTERNAL" if attested else "CALLER_SUPPLIED_UNVERIFIED",
    }
