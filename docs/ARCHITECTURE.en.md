# Architecture

[Русский](ARCHITECTURE.md)

```text
MCP host (Codex / Claude / OpenCode / others)
              |
         local stdio
              |
      questa_mcp.server
        /           \
    runtime       diagnostics
 (discovery)     (bounded text)
                 approved runner
                  (opt-in)
                     |
             local Siemens vsim
```

The server is independent of agent-dev-toolkit and other EDA MCP adapters. It uses the official MCP Python SDK 2.3.0. The service never opens an HTTP listener or contacts the network by itself.

## Evidence boundary

`tools/list` confirms protocol advertisement; `tools/call` confirms invocation of the selected read-only tool. Neither proves Questa is installed, licensed, executing, or that a test passed. A parser can confirm known fatal/error evidence (`FAIL`) but never infer PASS from a benign transcript or exit code.

## Experimental authorized runner (#4)

The implemented experimental administrator-provided local configuration maps opaque project IDs to fixed roots, a trusted vendor executable, immutable approved DO-script paths, allowed output paths and execution limits. MCP inputs may select from this allowlist, but must not supply shell arguments or Tcl/DO text. Canonical paths and symlinks require verification; output workspaces and subprocess trees need resource and timeout enforcement.

Trusted DO scripts themselves remain code execution and must be intentionally reviewed. Compiler, elaborator, simulator and checker verdicts must be independent (#5). Waveforms and native WLF conversion are a separate opt-in stage (#6).

Different editions/versions may use the newer QIS/Qrun path or the legacy vlog/vopt/vsim compatibility flow. The planned runner must require an explicitly validated profile; no implicit flow switching.

The implementation now contains an **experimental** opt-in approved-profile executor; see [Approved projects](APPROVED_PROJECTS.en.md). It does not provide an OS sandbox or a verified vendor-specific flow.

## Optional cocotb JUnit evidence flow (#5)

`approved.run_approved_project` → pinned local `vsim` binary → SHA-256-checked private DO snapshot → unique temporary `COCOTB_RESULTS_FILE` → bounded `junit_evidence` parser. The runner returns a positive **checker-only** verdict when exact expected cases are complete. Overall test, independent SVA, compilation/elaboration and regression remain `UNKNOWN`. Existing `verification.assess_run` / `assess_regression` accept untrusted client data and cannot generate PASS. No generic simulator is added. See [JUnit collection](JUNIT_EVIDENCE.en.md).
