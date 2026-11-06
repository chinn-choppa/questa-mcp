# Run-scoped waveform and coverage artifacts (#6)

[Русский](RUN_SCOPED_ARTIFACTS.md)

## Purpose and trust boundary

Unlike `list_approved_artifacts(project_id)`, which inspects **pre-existing workspace files with unverified run provenance**, this experimental collector creates a **new empty directory** for each approved `run_approved_project(project_id)` call.

An operator explicitly enables collection. The server provides `QUESTA_MCP_ARTIFACT_DIR` to the local simulator process so the pre-reviewed DO script can write approved VCD/FST/WLF/UCDB output names. After the process ends, the server inspects **metadata only**; no Wavepeek, wave-mcp, arbitrary MCP Tcl or vendor WLF converter runs automatically.

## Approved profile settings

Add these fields to the existing approved project profile:

```json
{
  "capture_run_artifacts": true,
  "executable_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "artifacts": [
    {
      "id": "wave",
      "path": "waves/tb.vcd",
      "format": "vcd",
      "declared_time_unit": "ns"
    }
  ],
  "expose_artifact_paths": false
}
```

The hash is a placeholder. **Both** a pinned, operator-verified simulator binary SHA-256 and at least one approved artifact specification are required for collection. Limits remain 8 artifact names, safe relative paths without traversal/symlinks, and hashing at most 8 MiB per file.

An existing approved DO script can construct the intended output filename:

```tcl
set artifact_file [file join $::env(QUESTA_MCP_ARTIFACT_DIR) waves tb.vcd]
file mkdir [file dirname $artifact_file]
# Use the waveform-export command documented for your Siemens edition.
```

This is a **human-reviewed local DO fragment**, never an MCP argument. Recompute the approved `do_sha256` after modifying the file. Edition-specific export syntax requires live vendor acceptance.

## Retention and external handoff

**By default**, each run uses a temporary output directory deleted after the tool call. Only the manifest and hashes remain; the path **cannot be passed to a later external analyzer**.

For optional durable handoff, the operator can set `run_artifact_store` to an **existing absolute directory outside `workspace`**. Each invocation creates a unique new subdirectory there. It is **not automatically cleaned**. The local file paths are returned only when `expose_artifact_paths=true` is also explicitly configured; trusted local agents can then pass them to Wavepeek or wave-mcp using those tools' own interfaces. The operator must enforce disk quotas, retention and cleanup independently: this MCP **does not enforce disk capacity**. Never expose confidential artifacts in a shared store.

## Evidence semantics

`run_approved_project` now includes `run_provenance.run_id` and `run_artifacts`: `run_id`, `retained`, `capture_mode`, `observed_count` and per-file `items`.

- An allowlisted file observed in a new directory after a settled process is tagged `origin=FRESH_RUN_DIRECTORY_OBSERVED` and `observed_under_run_id=<run_id>`.
- **`produced_by_run_id=null` and `production_verified=false` always.** Approved Tcl or another process with the same OS permissions could create a file; a fresh path does not cryptographically establish its producer.
- Missing files, timeout, output overflow, unconfirmed termination or a changed simulator hash do **not** gain a run association. Old workspace contents are never promoted to fresh evidence.
- `format_validated=false`, `external_execution=NOT_RUN`, independently unverified SVA and overall `test_verdict` retain their conservative meanings. Hashes and suffixes do not validate waveform content, assert completeness or vendor licensing.

Neither a private temporary directory nor an operator-approved persistent store is an OS sandbox. Use a restricted account or VM. On cancellation or failure, persistent stores may contain partial files; do not confuse those with passing verification.

## Test evidence

Public tests use mocked `vsim` processes and check stale-versus-fresh files, unique run identifiers, private paths by default, opt-in retention, rejection of invalid storage/hashes, timeout/binary mutation and **a real MCP `tools/call` with a mock subprocess**. Live licensed Siemens Questa, actual external Wavepeek/wave-mcp invocation and valid FST/WLF/UCDB analysis: **NOT_RUN**.
