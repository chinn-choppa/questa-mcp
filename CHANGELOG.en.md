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


### Approved phase runner and regressions (#5)
- Three SHA-256-allowlisted DO scripts, independent states, bounded seeds and new `run_approved_regression` MCP tool.
- Mock-process failure/ordering tests and real MCP contract tests, without inferred verification PASS.

### Run-scoped output metadata (#6)
- Fresh directory per seed, fixed environment and read-only `list_run_artifacts` MCP tool.
- Bounded SHA-256 metadata and explicit unattested vendor-provenance state.

- New read-only `prepare_run_handoff`: local pointers only to allowlisted VCD/FST after explicit path-disclosure consent; WLF/UCDB never misrepresented as supported.

### Verified external Wavepeek VCD/FST (#6)
- A separate Linux CI verified official SHA-256-pinned Wavepeek v3.2.0 reading public VCD/FST from typed MCP calls and detecting `tb.clk` transitions.
- Open-source GTKWave `vcd2fst` produced FST; EDA processes were mocked, licensed Siemens: `NOT_RUN`.
- Missing files/incomplete phases no longer gain run association; inherited execution environment is sanitized.
