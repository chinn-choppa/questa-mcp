# Roadmap

[Русский](ROADMAP.md)

## Completed foundations

- [x] Public local stdio MCP server, read-only discovery and bounded diagnostic parsing.
- [x] Real in-process and subprocess `tools/list`/`tools/call` CI tests on Windows/Linux, Python 3.11/3.13.
- [x] Synthetic compilation, simulation failure, UVM and no-evidence cases.
- [x] English and Russian main public documents.

## Next steps

- [ ] #3: validate parser against more public tool/version transcripts and assertion variants; add documented confidence limitations.
- [ ] #4: opt-in allowlisted project runner, bounded subprocess and mock-process tests.
- [ ] #5: distinct compilation, elaboration, simulation, checker and regression verdicts; seeds and artifact provenance.
- [ ] #6: opt-in coverage/waveform manifests and external Wavepeek/wave-mcp handoff; no assumed native WLF support.
- [ ] Real licensed Questa/ModelSim and Python 3.15 acceptance: **NOT_RUN** until evidenced.

No stage should equate process exit 0 with self-checking test success.

- [x] #4 initial explicit allowlist and mock-verified, bounded DO runner (not an OS sandbox).
- [ ] #4 real licensed simulator and OS process-tree acceptance: NOT_RUN.

## Conservative verification phases (#5)

The read-only MCP tools `assess_verification_run(record)` and `assess_regression(runs)` track compile, elaboration, simulation, checker and regression independently. Caller-supplied positive claims are **UNVERIFIED**, never PASS. See [verification contract](VERIFICATION.en.md). Live Siemens EDA **NOT_RUN**.

- [x] #5: add fresh cocotb JUnit checker and pinned local binary hash in an opt-in approved DO profile, covered by mock MCP calls
- [ ] #5: actual Siemens/version-specific run, trusted compilation/elaboration and native SVA evidence, full regression PASS — NOT_RUN / NOT_IMPLEMENTED

## Initial #6 milestone

- [x] Read-only operator-allowlisted VCD/FST/WLF/UCDB manifests with bounded SHA-256 and private paths by default.
- [x] Separate Wavepeek/wave-mcp routes, manual WLF conversion and native UCDB coverage descriptions.
- [ ] Actual external Wavepeek/wave-mcp handoff with public VCD/FST and vendor-edition acceptance: `NOT_RUN`.
- [ ] Associate artifacts with a unique observed execution: `NOT_IMPLEMENTED`; existing workspace files remain unattested.

