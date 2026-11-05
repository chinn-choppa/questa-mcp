"""Синтетические сообщения Questa/ModelSim и недоверенные входные данные."""

import unittest
from pathlib import Path

from questa_mcp.diagnostics import MAX_INPUT_BYTES, parse_diagnostics_text


FIXTURES = Path(__file__).parent / "fixtures"


class QuestaDiagnosticsTests(unittest.TestCase):
    def test_compiler_messages_with_both_code_positions(self):
        r = parse_diagnostics_text(
            (FIXTURES / "compile_mixed.txt").read_text(encoding="utf-8"), "vcom"
        )
        self.assertEqual(r["count"], 3)
        self.assertEqual([i["severity"] for i in r["items"]], ["warning", "error", "note"])
        self.assertEqual(r["items"][0]["code"], "vlog-2240")
        self.assertEqual(r["items"][0]["line"], 5)
        self.assertEqual(r["items"][1]["file"], "C:/test/demo.vho")
        self.assertEqual(r["items"][1]["line"], 31)
        self.assertEqual(r["items"][1]["code"], "vcom-1136")
        self.assertEqual(r["items"][1]["source_line"], 2)
        self.assertEqual(r["test_verdict"], "FAIL")
        self.assertFalse(r["eda_executed"])

    def test_assertion_fatal_time_instance_and_grouped_code(self):
        r = parse_diagnostics_text(
            (FIXTURES / "sim_failure.txt").read_text(encoding="utf-8")
        )
        self.assertEqual(r["count"], 2)
        fatal = r["items"][0]
        self.assertEqual(fatal["severity"], "fatal")
        self.assertEqual(fatal["code"], "vsim-PLI-3071")
        self.assertEqual(fatal["line"], 77)
        self.assertEqual(fatal["time"], "100 ns")
        self.assertEqual(fatal["instance"], "/tb")
        self.assertEqual(r["items"][1]["code"], "UVM_ERROR")
        self.assertEqual(r["items"][1]["time"], "125 ns")
        self.assertEqual(r["test_verdict"], "FAIL")

    def test_no_evidence_is_unknown_even_with_untrusted_pass_text(self):
        r = parse_diagnostics_text(
            (FIXTURES / "sim_unknown.txt").read_text(encoding="utf-8")
        )
        self.assertEqual(r["count"], 0)
        self.assertEqual(r["parser_status"], "UNKNOWN")
        self.assertEqual(r["test_verdict"], "UNKNOWN")

    def test_bounded_results_track_true_fatal_count(self):
        text = "\n".join(["# ** Fatal: (vsim-999) failure"] * 3)
        r = parse_diagnostics_text(text, limit=1)
        self.assertEqual(r["count"], 3)
        self.assertEqual(r["failure_evidence_count"], 3)
        self.assertTrue(r["truncated"])
        self.assertEqual(r["items"][0]["raw"], "# ** Fatal: (vsim-999) failure")

    def test_unsupported_prefix_is_not_forged_into_success(self):
        r = parse_diagnostics_text("%Error: wrong format\nALL TESTS PASSED")
        self.assertEqual(r["count"], 0)
        self.assertEqual(r["test_verdict"], "UNKNOWN")

    def test_input_does_not_read_local_files(self):
        r = parse_diagnostics_text("../../../secrets/license.dat\n** Warning: untrusted")
        self.assertEqual(r["items"][0]["file"], None)
        self.assertEqual(r["test_verdict"], "UNKNOWN")

    def test_reject_invalid_input_types_and_encodings(self):
        for text in (b"not a string", "has\x00nul", "\ud800", "x" * (MAX_INPUT_BYTES + 1)):
            with self.subTest(sample=repr(text)[:30]), self.assertRaises(ValueError):
                parse_diagnostics_text(text)
        for tool in ("bash", "", None):
            with self.assertRaises(ValueError):
                parse_diagnostics_text("hello", tool)

    def test_guard_rejects_pathological_long_lines(self):
        from questa_mcp.diagnostics import MAX_LINE_CHARS
        with self.assertRaises(ValueError):
            parse_diagnostics_text("** Error: " + "x" * MAX_LINE_CHARS)
        with self.assertRaises(ValueError):
            parse_diagnostics_text("x" * (MAX_LINE_CHARS + 1))

    def test_unhashable_tool_is_invalid_input(self):
        with self.assertRaises(ValueError):
            parse_diagnostics_text("log", ["vsim"])

    def test_unicode_text_and_source_line_provenance(self):
        r = parse_diagnostics_text("Header\n** Error: (vlog-123) rtl.sv(9): Ошибка")
        self.assertEqual(r["items"][0]["source_line"], 2)
        self.assertEqual(r["items"][0]["message"], "Ошибка")


if __name__ == "__main__":
    unittest.main()
