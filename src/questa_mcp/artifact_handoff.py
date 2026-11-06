"""Read-only manifest for operator-declared waveform/coverage files.

No waveform parsing, vendor conversion, network calls or process launch.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_ARTIFACTS = 8
MAX_HASH_BYTES = 8 * 1024 * 1024
_ARTIFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_FORMATS = frozenset({"vcd", "fst", "wlf", "ucdb"})
_TIME_UNITS = frozenset({"fs", "ps", "ns", "us", "ms", "s"})


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    parts: tuple[str, ...]
    format: str
    declared_time_unit: str | None


def validate_artifact_specs(value: object) -> tuple[ArtifactSpec, ...]:
    """Принимать только конечный список фиксированных оператором файлов."""
    if value is None:
        return ()
    if not isinstance(value, list) or len(value) > MAX_ARTIFACTS:
        raise ValueError("INVALID_ARTIFACTS")
    specs: list[ArtifactSpec] = []
    ids: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) - {
            "id", "path", "format", "declared_time_unit"
        }:
            raise ValueError("INVALID_ARTIFACT_DEFINITION")
        aid = item.get("id")
        raw = item.get("path")
        kind = item.get("format")
        unit = item.get("declared_time_unit")
        if not isinstance(aid, str) or not _ARTIFACT_ID.fullmatch(aid) or aid in ids:
            raise ValueError("INVALID_ARTIFACT_ID")
        if not isinstance(raw, str) or not raw or len(raw) > 512 or "\\" in raw or ":" in raw or "\x00" in raw:
            raise ValueError("INVALID_ARTIFACT_PATH")
        rel = PurePosixPath(raw)
        if rel.is_absolute() or not rel.parts or any(
            p in ("", ".", "..") for p in raw.split("/")
        ):
            raise ValueError("INVALID_ARTIFACT_PATH")
        if not isinstance(kind, str) or kind not in _FORMATS or rel.suffix.lower() != "." + kind:
            raise ValueError("INVALID_ARTIFACT_FORMAT")
        if unit is not None and (not isinstance(unit, str) or unit not in _TIME_UNITS):
            raise ValueError("INVALID_TIME_UNIT")
        ids.add(aid)
        specs.append(ArtifactSpec(aid, rel.parts, kind, unit))
    return tuple(specs)


def _safe_candidate(root: Path, parts: tuple[str, ...]) -> Path | None:
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            return None
        junction = getattr(current, "is_junction", None)
        if junction is not None and junction():
            return None
    try:
        candidate = current.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return candidate if candidate.is_relative_to(root) else None


def _hash_small_file(path: Path) -> tuple[str | None, int, str]:
    """Считать файл только ограниченно; слишком большие файлы не хешировать."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                return None, 0, "NOT_REGULAR_FILE"
            if before.st_size > MAX_HASH_BYTES:
                return None, before.st_size, "HASH_SKIPPED_LARGE_FILE"
            digest = hashlib.sha256()
            count = 0
            while data := handle.read(64 * 1024):
                count += len(data)
                if count > MAX_HASH_BYTES:
                    return None, count, "HASH_SKIPPED_GROWING_FILE"
                digest.update(data)
            after = os.fstat(handle.fileno())
        # Проверка метаданных вместе с именем снижает риск гонки и подмены.
        current = path.stat()
        identity = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns)
        if identity(before) != identity(after) or identity(after) != identity(current):
            return None, after.st_size, "MUTATED_DURING_INSPECTION"
        return digest.hexdigest(), after.st_size, "HASHED"
    except (OSError, ValueError):
        return None, 0, "UNREADABLE"


def _routes(fmt: str) -> dict[str, str]:
    if fmt in ("vcd", "fst"):
        return {
            "wavepeek": "EXTERNAL_FORMAT_SUPPORTED_NOT_TESTED_HERE",
            "wave_mcp": "EXTERNAL_FORMAT_SUPPORTED_NOT_TESTED_HERE",
            "conversion": "NOT_REQUIRED",
            "coverage": "NOT_APPLICABLE",
        }
    if fmt == "wlf":
        return {
            "wavepeek": "NOT_SUPPORTED_DIRECTLY",
            "wave_mcp": "NOT_SUPPORTED_DIRECTLY",
            "conversion": "VENDOR_WLF2VCD_MANUAL_NOT_RUN",
            "coverage": "NOT_APPLICABLE",
        }
    return {
        "wavepeek": "NOT_APPLICABLE",
        "wave_mcp": "NOT_APPLICABLE",
        "conversion": "NOT_DEFINED",
        "coverage": "VENDOR_UCDB_EXTERNAL_ONLY",
    }


def inspect_approved_artifacts(
    workspace: Path, specs: tuple[ArtifactSpec, ...], *, expose_paths: bool = False
) -> dict[str, object]:
    """Описать разрешённые файлы без передачи их содержимого."""
    if not isinstance(expose_paths, bool):
        raise ValueError("INVALID_DISCLOSURE_SETTING")
    root = workspace.resolve(strict=True)
    items: list[dict[str, object]] = []
    for spec in specs:
        path = _safe_candidate(root, spec.parts)
        sha256: str | None = None
        size: int | None = None
        if path is None:
            state = "MISSING_OR_UNSAFE_PATH"
        else:
            sha256, recorded_size, state = _hash_small_file(path)
            size = recorded_size if state not in ("UNREADABLE", "NOT_REGULAR_FILE") else None
        items.append({
            "id": spec.artifact_id,
            "format": spec.format.upper(),
            "declared_time_unit": spec.declared_time_unit,
            "time_unit_source": ("OPERATOR_DECLARED_NOT_VERIFIED"
                                 if spec.declared_time_unit is not None else "NOT_SPECIFIED"),
            "size_bytes": size,
            "sha256": sha256,
            "state": state,
            "format_validated": False,
            "produced_by_run_id": None,
            "origin": "EXISTING_WORKSPACE_FILE_NOT_ATTESTED",
            "external_execution": "NOT_RUN",
            "paths_disclosed": bool(expose_paths and path is not None),
            "local_path": str(path) if expose_paths and path is not None else None,
            "routes": _routes(spec.format),
        })
    return {"state": "OPERATOR_DECLARED_READ_ONLY", "count": len(items), "items": items}
