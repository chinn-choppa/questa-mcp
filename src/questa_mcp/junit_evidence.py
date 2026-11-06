"""Строгое чтение свежего cocotb JUnit XML без выполнения сторонних команд."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_XML_BYTES = 131_072
MAX_TESTS = 256
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def read_junit_artifact(path: Path) -> tuple[bytes | None, str]:
    """Открыть только обычный файл; не следовать конечным символьным ссылкам."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        if path.is_symlink():
            return None, "UNSAFE_SYMLINK"
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                return None, "NOT_REGULAR_FILE"
            if info.st_size > MAX_XML_BYTES:
                return None, "REPORT_TOO_LARGE"
            raw = handle.read(MAX_XML_BYTES + 1)
    except FileNotFoundError:
        return None, "REPORT_MISSING"
    except (OSError, ValueError):
        return None, "REPORT_UNREADABLE"
    if len(raw) > MAX_XML_BYTES:
        return None, "REPORT_TOO_LARGE"
    return raw, "READ_OK"


def analyze_junit_bytes(content: bytes, expected_names: tuple[str, ...]) -> dict[str, object]:
    """Сопоставить полную структуру JUnit с утверждённым списком проверок."""
    result: dict[str, object] = {
        "format": "cocotb-junit-v1", "state": "UNKNOWN", "reason": "INVALID_REPORT",
        "tests": 0, "failures": 0, "errors": 0, "skipped": 0,
        "expected_tests": len(expected_names), "report_sha256": hashlib.sha256(content).hexdigest(),
    }
    if not content or len(content) > MAX_XML_BYTES:
        result["reason"] = "REPORT_SIZE_INVALID"
        return result
    if b"\x00" in content or b"<!doctype" in content.lower() or b"<!entity" in content.lower():
        result["reason"] = "XML_UNSAFE"
        return result
    if len(set(expected_names)) != len(expected_names) or not expected_names or len(expected_names) > MAX_TESTS:
        result["reason"] = "INVALID_EXPECTED_TESTS"
        return result
    if any(not _NAME.fullmatch(x) for x in expected_names):
        result["reason"] = "INVALID_EXPECTED_TESTS"
        return result
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError, UnicodeError):
        result["reason"] = "XML_INVALID"
        return result
    if root.tag == "testsuites":
        suites = list(root)
        if not suites or any(s.tag != "testsuite" for s in suites):
            result["reason"] = "XML_UNSUPPORTED_SCHEMA"
            return result
    elif root.tag == "testsuite":
        suites = [root]
    else:
        result["reason"] = "XML_UNSUPPORTED_SCHEMA"
        return result

    all_names: list[str] = []
    total_failures = total_errors = total_skips = 0
    for suite in suites:
        cases = list(suite.findall("testcase"))
        if any(node.tag not in ("testcase", "properties", "system-out", "system-err") for node in suite):
            result["reason"] = "XML_UNSUPPORTED_SCHEMA"
            return result
        if len(all_names) + len(cases) > MAX_TESTS:
            result["reason"] = "TEST_COUNT_EXCEEDED"
            return result
        suite_failures = suite_errors = suite_skips = 0
        for case in cases:
            name = case.attrib.get("name", "")
            if not _NAME.fullmatch(name):
                result["reason"] = "INVALID_TEST_NAME"
                return result
            all_names.append(name)
            children = list(case)
            statuses = [node.tag for node in children if node.tag in ("failure", "error", "skipped")]
            if len(statuses) > 1 or any(
                node.tag not in ("failure", "error", "skipped", "properties", "system-out", "system-err")
                for node in children
            ):
                result["reason"] = "XML_UNSUPPORTED_SCHEMA"
                return result
            suite_failures += statuses.count("failure")
            suite_errors += statuses.count("error")
            suite_skips += statuses.count("skipped")
            if case.attrib.get("status", "passed") not in ("passed", "success") and not statuses:
                result["reason"] = "XML_UNSUPPORTED_SCHEMA"
                return result

        # В отличие от доверия к атрибутам, сверяем их с реальными testcase.
        for key, observed in (
            ("tests", len(cases)), ("failures", suite_failures),
            ("errors", suite_errors), ("skipped", suite_skips),
        ):
            value = suite.attrib.get(key)
            if value is None or not value.isascii() or not value.isdecimal() or int(value) != observed:
                result["reason"] = "INCONSISTENT_COUNTS"
                return result
        total_failures += suite_failures
        total_errors += suite_errors
        total_skips += suite_skips

    result.update(
        tests=len(all_names), failures=total_failures,
        errors=total_errors, skipped=total_skips,
    )
    if len(set(all_names)) != len(all_names):
        result["reason"] = "DUPLICATE_TEST_NAMES"
    elif set(all_names) != set(expected_names):
        result["reason"] = "EXPECTED_TESTS_MISMATCH"
    elif total_failures or total_errors:
        result.update(state="FAILED", reason="CHECKER_FAILURE")
    elif total_skips:
        result["reason"] = "SKIPPED_CHECKS"
    else:
        result.update(state="PASSED", reason="EXPECTED_CHECKS_COMPLETED")
    return result
