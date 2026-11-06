# Approved project and DO scenarios

[Русский](APPROVED_PROJECTS.md)

## Trust model

MCP callers **cannot** provide a shell command, Tcl snippet, arbitrary path or vsim flags. A human operator must prepare a local JSON manifest mapping fixed project identifiers to a trusted installed `vsim` and an existing approved DO script. `run_approved_project(project_id)` only selects an allowlisted ID.

**This is an API allowlist, not an OS sandbox.** An approved DO script is still executable Tcl with the user's filesystem and potentially network privileges. Run it only in a **disposable** workspace under a dedicated restricted OS account or in a dedicated isolated VM. The MCP server cannot prevent the Tcl script from accessing outside the working directory or sourcing other files. Never expose confidential RTL/licensing data to an unapproved AI client.

## Local configuration

Set `QUESTA_MCP_PROJECTS_CONFIG` to the **absolute** path of a locally operator-authored JSON file. Replace example paths with absolute paths for your platform.

```json
{
  "projects": {
    "public-smoke": {
      "workspace": "/absolute/disposable/workspace",
      "executable": "/absolute/questa/bin/vsim",
      "do_script": "run.do",
      "do_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "operator_approved": true,
      "disposable_workspace": true,
      "timeout_seconds": 120,
      "max_output_bytes": 65536,
      "expose_diagnostics": false
    }
  }
}
```

The hash shown is not valid for your actual script. Compute and enter the SHA-256 of the **reviewed** DO file. Its path must be relative to the disposable workspace, free of `..` and symlinks. Limits: DO 128 KiB, config 64 KiB, maximum 32 profiles. The executable filename must be `vsim` or `vsim.exe`. A changed DO script is rejected as `DO_HASH_MISMATCH`.

## Execution and results

- `list_approved_projects()` only lists approved IDs, never paths.
- `run_approved_project(project_id)` executes fixed `vsim -c -do <approved-file>` without a shell. Output is bounded in memory, and runtime is limited.
- Process start, timeout and output exhaustion produce explicit `TOOL_UNAVAILABLE`, `TIMEOUT` and `OUTPUT_LIMIT` statuses. Exit code 0 produces `COMPLETED_UNVERIFIED`, **never PASS**.
- `LICENSE_ERROR_EVIDENCE` is a recognized transcript clue, not proof of a licensed EDA run in public CI.
- Raw diagnostics disclosure is disabled by default. Setting `expose_diagnostics=true` reveals up to 20 messages that might contain proprietary paths or information.
- Compile, elaboration and simulation phase verdicts remain `UNKNOWN` until #5 supplies authoritative evidence.

Windows and Linux public CI use mock subprocesses. Real licensed Questa/ModelSim operation, vendor editions, and actual OS process-tree termination remain **NOT_RUN**.

## Execution-time script snapshot

The server reads a size-bounded DO file, checks the operator-approved SHA-256, and creates a private temporary snapshot outside the workspace. `vsim -do` receives the snapshot path, which is deleted after execution. This closes the gap between hashing and the simulator reopening the original DO, but **does not provide isolation** against an attacker with the same OS permissions, unsafe `source` commands or modifications of dependent files. On supported POSIX systems the final file read uses `O_NOFOLLOW`. If process-tree shutdown cannot be confirmed, the status is `TERMINATION_UNCONFIRMED`; descendants may survive, particularly on Windows. A real-Questa acceptance run in an OS sandbox remains mandatory.

## Optional cocotb JUnit profile

The local manifest can additionally specify `executable_sha256` and `checker: {"format":"cocotb-junit-v1","expected_tests":["check_counter"]}`. The hash is **required** when the checker is enabled. A fresh per-run `COCOTB_RESULTS_FILE` is read with 128 KiB and 256-test limits. A consistent self-checking result may set `checker_verdict=PASS`, but never asserts a full test/regression PASS. Changed executables return `EXECUTABLE_HASH_MISMATCH` before spawn or `EXECUTABLE_CHANGED` after spawn. Full details: [JUnit evidence](JUNIT_EVIDENCE.en.md).

## Cancellation lifecycle

Cancellation during or after process creation now waits for the protected child cleanup task **before deleting the temporary approved DO snapshot**, including repeated cancellations. This prevents early deletion of the script while cleanup is still running; **it does not prove that all grandchildren have exited** if OS-level process-tree termination fails. The configured execution timeout currently covers the running/reading phase **after process spawn**, not the initial OS spawn latency. A restricted VM/account is still required.
