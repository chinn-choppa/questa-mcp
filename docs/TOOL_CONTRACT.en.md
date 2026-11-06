# MCP tool contract v0.1

[Русский](TOOL_CONTRACT.md)

The server uses local stdio and official MCP SDK 2.3.0. Diagnostic and phase-analysis tools are **read-only**. Separately, an explicitly operator-enabled allowlisted runner may invoke installed vsim with a verified DO snapshot; it cannot run arbitrary caller commands.

## `server_info()`

Returns `server`, `version`, `vendor_tool`, `stage`, `operations` and `eda_execution_supported` (true only for an approved local profile).

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

Questa/ModelSim `** Error (suppressible):` and `** Warning (suppressible):` are recognized; each diagnostic includes `qualifier="suppressible"` or `null`. Suppressible **errors remain failures**, not successful checks.

## Experimental fresh JUnit checker (#5)

When an operator-approved profile contains `executable_sha256` and `checker={"format":"cocotb-junit-v1","expected_tests":[...]}`, `run_approved_project` sets `COCOTB_RESULTS_FILE` to a new private file path for that run. The response contains `checker` (format, state, reason, counts, report SHA-256), `checker_verdict=PASS|FAIL|UNKNOWN`, `assertions_verdict=UNKNOWN`, `regression_verdict=UNKNOWN`, `run_provenance`, and `transcript_utf8_lossless`/`transcript_parser_complete`. The overall `test_verdict` remains **UNKNOWN even when checker_verdict=PASS** because external assertions and phase completeness are not independently established. Observed process/checker failures can return `test_verdict=FAIL`. The binary hash is verified before and after launch. MCP callers cannot supply checker paths, XML, arbitrary Tcl or executable commands. See [evidence rules](JUNIT_EVIDENCE.en.md). The SDK may ignore additional unknown JSON fields, but they are not interpreted as a command.

## Read-only artifacts (#6)

`list_approved_artifacts(project_id: str)` only selects the approved profile and its operator-defined list of up to 8 `artifacts`. No permission returns `DENIED`/`NOT_CONFIGURED`; invalid setup returns `INVALID_CONFIGURATION`. Each item contains `id`, `format`, `declared_time_unit`, `time_unit_source`, `size_bytes`, optional bounded `sha256`, `state`, `format_validated=false`, `origin=EXISTING_WORKSPACE_FILE_NOT_ATTESTED`, `produced_by_run_id=null`, `external_execution=NOT_RUN`, `paths_disclosed`, optional `local_path` and `routes`. No MCP-supplied file paths or contents. WLF needs independent vendor conversion; UCDB is vendor-native coverage. See [manifest contract](ARTIFACT_HANDOFF.en.md).

## Run-scoped artifacts (#6)

`run_approved_project(project_id)` adds `run_artifacts` with `state`, `run_id`, `count`, `observed_count`, `items`, `retained`, `capture_mode`; also `run_provenance.run_id`. With operator-enabled `capture_run_artifacts=true` and a pinned `executable_sha256`, each invocation gets an empty `QUESTA_MCP_ARTIFACT_DIR`, and only declared files are inspected. `observed_under_run_id` links an observation after a settled process; **`produced_by_run_id=null` and `production_verified=false` always**. Timeout, unconfirmed termination and modified binaries cannot establish a run association. `run_artifact_store` enables explicit operator-approved retention. See the [contract](RUN_SCOPED_ARTIFACTS.en.md).
