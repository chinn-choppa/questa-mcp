"""Офлайн-контракты разбора диагностик Questa, без EDA."""
import pytest

from questa_mcp.diagnostics import parse_diagnostics_text


def test_realistic_log():
    text = ("** Error: (vsim-3601) Iteration limit reached\n"
            "** Warning: (vlog-2240) Port connection mismatch")
    result = parse_diagnostics_text(text, "vsim")
    assert result["count"] == 2
    assert [item["severity"] for item in result["items"]] == ["error", "warning"]
    assert result["truncated"] is False


def test_unknown_lines_do_not_become_success():
    result = parse_diagnostics_text("unknown format\nexit 1", "vsim")
    assert result["count"] == 0
    assert result["items"] == []
    assert "pass" not in result


def test_limit_returns_true_count():
    sample = "** Error: (vsim-3601) Iteration limit reached"
    result = parse_diagnostics_text("\n".join([sample] * 3), "vsim", limit=1)
    assert result["count"] == 3
    assert len(result["items"]) == 1
    assert result["truncated"] is True


@pytest.mark.parametrize("limit", [0, 201, -1, True, 1.4])
def test_invalid_limit_rejected(limit):
    with pytest.raises(ValueError):
        parse_diagnostics_text("", "vsim", limit=limit)


def test_oversized_text_rejected():
    with pytest.raises(ValueError):
        parse_diagnostics_text("x" * 1_048_577, "vsim")



def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError):
        parse_diagnostics_text("", "bash")
