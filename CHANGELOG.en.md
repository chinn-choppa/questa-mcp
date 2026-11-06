# Changelog

[Русский](CHANGELOG.md)

Changes follow Keep a Changelog. Semantic Versioning is planned once the public tool contract stabilizes.

## Unreleased

### Added
- Portable Python stdio MCP server and project-local uv setup.
- Read-only `server_info`, `tool_status` and bounded `parse_diagnostics` tools.
- Real MCP client-side in-process and subprocess stdio tests on Windows/Linux CI.
- Synthetic `vlog`, `vcom`, `vsim`, UVM and assertion failure fixtures.
- Explicit conservative FAIL/UNKNOWN diagnostics and source-line evidence.
- Paired English and Russian public documentation.

### Not yet implemented
- Execution of commercial EDA, approved DO scripts, regression control, coverage and waveform export.

### Experimental (#4)
- Operator allowlist of trusted vsim/DO profiles, SHA-256 validation and bounded mock-tested subprocess execution.
- No EDA product certification or proof of test PASS.

### Experimental cocotb self-checker (#5)
- Fresh bounded cocotb JUnit XML from an operator-approved local process, with pinned simulator and DO hashes
- Expected testcase and suite-count reconciliation, reject skipped/duplicate/missing/unsafe artifacts
- Separate `checker_verdict=PASS` from overall verification `test_verdict=UNKNOWN`; negative evidence is retained
- Synthetic mock subprocess and real MCP tools/call contract tests; no licensed Siemens validation

- Protected child cleanup waits through repeated MCP cancellations and cancellation during subprocess spawn before removing the DO snapshot (mock tested).

### Experimental artifact handoff (#6)
- Read-only `list_approved_artifacts` MCP tool: operator-allowlisted VCD/FST/WLF/UCDB metadata, declared time units and bounded SHA-256.
- Explicit external consumer routes and native WLF/UCDB limitations, without analyzer execution, automatic conversion or uploads.
- Synthetic security and real MCP contract tests on Windows/Linux.


### Experimental run-scoped artifacts (#6)

- Fresh `QUESTA_MCP_ARTIFACT_DIR` and unique `run_id` for each approved execution.
- Distinct `observed_under_run_id` observations without falsely setting `produced_by_run_id`.
- Temporary output by default, optional operator-controlled persistent storage.
- Stale-artifact, incomplete-process, executable-tampering, MCP and unit regression tests.


### Wavepeek integration smoke (#6)
- Linux CI checksum-verifies Wavepeek v3.2.0 and reads public VCD plus `vcd2fst`-generated FST.
- Paths originate from opt-in retained mock-run manifests; licensed Siemens EDA remains `NOT_RUN`.
