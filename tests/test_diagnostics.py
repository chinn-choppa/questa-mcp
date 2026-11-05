"""Офлайн-проверки парсинга диагностик без коммерческих инструментов."""

import unittest
from questa_mcp.diagnostics import parse_diagnostics_text


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tool = "vsim"

    def test_realistic_log(self):
        text = '** Error: (vsim-3601) Iteration limit reached\n** Warning: (vlog-2240) Port connection mismatch'
        result = parse_diagnostics_text(text, self.tool)
        self.assertEqual(result["count"], 2)
        self.assertEqual([x["severity"] for x in result["items"]], ["error", "warning"])
        self.assertFalse(result["truncated"])

    def test_unknown_lines_do_not_become_success(self):
        r = parse_diagnostics_text("unknown format\nexit 1", self.tool)
        self.assertEqual(r["count"], 0)
        self.assertEqual(r["items"], [])
        self.assertNotIn("pass", r)

    def test_limit_returns_true_count(self):
        sample = '** Error: (vsim-3601) Iteration limit reached'
        r = parse_diagnostics_text("\n".join([sample] * 3), self.tool, limit=1)
        self.assertEqual(r["count"], 3)
        self.assertEqual(len(r["items"]), 1)
        self.assertTrue(r["truncated"])

    def test_reject_oversize_and_invalid_limit(self):
        with self.assertRaises(ValueError):
            parse_diagnostics_text("x" * 1_048_577, self.tool)
        for limit in (0, 201, -1, True, 1.4):
            with self.assertRaises(ValueError):
                parse_diagnostics_text("", self.tool, limit=limit)

    def test_unknown_tool_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_diagnostics_text("", "bash")


if __name__ == "__main__":
    unittest.main()
