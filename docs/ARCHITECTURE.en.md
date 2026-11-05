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
              |
   no licensed EDA invocation yet
```

The server is independent of agent-dev-toolkit and other EDA MCP adapters. It uses the official MCP Python SDK 2.3.0. The service never opens an HTTP listener or contacts the network by itself.

## Evidence boundary

`tools/list` confirms protocol advertisement; `tools/call` confirms invocation of the selected read-only tool. Neither proves Questa is installed, licensed, executing, or that a test passed. A parser can confirm known fatal/error evidence (`FAIL`) but never infer PASS from a benign transcript or exit code.

## Planned authorized runner (#4)

A future administrator-provided, local configuration will map opaque project IDs to fixed roots, a trusted vendor executable, immutable approved DO-script paths, allowed output paths and execution limits. MCP inputs may select from this allowlist, but must not supply shell arguments or Tcl/DO text. Canonical paths and symlinks require verification; output workspaces and subprocess trees need resource and timeout enforcement.

Trusted DO scripts themselves remain code execution and must be intentionally reviewed. Compiler, elaborator, simulator and checker verdicts must be independent (#5). Waveforms and native WLF conversion are a separate opt-in stage (#6).
