"""Пофазные результаты: PASS только от внутреннего аттестованного коллектора."""

from __future__ import annotations

import copy
import unittest

from questa_mcp.verification import assess_regression, assess_run


class PhaseModelTests(unittest.TestCase):
    def setUp(self):
        self.passing = {
            "test_id": "tb_counter", "seed": 42, "tool": "questa", "tool_version": "mock-2026",
            "os": "synthetic-linux",
            "artifacts": {"testbench": "a" * 64, "do": "b" * 64},
            "phases": {
                "compile": {"started": True, "completed": True, "exit_code": 0, "log": "0 errors"},
                "elaboration": {"started": True, "completed": True, "exit_code": 0, "log": "# Loading work.tb"},
                "simulation": {"started": True, "completed": True, "exit_code": 0, "log": "# Simulation completed"},
            },
            "checker": {
                "executed": True, "completed": True, "checks_run": 4, "failures": 0,
                "success_evidence": {"source_line": 3, "raw": "TB_VERDICT: PASS checks=4"},
            },
        }

    def test_no_remote_report_can_claim_pass_even_with_marker(self):
        got = assess_run(self.passing)
        self.assertEqual(got["test_verdict"], "UNKNOWN")
        self.assertEqual(got["reason"], "UNVERIFIED_POSITIVE_EVIDENCE")
        self.assertEqual(got["checker"]["state"], "REPORTED_COMPLETE")
        self.assertEqual(got["provenance"], "CALLER_SUPPLIED_UNVERIFIED")
        self.assertEqual(got["phases"]["simulation"]["state"], "COMPLETED")

    def test_internal_mock_attestation_models_true_pass(self):
        got = assess_run(self.passing, attested=True)
        self.assertEqual(got["test_verdict"], "PASS")
        self.assertEqual(got["reason"], "ATTESTED_CHECKER_COMPLETED")

    def test_positive_evidence_without_provenance_remains_unknown(self):
        report = copy.deepcopy(self.passing)
        report["tool_version"] = ""
        report["artifacts"] = {}
        got = assess_run(report, attested=True)
        self.assertEqual(got["test_verdict"], "UNKNOWN")
        self.assertEqual(got["reason"], "INSUFFICIENT_PROVENANCE")

    def test_exit_zero_without_checker_is_unknown(self):
        report = copy.deepcopy(self.passing)
        report.pop("checker")
        got = assess_run(report, attested=True)
        self.assertEqual(got["test_verdict"], "UNKNOWN")
        self.assertFalse(got["reported_checker_pass"])

    def test_checker_without_checks_is_not_a_pass(self):
        report = copy.deepcopy(self.passing)
        report["checker"]["checks_run"] = 0
        report["checker"].pop("success_evidence")
        self.assertEqual(assess_run(report, attested=True)["test_verdict"], "UNKNOWN")

    def test_compile_error_has_exact_failing_line(self):
        report = copy.deepcopy(self.passing)
        report["phases"]["compile"]["log"] = (
            "header\n** Error: (vlog-1234) counter.sv(4): Invalid signal\n"
        )
        got = assess_run(report)
        self.assertEqual(got["test_verdict"], "FAIL")
        self.assertEqual(got["failure_source"], "compile")
        self.assertEqual(got["phases"]["compile"]["failure_evidence"][0]["source_line"], 2)
        self.assertIn("vlog-1234", got["phases"]["compile"]["failure_evidence"][0]["raw"])

    def test_elaboration_failed_by_exit_code(self):
        report = copy.deepcopy(self.passing)
        report["phases"]["elaboration"]["exit_code"] = 1
        got = assess_run(report)
        self.assertEqual(got["test_verdict"], "FAIL")
        self.assertEqual(got["failure_source"], "elaboration")
        self.assertEqual(got["phases"]["elaboration"]["exit_code"], 1)

    def test_checker_failure_needs_failure_evidence(self):
        report = copy.deepcopy(self.passing)
        report["checker"].update({
            "failures": 1, "failure_evidence": {"source_line": 7, "raw": "ASSERTION FAILED"}
        })
        self.assertEqual(assess_run(report)["test_verdict"], "FAIL")
        self.assertEqual(assess_run(report)["failure_source"], "checker")
        report["checker"].pop("failure_evidence")
        self.assertEqual(assess_run(report, attested=True)["test_verdict"], "UNKNOWN")

    def test_timeout_cancellation_are_unknown_not_pass(self):
        for state in ("timed_out", "cancelled"):
            report = copy.deepcopy(self.passing)
            report["phases"]["simulation"].update({"completed": False, "exit_code": None, state: True})
            result = assess_run(report, attested=True)
            self.assertEqual(result["test_verdict"], "UNKNOWN")
            self.assertEqual(result["phases"]["simulation"]["state"],
                             "TIMEOUT" if state == "timed_out" else "CANCELLED")

    def test_no_execution_is_not_run(self):
        report = copy.deepcopy(self.passing)
        report["phases"] = {}
        report.pop("checker")
        result = assess_run(report)
        self.assertEqual(result["test_verdict"], "NOT_RUN")
        self.assertEqual(result["phases"]["compile"]["state"], "NOT_RUN")

    def test_regression_aggregates_fail_unknown_and_attested_pass(self):
        good = copy.deepcopy(self.passing)
        bad = copy.deepcopy(self.passing)
        bad["seed"] = 43
        bad["phases"]["simulation"]["log"] = "** Fatal: (vsim-3825) assertion failed"
        got = assess_regression([good, bad])
        self.assertEqual(got["regression_verdict"], "FAIL")
        self.assertEqual(got["counts"]["FAIL"], 1)
        self.assertEqual(got["counts"]["UNKNOWN"], 1)
        got = assess_regression([good])
        self.assertEqual(got["regression_verdict"], "UNKNOWN")
        got = assess_regression([good], attested=True)
        self.assertEqual(got["regression_verdict"], "PASS")
        self.assertEqual(assess_regression([])["regression_verdict"], "NOT_RUN")

    def test_duplicate_test_seed_and_invalid_artifact_denied(self):
        with self.assertRaises(ValueError):
            assess_regression([self.passing, self.passing])
        invalid = copy.deepcopy(self.passing)
        invalid["artifacts"]["do"] = "not-a-hash"
        with self.assertRaises(ValueError):
            assess_run(invalid)

    def test_bad_phase_values_and_checker_counts_denied(self):
        for changes in ({"started": False, "completed": True}, {"exit_code": True},
                        {"timed_out": True, "cancelled": True}):
            report = copy.deepcopy(self.passing)
            report["phases"]["simulation"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                assess_run(report)
        report = copy.deepcopy(self.passing)
        report["checker"]["failures"] = 5
        with self.assertRaises(ValueError):
            assess_run(report)

    def test_missing_checker_proof_does_not_create_pass(self):
        report = copy.deepcopy(self.passing)
        report["checker"].pop("success_evidence")
        self.assertEqual(assess_run(report, attested=True)["test_verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
