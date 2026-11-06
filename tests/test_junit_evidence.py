"""Синтетические JUnit-файлы: полнота, отсутствие подмены и ложных PASS."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from questa_mcp.junit_evidence import analyze_junit_bytes, read_junit_artifact


def report(case: str = '<testcase name="check_add" classname="test_counter"/>',
           tests: int = 1, failures: int = 0, errors: int = 0,
           skipped: int = 0) -> bytes:
    return (
        f'<testsuites name="cocotb tests"><testsuite name="test_counter" '
        f'tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}">'
        f'{case}</testsuite></testsuites>'
    ).encode("utf-8")


class JUnitEvidenceTests(unittest.TestCase):
    def test_expected_single_test_is_passed_report(self):
        result = analyze_junit_bytes(report(), ("check_add",))
        self.assertEqual(result["state"], "PASSED")
        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(len(result["report_sha256"]), 64)

    def test_report_failure_and_error(self):
        for tag in ("failure", "error"):
            with self.subTest(tag=tag):
                r = analyze_junit_bytes(
                    report(f'<testcase name="check_add"><{tag} message="bad"/></testcase>',
                           failures=int(tag == "failure"), errors=int(tag == "error")),
                    ("check_add",))
                self.assertEqual(r["state"], "FAILED")
                self.assertEqual(r["reason"], "CHECKER_FAILURE")

    def test_skip_or_missing_test_is_not_pass(self):
        skip = report('<testcase name="check_add"><skipped/></testcase>', skipped=1)
        self.assertEqual(analyze_junit_bytes(skip, ("check_add",))["state"], "UNKNOWN")
        self.assertEqual(
            analyze_junit_bytes(report(), ("check_add", "check_sub"))["reason"],
            "EXPECTED_TESTS_MISMATCH",
        )

    def test_duplicate_test_and_tampered_counts_are_unknown(self):
        doubled = report(
            '<testcase name="check_add"/><testcase name="check_add"/>', tests=2
        )
        self.assertEqual(analyze_junit_bytes(doubled, ("check_add",))["state"], "UNKNOWN")
        self.assertEqual(
            analyze_junit_bytes(report(tests=5), ("check_add",))["reason"],
            "INCONSISTENT_COUNTS",
        )

    def test_no_expected_tests_no_success(self):
        self.assertEqual(
            analyze_junit_bytes(report(), ())["state"], "UNKNOWN"
        )
        self.assertEqual(
            analyze_junit_bytes(report(), ("a", "a"))["state"], "UNKNOWN"
        )

    def test_malformed_and_dangerous_xml_rejected(self):
        for data in (
            b"<testsuites", b"", b"<root/>",
            b'<!DOCTYPE t [<!ENTITY x "secret">]><testsuites/>',
            b"<testsuites>" + b"x" * 131_073,
            b"<testsuites>\x00</testsuites>",
        ):
            with self.subTest(data=data[:30]):
                self.assertEqual(analyze_junit_bytes(data, ("check_add",))["state"], "UNKNOWN")

    def test_file_is_fresh_read_only_regular_not_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "results.xml"
            self.assertEqual(read_junit_artifact(p)[1], "REPORT_MISSING")
            p.write_bytes(report())
            raw, state = read_junit_artifact(p)
            self.assertEqual(state, "READ_OK")
            self.assertEqual(raw, report())
            link = Path(temp) / "linked.xml"
            try:
                link.symlink_to(p)
            except (OSError, NotImplementedError):
                return
            raw, state = read_junit_artifact(link)
            self.assertIsNone(raw)
            self.assertEqual(state, "UNSAFE_SYMLINK")

    def test_report_rejects_wrong_name_and_unspecified_status(self):
        self.assertEqual(
            analyze_junit_bytes(report('<testcase name="bad name"/>'), ("bad name",))["state"],
            "UNKNOWN",
        )
        self.assertEqual(
            analyze_junit_bytes(
                report('<testcase name="check_add" status="failed"/>'),
                ("check_add",),
            )["state"],
            "UNKNOWN",
        )


if __name__ == "__main__":
    unittest.main()
