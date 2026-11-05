"""Запуск только вручную разрешённых DO-профилей: без произвольного Tcl из MCP."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .diagnostics import parse_diagnostics_text

CONFIG_ENV = "QUESTA_MCP_PROJECTS_CONFIG"
MAX_CONFIG_BYTES = 65_536
MAX_DO_BYTES = 131_072
MAX_OUTPUT_BYTES = 262_144
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_LICENSE = re.compile(
    r"license (?:check\s*out|checkout) failed|"
    r"(?:unable|cannot|failed) to (?:check\s*out|obtain) .*?license|"
    r"license (?:not available|unavailable)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ApprovedProject:
    project_id: str
    workspace: Path
    executable: Path
    script: Path
    script_sha256: str
    timeout_seconds: int
    max_output_bytes: int
    expose_diagnostics: bool


def _absolute_file(value: object) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("INVALID_PATH")
    p = Path(value)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise ValueError("INVALID_PATH")
    return p.resolve(strict=True)


def _approved_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or "\x00" in relative:
        raise ValueError("INVALID_SCRIPT")
    r = Path(relative)
    if r.is_absolute() or any(part in ("..", ".") for part in r.parts):
        raise ValueError("INVALID_SCRIPT")
    candidate = root / r
    for parent in (candidate, *list(candidate.parents)):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise ValueError("INVALID_SCRIPT")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file() or resolved.suffix.lower() != ".do":
        raise ValueError("INVALID_SCRIPT")
    if resolved.stat().st_size > MAX_DO_BYTES:
        raise ValueError("SCRIPT_TOO_LARGE")
    return resolved


def _load_approved_profiles() -> dict[str, ApprovedProject]:
    config_name = os.getenv(CONFIG_ENV)
    if not config_name:
        return {}
    config_path = _absolute_file(config_name)
    if config_path.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError("CONFIG_TOO_LARGE")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("projects"), dict):
        raise ValueError("INVALID_CONFIG")
    profiles: dict[str, ApprovedProject] = {}
    if len(raw["projects"]) > 32:
        raise ValueError("TOO_MANY_PROJECTS")
    for key, item in raw["projects"].items():
        if not isinstance(key, str) or not _ID.fullmatch(key) or not isinstance(item, dict):
            raise ValueError("INVALID_CONFIG")
        if item.get("operator_approved") is not True or item.get("disposable_workspace") is not True:
            raise ValueError("EXPLICIT_APPROVAL_REQUIRED")
        root_text = item.get("workspace")
        if not isinstance(root_text, str) or not root_text or "\x00" in root_text:
            raise ValueError("INVALID_WORKSPACE")
        workspace = Path(root_text)
        if not workspace.is_absolute() or workspace.is_symlink() or not workspace.is_dir():
            raise ValueError("INVALID_WORKSPACE")
        workspace = workspace.resolve(strict=True)
        executable = _absolute_file(item.get("executable"))
        if executable.name.lower() not in {"vsim", "vsim.exe"}:
            raise ValueError("EXECUTABLE_NOT_VSIM")
        script = _approved_file(workspace, item.get("do_script"))
        digest = item.get("do_sha256")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("MISSING_DO_HASH")
        seconds = item.get("timeout_seconds", 120)
        max_bytes = item.get("max_output_bytes", 65536)
        expose = item.get("expose_diagnostics", False)
        if not isinstance(seconds, int) or isinstance(seconds, bool) or not 1 <= seconds <= 3600:
            raise ValueError("INVALID_TIMEOUT")
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or not 1024 <= max_bytes <= MAX_OUTPUT_BYTES:
            raise ValueError("INVALID_OUTPUT_LIMIT")
        if not isinstance(expose, bool):
            raise ValueError("INVALID_DISCLOSURE_SETTING")
        profiles[key] = ApprovedProject(
            key, workspace, executable, script, digest, seconds, max_bytes, expose
        )
    return profiles


def list_approved_projects() -> dict[str, object]:
    """Не возвращать локальные пути, содержимое DO и переменные лицензий."""
    try:
        profiles = _load_approved_profiles()
    except (OSError, ValueError, json.JSONDecodeError):
        return {"state": "INVALID_CONFIGURATION", "projects": []}
    return {
        "state": "CONFIGURED" if os.getenv(CONFIG_ENV) else "NOT_CONFIGURED",
        "projects": sorted(profiles),
        "execution_supported": True,
    }


async def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    if os.name == "nt":
        # Windows не поддерживает os.killpg: используем фиксированный системный taskkill.
        winroot = os.environ.get("SystemRoot", r"C:\Windows")
        taskkill = Path(winroot) / "System32" / "taskkill.exe"
        if taskkill.is_file():
            try:
                killer = await asyncio.create_subprocess_exec(
                    str(taskkill), "/PID", str(proc.pid), "/T", "/F",
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(killer.wait(), timeout=5)
            except (OSError, asyncio.TimeoutError):
                pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        pass


async def _execute(profile: ApprovedProject) -> tuple[str, int | None, bytes]:
    kwargs: dict[str, object] = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt" else {"start_new_session": True}
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            str(profile.executable), "-c", "-do", str(profile.script),
            cwd=str(profile.workspace),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            **kwargs,
        )
    except OSError:
        return "TOOL_UNAVAILABLE", None, b""

    data = bytearray()
    try:
        async with asyncio.timeout(profile.timeout_seconds):
            assert proc.stdout is not None
            while chunk := await proc.stdout.read(4096):
                if len(data) + len(chunk) > profile.max_output_bytes:
                    data.extend(chunk[: max(0, profile.max_output_bytes - len(data))])
                    await _kill_tree(proc)
                    return "OUTPUT_LIMIT", proc.returncode, bytes(data)
                data.extend(chunk)
            result = await proc.wait()
            return ("COMPLETED_UNVERIFIED" if result == 0 else "PROCESS_FAILED",
                    result, bytes(data))
    except TimeoutError:
        await _kill_tree(proc)
        return "TIMEOUT", proc.returncode, bytes(data)
    except asyncio.CancelledError:
        await _kill_tree(proc)
        raise
    except BaseException:
        await _kill_tree(proc)
        raise


async def run_approved_project(project_id: str) -> dict[str, object]:
    """Выполнить зафиксированный сценарий; exit code 0 не подтверждает PASS."""
    if not isinstance(project_id, str) or not _ID.fullmatch(project_id):
        return {"status": "DENIED", "test_verdict": "UNKNOWN", "eda_executed": False}
    if not os.getenv(CONFIG_ENV):
        return {"status": "NOT_CONFIGURED", "test_verdict": "UNKNOWN", "eda_executed": False}
    try:
        profiles = _load_approved_profiles()
        profile = profiles.get(project_id)
        if profile is None:
            return {"status": "DENIED", "test_verdict": "UNKNOWN", "eda_executed": False}
        if hashlib.sha256(profile.script.read_bytes()).hexdigest() != profile.script_sha256:
            return {"status": "DO_HASH_MISMATCH", "test_verdict": "UNKNOWN", "eda_executed": False}
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "INVALID_CONFIGURATION", "test_verdict": "UNKNOWN", "eda_executed": False}

    status, code, log = await _execute(profile)
    try:
        parsed = parse_diagnostics_text(log.decode("utf-8", errors="replace"))
    except ValueError:
        parsed = {"test_verdict": "UNKNOWN", "count": 0, "items": []}
    if _LICENSE.search(log.decode("utf-8", errors="replace")):
        status = "LICENSE_ERROR_EVIDENCE"
    disclosed = parsed["items"][:20] if profile.expose_diagnostics else []
    return {
        "status": status,
        "exit_code": code,
        "eda_executed": status not in {"TOOL_UNAVAILABLE"},
        "test_verdict": parsed["test_verdict"],
        "compile_status": "UNKNOWN",
        "elaboration_status": "UNKNOWN",
        "simulation_status": "UNKNOWN",
        "diagnostic_count": parsed["count"],
        "diagnostics": disclosed,
        "diagnostics_disclosed": profile.expose_diagnostics,
        "captured_log_sha256": hashlib.sha256(log).hexdigest(),
        "captured_bytes": len(log),
        "log_complete": status not in {"TIMEOUT", "OUTPUT_LIMIT"},
    }
