# Contributing

[Русский](CONTRIBUTING.md)

Contributions from FPGA/ASIC verification engineers are welcome. Check existing issues and prior implementations before opening a PR. Report expected versus actual behavior, product and OS versions and reproducible public evidence.

## Build and checks

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
```

Real MCP contract tests connect through both in-memory and subprocess stdio transports. They are **not** evidence of licensed Questa execution. Public CI needs no Siemens installation or license.

A PR should be narrowly scoped, linked to its issue, and include positive, negative, boundary and security tests. Prefer Conventional Commits and explain compatibility and recovery. Update the Russian and English README, contracts, compatibility and architecture together when relevant.

Never include internal design sources, real corporate logs, commercial binaries, license files, authorization tokens or copied third-party code without license review. For security reports use the private process in [SECURITY.en.md](SECURITY.en.md).

Any change to approved DO execution requires process-boundary, path, timeout, output-limit and cancellation tests. Never propose an unrestricted shell/Tcl tool. See [configuration](docs/APPROVED_PROJECTS.en.md).

When changing the opt-in JUnit integration, keep `checker_verdict` separate from overall `test_verdict`. Exercise corrupted XML, wrong expected names, stale/symlinked artifacts, unexpected encodings, executable hash tampering, process failure and MCP calls on synthetic data. Update [JUnit contract](docs/JUNIT_EVIDENCE.en.md) and its Russian counterpart in the same PR.

For #6 use public synthetic waveform/coverage artifacts only. Keep metadata separate from proof of waveform validity or run provenance. Never add caller-provided arbitrary paths, automatic downloads, WLF converter execution or duplicate third-party decoders. Update [handoff docs](docs/ARTIFACT_HANDOFF.en.md) and the Russian counterpart together.
