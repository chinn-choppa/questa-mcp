"""Синтетические диагностические сообщения Questa; строгие негативные кейсы."""
from pathlib import Path

import pytest

from questa_mcp.diagnostics import MAX_INPUT_BYTES, MAX_LINE_CHARS, parse_diagnostics_text


FIXTURES = Path(__file__).parent / "fixtures"


def test_compiler_messages_with_both_code_positions():
    result = parse_diagnostics_text((FIXTURES / "compile_mixed.txt").read_text("utf-8"), "vcom")
    assert result["count"] == 3
    assert [item["severity"] for item in result["items"]] == ["warning", "error", "note"]
    assert result["items"][0]["code"] == "vlog-2240"
    assert result["items"][0]["line"] == 5
    assert result["items"][1]["file"] == "C:/test/demo.vho"
    assert result["items"][1]["line"] == 31
    assert result["items"][1]["code"] == "vcom-1136"
    assert result["items"][1]["source_line"] == 2
    assert result["test_verdict"] == "FAIL"
    assert result["eda_executed"] is False


def test_assertion_fatal_time_instance_and_grouped_code():
    result = parse_diagnostics_text((FIXTURES / "sim_failure.txt").read_text("utf-8"))
    assert result["count"] == 2
    fatal = result["items"][0]
    assert fatal["severity"] == "fatal"
    assert fatal["code"] == "vsim-PLI-3071"
    assert fatal["line"] == 77
    assert fatal["time"] == "100 ns"
    assert fatal["instance"] == "/tb"
    assert result["items"][1]["code"] == "UVM_ERROR"
    assert result["items"][1]["time"] == "125 ns"
    assert result["test_verdict"] == "FAIL"


def test_no_evidence_is_unknown_even_with_untrusted_pass_text():
    result = parse_diagnostics_text((FIXTURES / "sim_unknown.txt").read_text("utf-8"))
    assert result["count"] == 0
    assert result["parser_status"] == "UNKNOWN"
    assert result["test_verdict"] == "UNKNOWN"


def test_bounded_results_track_true_fatal_count():
    text = "\n".join(["# ** Fatal: (vsim-999) failure"] * 3)
    result = parse_diagnostics_text(text, limit=1)
    assert result["count"] == 3
    assert result["failure_evidence_count"] == 3
    assert result["truncated"] is True
    assert result["items"][0]["raw"] == "# ** Fatal: (vsim-999) failure"


def test_unsupported_prefix_is_not_forged_into_success():
    result = parse_diagnostics_text("%Error: wrong format\nALL TESTS PASSED")
    assert result["count"] == 0
    assert result["test_verdict"] == "UNKNOWN"


def test_input_does_not_read_local_files():
    result = parse_diagnostics_text("../../../secrets/license.dat\n** Warning: untrusted")
    assert result["items"][0]["file"] is None
    assert result["test_verdict"] == "UNKNOWN"


@pytest.mark.parametrize("text", [
    b"not a string", "has\x00nul", "\ud800", "x" * (MAX_INPUT_BYTES + 1),
])
def test_reject_invalid_input_types_and_encodings(text):
    with pytest.raises(ValueError):
        parse_diagnostics_text(text)


@pytest.mark.parametrize("tool", ["bash", "", None, ["vsim"]])
def test_invalid_tool_rejected(tool):
    with pytest.raises(ValueError):
        parse_diagnostics_text("hello", tool)


@pytest.mark.parametrize("text", [
    "** Error: " + "x" * MAX_LINE_CHARS,
    "x" * (MAX_LINE_CHARS + 1),
])
def test_pathological_long_line_rejected(text):
    with pytest.raises(ValueError):
        parse_diagnostics_text(text)


def test_suppressible_vendor_diagnostic():
    sample = ("# ** Error (suppressible): (vsim-FLI-3155) The FLI is not enabled\n"
              "** Warning (suppressible): (vlog-2240) port mismatch")
    parsed = parse_diagnostics_text(sample, "vsim")
    assert parsed["count"] == 2
    assert [item["severity"] for item in parsed["items"]] == ["error", "warning"]
    assert parsed["items"][0]["code"] == "vsim-FLI-3155"
    assert parsed["items"][0]["qualifier"] == "suppressible"
    assert parsed["test_verdict"] == "FAIL"
    assert "(suppressible)" in parsed["items"][0]["raw"]


def test_unicode_text_and_source_line_provenance():
    result = parse_diagnostics_text("Header\n** Error: (vlog-123) rtl.sv(9): Ошибка")
    assert result["items"][0]["source_line"] == 2
    assert result["items"][0]["message"] == "Ошибка"
