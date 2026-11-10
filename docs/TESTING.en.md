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
