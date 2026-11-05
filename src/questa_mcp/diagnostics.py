"""Консервативный разбор синтетических журналов Questa/ModelSim.

Парсер доказывает наличие диагностик, но не подтверждает успешный тест.
"""

from __future__ import annotations

import re

MAX_INPUT_BYTES = 1_048_576
MAX_ITEMS = 200
SUPPORTED_TOOLS = frozenset({"vsim", "vlog", "vcom"})

_DIAGNOSTIC = re.compile(
    r"^\s*(?:#\s*)?\*\*\s*(?P<level>Note|Info|Warning|Error|Fatal|Failure)\s*:"
    r"\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_UVM = re.compile(
    r"^\s*(?:#\s*)?UVM_(?P<level>INFO|WARNING|ERROR|FATAL)\s+@\s*"
    r"(?P<time>[^:]+):\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_CODE = re.compile(r"\((?P<code>(?:vlog|vcom|vsim)(?:-[A-Za-z0-9_]+)+)\)", re.IGNORECASE)
_LOCATION = re.compile(
    r"(?P<file>(?:[A-Za-z]:)?[/\\\w. \-]+?\.(?:sv|svh|v|vh|vhd|vhdl|vho))"
    r"\((?P<line>\d+)(?:,(?P<column>\d+))?\)\s*:",
    re.IGNORECASE,
)
_EXPLICIT_LOCATION = re.compile(
    r"\bFile:\s*(?P<file>.+?)\s+Line:\s*(?P<line>\d+)\b", re.IGNORECASE
)
_TIME = re.compile(
    r"\bTime:\s*(?P<time>[+-]?\d+(?:\.\d+)?\s*(?:fs|ps|ns|us|ms|s))\b",
    re.IGNORECASE,
)
_INSTANCE = re.compile(r"\bInstance:\s*(?P<instance>\S+)", re.IGNORECASE)


def parse_diagnostics_text(text: str, tool: str = "vsim", limit: int = 200) -> dict[str, object]:
    """Извлечь наблюдаемые ошибки без присвоения недоказанного PASS."""
    if not isinstance(text, str):
        raise ValueError("text должен быть строкой")
    try:
        byte_count = len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("text содержит некорректные Unicode-символы") from exc
    if byte_count > MAX_INPUT_BYTES:
        raise ValueError("Слишком большой вход: максимум 1 МиБ")
    if "\x00" in text:
        raise ValueError("text содержит NUL")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_ITEMS:
        raise ValueError("limit должен быть целым числом от 1 до 200")
    if tool not in SUPPORTED_TOOLS:
        raise ValueError("Неизвестный EDA-инструмент")

    items: list[dict[str, object]] = []
    count = 0
    unrecognized = 0
    failures = 0
    for source_line, raw in enumerate(text.splitlines(), start=1):
        match = _DIAGNOSTIC.match(raw)
        uvm = _UVM.match(raw) if match is None else None
        if match is None and uvm is None:
            if raw.strip():
                unrecognized += 1
            continue

        groups = (match or uvm).groupdict()
        level = groups["level"].lower()
        severity = {"failure": "fatal"}.get(level, level)
        if severity in {"error", "fatal"}:
            failures += 1
        count += 1
        if len(items) >= limit:
            continue

        body = groups["body"]
        code_match = _CODE.search(body) if match else None
        location_match = _LOCATION.search(body)
        explicit_match = _EXPLICIT_LOCATION.search(body) if location_match is None else None
        time_match = _TIME.search(body)
        instance_match = _INSTANCE.search(body)
        code = code_match.group("code") if code_match else None
        file = None
        line = None
        column = None
        if location_match:
            file = location_match.group("file")
            line = int(location_match.group("line"))
            column = (
                int(location_match.group("column"))
                if location_match.group("column") is not None else None
            )
        elif explicit_match:
            file = explicit_match.group("file").strip()
            line = int(explicit_match.group("line"))

        message = body
        if code_match:
            message = message.replace(code_match.group(0), "", 1)
        if location_match:
            message = message.replace(location_match.group(0), "", 1)
        message = message.strip(" :")
        items.append({
            "severity": severity,
            "code": code if match else f"UVM_{level.upper()}",
            "emitter": code.split("-")[0].lower() if code else ("uvm" if uvm else tool),
            "file": file,
            "line": line,
            "column": column,
            "time": (groups.get("time") or "").strip() if uvm else (
                time_match.group("time") if time_match else None
            ),
            "instance": instance_match.group("instance") if instance_match else None,
            "message": message,
            "source_line": source_line,
            "raw": raw,
            "format": "uvm" if uvm else "questa_message",
            "confidence": "HIGH",
        })

    return {
        "tool": tool,
        "count": count,
        "truncated": count > len(items),
        "unrecognized_lines": unrecognized,
        "parser_status": "UNKNOWN" if count == 0 else (
            "PARTIAL" if unrecognized or count > len(items) else "RECOGNIZED"
        ),
        "test_verdict": "FAIL" if failures else "UNKNOWN",
        "failure_evidence_count": failures,
        "eda_executed": False,
        "items": items,
    }
