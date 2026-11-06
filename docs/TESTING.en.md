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

Synthetic VCD and placeholder FST/WLF/UCDB files test **metadata and routing only**. Tests cover workspace boundaries, symlinks, invalid extensions/paths, missing artifacts, SHA-256 for small files, skip-hash for large files and hidden local paths. Real MCP `tools/list`/`tools/call` reaches the new tool. A separate [Wavepeek VCD/FST CI](https://github.com/chinn-choppa/questa-mcp/actions/runs/42195636610) confirmed actual Wavepeek queries on public VCD/FST; FST is produced by open-source `vcd2fst` in a Linux runner. WLF conversion, UCDB coverage, `wave-mcp` and licensed Questa: `NOT_RUN`.

## Run-scoped artifact isolation tests (#6)

A mocked vendor process receives a new directory through an environment variable, writes a synthetic VCD, and the MCP returns only metadata and `observed_under_run_id`. Negative tests cover pre-existing workspace artifacts, unique identifiers across runs, temporary cleanup, explicit retention and path disclosure, unsafe storage, mandatory binary SHA-256, timeout, binary changes, and a real MCP `tools/call` with a mock vsim. Licensed Siemens Questa is **NOT_RUN**. See [contract](RUN_SCOPED_ARTIFACTS.en.md).

