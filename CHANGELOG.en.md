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
