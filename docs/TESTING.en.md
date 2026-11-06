# Testing

[Русский](TESTING.md)

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
```

CI on `ubuntu-latest` and `windows-latest`, Python 3.11 and 3.13, installs dependencies into a project-local uv environment. Tests include real in-process MCP `tools/list`, `tools/call`, subprocess stdio roundtrip, bad JSON-schema arguments, domain parsing and synthetic vendor transcript examples.

The first verified branch run: [GitHub Actions 42054703978](https://github.com/chinn-choppa/questa-mcp/actions/runs/42054703978), four jobs succeeded (2026-11-05). This validates the MCP protocol and pure parser only. The pinned SDK is `mcp==2.3.0`.

## Acceptance matrix

| Level | Status |
| --- | --- |
| Python compile/unit and MCP contract, Ubuntu/Windows Python 3.11/3.13 | PASS in public CI |
| Licensed Questa/ModelSim compilation | NOT_RUN |
| Actual elaboration or simulation | NOT_RUN |
| Self-checking RTL testbench and assertions | NOT_RUN |
| Python 3.15 | NOT_RUN |
| WLF/coverage or waveform handoff | NOT_RUN |

When implementing #4, add mock-process, cancellation, timeout, symlink traversal, license-unavailable and permissions tests before running real EDA. Do not publish commercial logs or internal RTL.

## Mock executor tests (#4)

Public CI additionally verifies denied/unconfigured profiles, changed DO hashes, traversal/symlink rejection, `shell=False` semantics, a fake process, timeout, output limit, error and license-text evidence. These are synthetic mock-process tests, **not licensed Questa runs**.

## Conservative verification phases (#5)

The read-only MCP tools `assess_verification_run(record)` and `assess_regression(runs)` track compile, elaboration, simulation, checker and regression independently. Caller-supplied positive claims are **UNVERIFIED**, never PASS. See [verification contract](VERIFICATION.en.md). Live Siemens EDA **NOT_RUN**.

## Fresh JUnit mock integration (#5)

The added tests exercise size-bounded XML parsing (including DTD rejection, inconsistent totals, duplicate/omitted names and skipped cases), fresh per-invocation report paths, pinned executable hash before/after, malformed UTF-8, unrecognized long transcript lines, errors and lost reports. A **real** MCP in-process `tools/list`/`tools/call` test uses a mocked vendor process. Positive mock evidence produces `checker_verdict=PASS` but `test_verdict=UNKNOWN`. No commercial Siemens license or real Questa is used in CI. See [JUnit test contract](JUNIT_EVIDENCE.en.md).

The #4 security regression suite additionally checks cancellation **during process spawn** and repeated cancellation while child cleanup is pending. The temporary DO snapshot must remain available until cleanup is complete. These are mock-process tests; real Windows/Linux vendor descendant shutdown remains NOT_RUN.

## VCD/FST/WLF/UCDB manifests (#6)

Synthetic VCD and placeholder FST/WLF/UCDB files test **metadata and routing only**. Tests cover workspace boundaries, symlinks, invalid extensions/paths, missing artifacts, SHA-256 for small files, skip-hash for large files and hidden local paths. Real MCP `tools/list`/`tools/call` reaches the new tool. Opening a real FST in Wavepeek, WLF conversion, UCDB coverage analysis and licensed Questa: `NOT_RUN`.

## Approved phase regressions (#5)

Unit/mock and real in-process MCP tests check the ordered three phases, seeds, compile/elaboration failure short-circuit, no false PASS, invalid/duplicate seeds, executable hash mismatch and missing profiles. All EDA subprocesses are synthetic mocks. Actual licensed Questa remains `NOT_RUN`. See [phase-runner tests](PHASE_RUNNER.en.md).

## Run-specific directory tests

Synthetic processes test distinct seeds/run IDs, `QUESTA_MCP_ARTIFACT_DIR`, hashes, path disclosure, invalid roots and symlinks, plus real MCP tools/call for execution and artifact reinspection. Commercial EDA is not required.

Typed handoff has unit and real MCP `tools/call` checks: missing path-consent, VCD pointer, refusal of WLF and unknown consumers, and no fabricated `external_execution`. Real Wavepeek/wave-mcp remains for final acceptance only.
