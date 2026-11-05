# MCP tool contract v0.1

[Русский](TOOL_CONTRACT.md)

The server uses local stdio, official MCP Python SDK 2.3.0 and **read-only** tools. No tool may execute commands or read project files.

## `server_info()`

Returns `server`, `version`, `vendor_tool`, `stage`, `operations` and `eda_execution_supported=false`.

## `tool_status()`

Checks the local vsim candidate from PATH or the administrator's `QUESTA_MCP_EXECUTABLE` environment variable. It **never invokes** it. Returns `tool`, `state` (`DETECTED_UNVERIFIED`, `NOT_FOUND`, `INVALID_OVERRIDE`), `configured` and `executed=false`. No executable path or license values are returned.

## `parse_diagnostics(text, tool="vsim", limit=200)`

`tool` is one of `vsim`, `vlog`, `vcom`. Text must be valid UTF-8 encodable Unicode without NUL and at most 1,048,576 bytes. `limit` is an integer 1–200 (not bool). Unsupported tool or invalid input is an MCP tool error.

Returns `tool`, `count` (all recognized messages), `items` (capped), `truncated`, `unrecognized_lines`, `parser_status` (`UNKNOWN`, `PARTIAL`, `RECOGNIZED`), `failure_evidence_count`, `eda_executed=false`, `test_verdict` (`FAIL` or `UNKNOWN`).

Items include `severity`, `code`, `emitter`, `file`, `line`, `column`, `time`, `instance`, `message`, `source_line` (1-based in supplied text), `raw` (exact original line except line terminator), `format` and `confidence=HIGH` for recognized prefixes. `confidence` refers **only** to recognition, never successful verification.

A recognized error/fatal/UVM_ERROR/UVM_FATAL establishes a failure indication, but absence of such evidence is **UNKNOWN**, not PASS. Synthetic `TEST PASSED` text cannot establish checker completion. File paths are treated strictly as text and are not opened.

## Planned execution API

A separate approved-project API must enforce allowlists, fixed executables, existing DO scripts and bounded workspace. Do not add `command`, unrestricted Tcl, arbitrary shell or network execution.

For regex resource safety, any single log line longer than **8192 characters** is rejected. Invalid types generate tool errors, not UNKNOWN/PASS.

## Approved runner contract (#4)

`list_approved_projects()` lists safe IDs or `NOT_CONFIGURED`/`INVALID_CONFIGURATION`. `run_approved_project(project_id: str)` returns `status`, `exit_code`, `eda_executed`, `test_verdict=FAIL|UNKNOWN`, per-phase `UNKNOWN`, diagnostic count, optional explicitly disclosed entries, captured byte count and SHA-256, and log completeness. No caller-supplied Tcl/DO/paths; see [profile config](APPROVED_PROJECTS.en.md). Never convert zero exit code into PASS.

The runner executes an isolated temporary snapshot of SHA-256 checked DO bytes rather than reopening the mutable original. `TERMINATION_UNCONFIRMED` means process-tree shutdown was not verified; do not retry without inspection. `DO_HASH_MISMATCH` and `INVALID_SCRIPT` never launch EDA and return `eda_executed=false`.
