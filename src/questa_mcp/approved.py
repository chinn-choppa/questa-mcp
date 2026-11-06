"""Запуск только вручную разрешённых DO-профилей: без произвольного Tcl из MCP."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .artifact_handoff import ArtifactSpec, inspect_approved_artifacts, validate_artifact_specs
from .diagnostics import parse_diagnostics_text
from .junit_evidence import MAX_TESTS, analyze_junit_bytes, read_junit_artifact

CONFIG_ENV = "QUESTA_MCP_PROJECTS_CONFIG"
MAX_CONFIG_BYTES = 65_536
MAX_DO_BYTES = 131_072
MAX_OUTPUT_BYTES = 262_144
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_CASE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
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
    checker_format: str | None = None
    expected_tests: tuple[str, ...] = ()
    executable_sha256: str | None = None
    artifact_specs: tuple[ArtifactSpec, ...] = ()
    expose_artifact_paths: bool = False
    phase_scripts: tuple[tuple[str, Path, str], ...] = ()
    regression_seeds: tuple[int, ...] = ()
    run_artifact_root: Path | None = None
    run_artifact_specs: tuple[ArtifactSpec, ...] = ()


def _absolute_file(value: object) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("INVALID_PATH")
    p = Path(value)
    if not p.is_absolute() or p.is_symlink() or not p.is_file():
        raise ValueError("INVALID_PATH")
    return p.resolve(strict=True)


def _hash_executable(path: Path) -> str:
    """Хешировать binary потоково, без следования конечным ссылкам."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("EXECUTABLE_NOT_REGULAR")
        digest = hashlib.sha256()
        while data := handle.read(1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


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
        checker = item.get("checker")
        checker_format: str | None = None
        expected_tests: tuple[str, ...] = ()
        if checker is not None:
            if not isinstance(checker, dict) or set(checker) != {"format", "expected_tests"}:
                raise ValueError("INVALID_CHECKER_CONFIG")
            if checker["format"] != "cocotb-junit-v1":
                raise ValueError("UNSUPPORTED_CHECKER")
            names = checker["expected_tests"]
            if (not isinstance(names, list) or not 1 <= len(names) <= MAX_TESTS
                    or any(not isinstance(x, str) or not _CASE_ID.fullmatch(x) for x in names)
                    or len(set(names)) != len(names)):
                raise ValueError("INVALID_EXPECTED_TESTS")
            checker_format = "cocotb-junit-v1"
            expected_tests = tuple(names)
        binary_digest = item.get("executable_sha256")
        if binary_digest is not None and (
            not isinstance(binary_digest, str) or not _SHA256.fullmatch(binary_digest)
        ):
            raise ValueError("INVALID_EXECUTABLE_HASH")
        if checker_format and binary_digest is None:
            raise ValueError("EXECUTABLE_HASH_REQUIRED")
        artifact_specs = validate_artifact_specs(item.get("artifacts"))
        reveal_paths = item.get("expose_artifact_paths", False)
        if not isinstance(reveal_paths, bool):
            raise ValueError("INVALID_ARTIFACT_PATH_DISCLOSURE")
        # Только фиксированный набор DO-профилей, заранее утверждённых оператором.
        phases_config = item.get("phase_scripts")
        phase_scripts: tuple[tuple[str, Path, str], ...] = ()
        regression_seeds: tuple[int, ...] = ()
        if phases_config is not None:
            if (not isinstance(phases_config, dict)
                    or set(phases_config) != {"compile", "elaboration", "simulation"}
                    or binary_digest is None):
                raise ValueError("INVALID_PHASE_CONFIG")
            ordered_phases: list[tuple[str, Path, str]] = []
            for phase_name in ("compile", "elaboration", "simulation"):
                phase = phases_config[phase_name]
                if not isinstance(phase, dict) or set(phase) != {"do_script", "do_sha256"}:
                    raise ValueError("INVALID_PHASE_CONFIG")
                do_file = _approved_file(workspace, phase["do_script"])
                do_digest = phase["do_sha256"]
                if not isinstance(do_digest, str) or not _SHA256.fullmatch(do_digest):
                    raise ValueError("INVALID_PHASE_HASH")
                ordered_phases.append((phase_name, do_file, do_digest))
            phase_scripts = tuple(ordered_phases)
            seeds = item.get("regression_seeds", [0])
            if (not isinstance(seeds, list) or not 1 <= len(seeds) <= 8
                    or any(not isinstance(seed, int) or isinstance(seed, bool)
                           or not 0 <= seed <= 2**32 - 1 for seed in seeds)
                    or len(set(seeds)) != len(seeds)):
                raise ValueError("INVALID_REGRESSION_SEEDS")
            regression_seeds = tuple(seeds)
        elif "regression_seeds" in item:
            raise ValueError("PHASE_CONFIG_REQUIRED")
        # Опциональный каталог для новых выходных данных каждого seed.
        run_root: Path | None = None
        run_artifacts: tuple[ArtifactSpec, ...] = ()
        if "run_artifacts" in item or "run_artifacts_dir" in item:
            if not phase_scripts or "run_artifacts" not in item or "run_artifacts_dir" not in item:
                raise ValueError("PHASE_RUN_ARTIFACTS_REQUIRED")
            specs = validate_artifact_specs(item["run_artifacts"])
            if not specs:
                raise ValueError("EMPTY_RUN_ARTIFACTS")
            raw_output = item["run_artifacts_dir"]
            if (not isinstance(raw_output, str) or not raw_output or len(raw_output) > 512
                    or "\\" in raw_output or ":" in raw_output or "\x00" in raw_output):
                raise ValueError("INVALID_RUN_ARTIFACT_ROOT")
            rel_output = PurePosixPath(raw_output)
            if rel_output.is_absolute() or any(p in ("", ".", "..") for p in raw_output.split("/")):
                raise ValueError("INVALID_RUN_ARTIFACT_ROOT")
            candidate = workspace
            for part in rel_output.parts:
                candidate = candidate / part
                if candidate.is_symlink() or (hasattr(candidate, "is_junction") and candidate.is_junction()):
                    raise ValueError("UNSAFE_RUN_ARTIFACT_ROOT")
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(workspace) or not resolved.is_dir():
                raise ValueError("INVALID_RUN_ARTIFACT_ROOT")
            run_root, run_artifacts = resolved, specs
        profiles[key] = ApprovedProject(
            key, workspace, executable, script, digest, seconds, max_bytes, expose,
            checker_format, expected_tests, binary_digest, artifact_specs, reveal_paths,
            phase_scripts, regression_seeds, run_root, run_artifacts,
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


def _verified_do_bytes(profile: ApprovedProject) -> bytes:
    """Прочитать фиксированную версию DO и сверить хеш до передачи симулятору."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(profile.script, flags)
    with os.fdopen(descriptor, "rb") as source:
        if not source.seekable():
            raise ValueError("INVALID_SCRIPT")
        if not profile.script.resolve(strict=True).is_relative_to(profile.workspace):
            raise ValueError("INVALID_SCRIPT")
        contents = source.read(MAX_DO_BYTES + 1)
    if len(contents) > MAX_DO_BYTES:
        raise ValueError("SCRIPT_TOO_LARGE")
    if hashlib.sha256(contents).hexdigest() != profile.script_sha256:
        raise ValueError("DO_HASH_MISMATCH")
    return contents


async def _kill_tree(proc: asyncio.subprocess.Process) -> bool:
    """Вернуть true, только если остановка дерева подтверждена доступным механизмом."""
    if proc.returncode is not None:
        return False
    tree_signalled = False
    if os.name == "nt":
        winroot = os.environ.get("SystemRoot", r"C:\Windows")
        taskkill = Path(winroot) / "System32" / "taskkill.exe"
        if taskkill.is_file():
            try:
                killer = await asyncio.create_subprocess_exec(
                    str(taskkill), "/PID", str(proc.pid), "/T", "/F",
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                tree_signalled = await asyncio.wait_for(killer.wait(), timeout=5) == 0
            except (OSError, asyncio.TimeoutError):
                tree_signalled = False
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            tree_signalled = True
        except (ProcessLookupError, PermissionError):
            tree_signalled = False
    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        return False
    return tree_signalled and proc.returncode is not None




def list_approved_artifacts(project_id: str) -> dict[str, object]:
    """Только оператором разрешённые файлы; без произвольных путей от MCP."""
    if not isinstance(project_id, str) or not _ID.fullmatch(project_id):
        return {"state": "DENIED", "items": [], "eda_executed": False}
    if not os.getenv(CONFIG_ENV):
        return {"state": "NOT_CONFIGURED", "items": [], "eda_executed": False}
    try:
        profile = _load_approved_profiles().get(project_id)
        if profile is None:
            return {"state": "DENIED", "items": [], "eda_executed": False}
        if not profile.artifact_specs:
            return {"state": "NOT_CONFIGURED", "items": [], "eda_executed": False}
        manifest = inspect_approved_artifacts(
            profile.workspace, profile.artifact_specs,
            expose_paths=profile.expose_artifact_paths,
        )
        return {"project_id": project_id, "eda_executed": False, **manifest}
    except (OSError, ValueError, json.JSONDecodeError):
        return {"state": "INVALID_CONFIGURATION", "items": [], "eda_executed": False}



def list_run_artifacts(project_id: str, run_id: str) -> dict[str, object]:
    """Только ранее разрешённые имена в конкретном наблюдаемом каталоге запуска."""
    if (not isinstance(project_id, str) or not _ID.fullmatch(project_id)
            or not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{24}", run_id)):
        return {"state": "DENIED", "items": [], "eda_executed": False}
    if not os.getenv(CONFIG_ENV):
        return {"state": "NOT_CONFIGURED", "items": [], "eda_executed": False}
    try:
        profile = _load_approved_profiles().get(project_id)
        if profile is None:
            return {"state": "DENIED", "items": [], "eda_executed": False}
        root = profile.run_artifact_root
        if root is None or not profile.run_artifact_specs:
            return {"state": "NOT_CONFIGURED", "items": [], "eda_executed": False}
        dirname = root / run_id
        if dirname.is_symlink() or (hasattr(dirname, "is_junction") and dirname.is_junction()):
            return {"state": "UNSAFE_RUN_DIRECTORY", "items": [], "eda_executed": False}
        if not dirname.is_dir() or dirname.resolve(strict=True).parent != root:
            return {"state": "RUN_NOT_FOUND", "items": [], "eda_executed": False}
        manifest = inspect_approved_artifacts(
            dirname, profile.run_artifact_specs,
            expose_paths=profile.expose_artifact_paths,
        )
        for entry in manifest["items"]:
            observed = entry["state"] in {"HASHED", "HASH_SKIPPED_LARGE_FILE"}
            entry["origin"] = (
                "OBSERVED_IN_RUN_DIRECTORY_NOT_VENDOR_ATTESTED"
                if observed else "NO_RUN_ASSOCIATION"
            )
            entry["observed_in_run_id"] = run_id if observed else None
            entry["produced_by_run_id"] = None
        return {
            "project_id": project_id, "run_id": run_id, "eda_executed": False,
            "origin": "RUN_DIRECTORY_EXISTS_NOT_VENDOR_ATTESTED", **manifest,
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {"state": "INVALID_CONFIGURATION", "items": [], "eda_executed": False}



def prepare_run_handoff(
    project_id: str, run_id: str, artifact_id: str, consumer: str
) -> dict[str, object]:
    """Не запускает анализатор: только явно разрешённый локальный указатель VCD/FST."""
    if (not isinstance(project_id, str) or not _ID.fullmatch(project_id)
            or not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{24}", run_id)
            or not isinstance(artifact_id, str) or not _ID.fullmatch(artifact_id)
            or not isinstance(consumer, str) or consumer not in ("wavepeek", "wave-mcp")):
        return {"status": "DENIED", "external_execution": "NOT_RUN"}
    try:
        profile = _load_approved_profiles().get(project_id)
        if profile is None:
            return {"status": "DENIED", "external_execution": "NOT_RUN"}
        if not profile.expose_artifact_paths:
            return {"status": "OPT_IN_REQUIRED", "external_execution": "NOT_RUN"}
        manifest = list_run_artifacts(project_id, run_id)
        if manifest["state"] != "OPERATOR_DECLARED_READ_ONLY":
            return {"status": manifest["state"], "external_execution": "NOT_RUN"}
        item = next((x for x in manifest["items"] if x["id"] == artifact_id), None)
        if item is None:
            return {"status": "ARTIFACT_NOT_ALLOWLISTED", "external_execution": "NOT_RUN"}
        if item["format"] not in ("VCD", "FST"):
            return {"status": "UNSUPPORTED_NATIVE_FORMAT", "external_execution": "NOT_RUN"}
        if item["state"] not in ("HASHED", "HASH_SKIPPED_LARGE_FILE") or not item["local_path"]:
            return {"status": "ARTIFACT_UNAVAILABLE", "external_execution": "NOT_RUN"}
        return {
            "status": "READY_FOR_EXTERNAL_CLIENT",
            "consumer": consumer, "project_id": project_id,
            "run_id": run_id, "artifact_id": artifact_id,
            "format": item["format"], "size_bytes": item["size_bytes"],
            "sha256": item["sha256"], "hash_status": item["state"],
            "local_path": item["local_path"], "format_validated": False,
            "origin": item["origin"], "vendor_attested": False,
            "external_execution": "NOT_RUN",
            "consumer_support": "DECLARED_FORMAT_NOT_INTEGRATION_TESTED",
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "INVALID_CONFIGURATION", "external_execution": "NOT_RUN"}


async def _await_protected(task: asyncio.Task) -> object:
    """Дождаться завершения дочерней задачи при повторных cancel() родителя."""
    current = asyncio.current_task()
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()
            if current is not None:
                # Только для ожидания cleanup; внешнее исключение повторно выдаётся вызывающим.
                current.uncancel()


async def _terminate_before_return(proc: asyncio.subprocess.Process) -> bool:
    """Не удалять DO snapshot до завершения операции очистки."""
    task = asyncio.create_task(_kill_tree(proc))
    return bool(await _await_protected(task))


async def _execute(
    profile: ApprovedProject, *, results_file: Path | None = None,
    seed: int | None = None, artifact_dir: Path | None = None,
) -> tuple[str, int | None, bytes]:
    """Снимать снимок DO в приватную папку, не передавать изменяемый исходник."""
    try:
        snapshot = _verified_do_bytes(profile)
    except ValueError as exc:
        return str(exc), None, b""
    except OSError:
        return "INVALID_SCRIPT", None, b""

    # Временный каталог вне недоверенного workspace, с ограниченными правами.
    with tempfile.TemporaryDirectory(prefix="questa-mcp-do-") as temporary:
        staged = Path(temporary) / "approved.do"
        with staged.open("xb") as handle:
            handle.write(snapshot)
        if os.name != "nt":
            staged.chmod(0o400)
        kwargs: dict[str, object] = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == "nt" else {"start_new_session": True}
        )
        extra: dict[str, object] = {}
        if results_file is not None or seed is not None or artifact_dir is not None:
            # Программный ввод ограничен именами переменных из реализации.
            environment = os.environ.copy()
            # Не наследовать потенциально опасные старые пути и seed из окружения.
            for key in ("COCOTB_RESULTS_FILE", "QUESTA_MCP_SEED", "QUESTA_MCP_ARTIFACT_DIR"):
                environment.pop(key, None)
            if results_file is not None:
                environment["COCOTB_RESULTS_FILE"] = str(results_file)
            if seed is not None:
                environment["QUESTA_MCP_SEED"] = str(seed)
            if artifact_dir is not None:
                environment["QUESTA_MCP_ARTIFACT_DIR"] = str(artifact_dir)
            extra["env"] = environment
        spawn = asyncio.create_task(
            asyncio.create_subprocess_exec(
                str(profile.executable), "-c", "-do", str(staged),
                cwd=str(profile.workspace),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                **kwargs, **extra,
            )
        )
        try:
            proc = await asyncio.shield(spawn)
        except OSError:
            return "TOOL_UNAVAILABLE", None, b""
        except asyncio.CancelledError:
            spawned = await _await_protected(spawn)
            await _terminate_before_return(spawned)
            raise

        data = bytearray()
        try:
            async with asyncio.timeout(profile.timeout_seconds):
                assert proc.stdout is not None
                while chunk := await proc.stdout.read(4096):
                    if len(data) + len(chunk) > profile.max_output_bytes:
                        data.extend(chunk[: max(0, profile.max_output_bytes - len(data))])
                        confirmed = await _kill_tree(proc)
                        state = "OUTPUT_LIMIT" if confirmed else "TERMINATION_UNCONFIRMED"
                        return state, proc.returncode, bytes(data)
                    data.extend(chunk)
                result = await proc.wait()
                return ("COMPLETED_UNVERIFIED" if result == 0 else "PROCESS_FAILED",
                        result, bytes(data))
        except TimeoutError:
            confirmed = await _kill_tree(proc)
            return ("TIMEOUT" if confirmed else "TERMINATION_UNCONFIRMED",
                    proc.returncode, bytes(data))
        except asyncio.CancelledError:
            await _terminate_before_return(proc)
            raise
        except BaseException:
            await _terminate_before_return(proc)
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
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "INVALID_CONFIGURATION", "test_verdict": "UNKNOWN", "eda_executed": False}

    # Для аттестации checker необходимо заранее закрепить конкретный binary.
    if profile.executable_sha256 is not None:
        try:
            if _hash_executable(profile.executable) != profile.executable_sha256:
                return {"status": "EXECUTABLE_HASH_MISMATCH",
                        "test_verdict": "UNKNOWN", "eda_executed": False}
        except (OSError, ValueError):
            return {"status": "EXECUTABLE_UNVERIFIED",
                    "test_verdict": "UNKNOWN", "eda_executed": False}

    # Один приватный каталог и новый путь результата для каждого выполнения.
    with tempfile.TemporaryDirectory(prefix="questa-mcp-checks-") as artifact_dir:
        report_path = Path(artifact_dir) / "results.xml"
        status, code, log = await _execute(
            profile, results_file=report_path if profile.checker_format else None
        )
        checker: dict[str, object] = {
            "format": profile.checker_format, "state": "NOT_CONFIGURED",
            "reason": "CHECKER_NOT_CONFIGURED", "tests": 0,
            "failures": 0, "errors": 0, "skipped": 0,
            "expected_tests": len(profile.expected_tests), "report_sha256": None,
        }
        if profile.checker_format is not None:
            content, read_state = read_junit_artifact(report_path)
            if content is None:
                checker.update(state="UNKNOWN", reason=read_state)
            else:
                checker = analyze_junit_bytes(content, profile.expected_tests)

    log_decoded_without_loss = True
    try:
        decoded = log.decode("utf-8")
    except UnicodeDecodeError:
        decoded = log.decode("utf-8", errors="replace")
        log_decoded_without_loss = False
    parse_complete = True
    try:
        parsed = parse_diagnostics_text(decoded)
    except ValueError:
        parse_complete = False
        parsed = {"test_verdict": "UNKNOWN", "failure_evidence_count": 0,
                  "count": 0, "items": []}
    if status in {"PROCESS_FAILED", "COMPLETED_UNVERIFIED"} and _LICENSE.search(decoded):
        status = "LICENSE_ERROR_EVIDENCE"
    started = status not in {"TOOL_UNAVAILABLE", "DO_HASH_MISMATCH",
                             "SCRIPT_TOO_LARGE", "INVALID_SCRIPT"}
    binary_unchanged = True
    if started and profile.executable_sha256 is not None:
        try:
            binary_unchanged = (
                _hash_executable(profile.executable) == profile.executable_sha256
            )
        except (OSError, ValueError):
            binary_unchanged = False
        if not binary_unchanged:
            status = "EXECUTABLE_CHANGED"
    fail_process = status in {"PROCESS_FAILED", "LICENSE_ERROR_EVIDENCE"}
    fail_diagnostic = parsed["test_verdict"] == "FAIL"
    fail_checks = checker["state"] == "FAILED"
    completed_and_checked = (
        status == "COMPLETED_UNVERIFIED"
        and code == 0
        and checker["state"] == "PASSED"
        and not fail_diagnostic
        and parse_complete
        and log_decoded_without_loss
        and binary_unchanged
    )
    if fail_process or fail_diagnostic or fail_checks:
        verdict = "FAIL"
        checker_verdict = "FAIL" if fail_checks else "UNKNOWN"
    elif completed_and_checked:
        # JUnit подтверждает лишь cocotb-тесты, но не все внешние SVA/assertions.
        verdict = "UNKNOWN"
        checker_verdict = "PASS"
    else:
        verdict = "UNKNOWN"
        checker_verdict = "UNKNOWN"
    disclosed = parsed["items"][:20] if profile.expose_diagnostics else []
    return {
        "status": status,
        "exit_code": code,
        "eda_executed": started,
        "test_verdict": verdict,
        "checker_verdict": checker_verdict,
        "assertions_verdict": "UNKNOWN",
        "regression_verdict": "UNKNOWN",
        "verdict_basis": (
            "FRESH_JUNIT_CHECKER_PASS_ONLY" if checker_verdict == "PASS"
            else "OBSERVED_NEGATIVE_EVIDENCE" if verdict == "FAIL"
            else "INSUFFICIENT_EVIDENCE"
        ),
        "vendor_compatibility_verified": False,
        "transcript_parser_complete": parse_complete,
        "transcript_utf8_lossless": log_decoded_without_loss,
        "run_provenance": {
            "collector": "LOCAL_ALLOWLISTED_VSIM_PROCESS",
            "approved_do_sha256": profile.script_sha256 if started else None,
            "approved_executable_sha256": profile.executable_sha256 if started else None,
            "executable_unchanged": binary_unchanged,
            "stdout_sha256": hashlib.sha256(log).hexdigest(),
        },
        "checker": checker,
        "compile_status": "UNKNOWN",
        "elaboration_status": "UNKNOWN",
        "simulation_status": "UNKNOWN",
        "diagnostic_count": parsed["count"],
        "diagnostics": disclosed,
        "diagnostics_disclosed": profile.expose_diagnostics,
        "captured_log_sha256": hashlib.sha256(log).hexdigest(),
        "captured_bytes": len(log),
        "log_complete": status not in {"TIMEOUT", "OUTPUT_LIMIT", "TERMINATION_UNCONFIRMED"},
    }
