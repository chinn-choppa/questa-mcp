# questa-mcp

[Русский](README.md) · [Contributing](CONTRIBUTING.en.md) · [Security](SECURITY.en.md)

An independent, local-first MCP adapter for Siemens Questa/ModelSim. Not affiliated with Siemens.

**Status: experimental diagnostic foundation (0.0.1).** Real MCP protocol tests and bounded Questa/ModelSim transcript parsing are implemented. **No EDA process runs by default**; an explicitly approved disposable-workspace DO runner is experimental. A returned zero error count is not a passing test.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Tested in public CI with Python 3.11 and 3.13 on Ubuntu and Windows, with official MCP SDK 2.3.0. Python 3.15 and vendor-specific tool compatibility remain **NOT_RUN**.

```bash
git clone https://github.com/chinn-choppa/questa-mcp.git
cd questa-mcp
uv sync
uv run questa-mcp
```

For clients using an `mcpServers` entry (other hosts have different configuration formats):

```json
{
  "mcpServers": {
    "questa-mcp": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/questa-mcp", "run", "questa-mcp"]
    }
  }
}
```

The server communicates over local `stdio` and does not start a network listener.

## Available tools

| Tool | Result | Execution |
| --- | --- | --- |
| `server_info()` | Capabilities and version | No EDA by default |
| `tool_status()` | Detect `vsim` without disclosing a path | No EDA |
| `parse_diagnostics(text, tool="vsim", limit=200)` | Structured `vsim`, `vlog`, `vcom`, UVM messages and evidence | No EDA |

Parsing accepts up to 1 MiB of text and returns at most 200 records. Entries include severity, message code, emitting tool, source file and line where present, simulation time, original transcript line and its position. `test_verdict` is **FAIL** when recognized error/fatal evidence exists, otherwise **UNKNOWN**. Neither compilation nor actual simulation is performed by the parser. It never reports PASS.

## Verification

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
```

CI includes real in-process and subprocess `stdio` MCP `tools/list` and `tools/call`, invalid request tests, and synthetic transcripts. Commercial EDA verification is separate and **NOT_RUN**.

See [architecture](docs/ARCHITECTURE.en.md), [tool contract](docs/TOOL_CONTRACT.en.md), [testing](docs/TESTING.en.md), [compatibility](docs/COMPATIBILITY.en.md), and [roadmap](docs/ROADMAP.en.md).

Licensed under Apache-2.0; Siemens binaries, licenses and proprietary examples are not distributed.

## Experimental approved runner (#4)

A human operator can opt in to a SHA-256 checked private DO snapshot and the **allowlisted** `list_approved_projects` and `run_approved_project(project_id)` tools. Only pre-approved, SHA-256 checked existing DO files are allowed; no MCP-supplied Tcl or paths. Details and trust limitations: [approved-project runner](docs/APPROVED_PROJECTS.en.md). All real licensed EDA results remain **NOT_RUN**. A zero exit code is reported as `COMPLETED_UNVERIFIED`, never PASS.

## Conservative verification phases (#5)

The read-only MCP tools `assess_verification_run(record)` and `assess_regression(runs)` track compile, elaboration, simulation, checker and regression independently. Caller-supplied positive claims are **UNVERIFIED**, never PASS. See [verification contract](docs/VERIFICATION.en.md). Live Siemens EDA **NOT_RUN**.

## Experimental cocotb JUnit checker (#5)

Approved local DO profiles may enable `checker.format="cocotb-junit-v1"`, an exact list of `expected_tests`, and a pinned `executable_sha256`. Each run receives a fresh `COCOTB_RESULTS_FILE` location. When the local process exits 0 and a complete XML report matches all expected tests, the response exposes `checker_verdict=PASS` **only for cocotb self-checks**. Overall `test_verdict`, independent assertions and regression remain `UNKNOWN` unless negative evidence establishes `FAIL`. No live licensed Siemens test was run. See [JUnit integration](docs/JUNIT_EVIDENCE.en.md).
