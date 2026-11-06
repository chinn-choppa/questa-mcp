# Run-scoped output artifact observation (#6)

[Русский](RUN_ARTIFACTS.md)

The existing `list_approved_artifacts(project_id)` remains read-only and treats pre-existing workspace files as **unattested**. The new opt-in mode creates *a fresh separate output directory for each configured seed*, allowing a reviewed DO script to write waveform/coverage files without claiming vendor-certified provenance.

## Operator configuration

Extend a profile with `phase_scripts` and `regression_seeds`:

```json
{
  "run_artifacts_dir": "run-results",
  "run_artifacts": [
    {"id": "trace", "path": "wave.vcd", "format": "vcd", "declared_time_unit": "ns"},
    {"id": "coverage", "path": "coverage.ucdb", "format": "ucdb"}
  ],
  "expose_artifact_paths": false
}
```

The operator must create `run-results` beneath the approved `workspace` before use. It must not be a symlink or junction. The path is strictly relative, without `..`, backslashes, colons, NUL, or absolute paths. The artifact list must be non-empty, up to 8 operator-defined VCD/FST/WLF/UCDB files.

For every seed, `run_approved_regression` creates a new unpredictable `run-results/<run_id>` directory with restrictive OS permissions where supported. Its absolute path is passed via the **fixed** `QUESTA_MCP_ARTIFACT_DIR` environment variable to the three approved subprocesses. The reviewed DO script must explicitly consume that variable and write to the directory. The agent cannot select paths or arbitrary Tcl commands.

## MCP operations

`run_approved_regression` returns `runs[].run_id`, `runs[].artifact_manifest`, and `runs[].artifact_origin`. The independent read-only tool `list_run_artifacts(project_id, run_id)` reopens only those fixed allowed files in the specified run directory. `run_id` is exactly 24 lowercase hexadecimal characters, never a path.

Small ordinary files (up to 8 MiB) have `state=HASHED`, size, SHA-256, an operator-declared format and external route descriptors; larger files are not hashed. `format_validated=false`, `external_execution=NOT_RUN`, and `produced_by_run_id=null` remain unchanged. Additional fields:

- `observed_in_run_id`: identifies the **directory** in which the file was observed.
- `origin=OBSERVED_IN_RUN_DIRECTORY_NOT_VENDOR_ATTESTED`: a location observation, **not proof that Siemens generated the file**.

Files persist after execution. Only when an operator enables `expose_artifact_paths=true` can the MCP result disclose a local path for a trusted external analyzer. No Wavepeek/wave-mcp calls, automatic WLF conversion or network uploads occur.

## Security and retention

Run directories are **not automatically deleted**. The operator must manage permissions, disk quotas, cleanup, and retention. The 8 MiB hashing/read limit **does not cap file size written by the subprocess**. A different process with the same OS privileges can tamper with outputs; unpredictable run IDs prevent incidental reuse, not hostile modification or cryptographic forgery.

Invalid or inaccessible output-root configuration fails closed. Public tests use a mock simulator writing two seed directories, malformed/root-escape paths, optional path disclosure and a real MCP tools/call roundtrip. Licensed Questa, licensed Questa, `wave-mcp`, wlf2vcd, WLF/UCDB and vendor-authenticated provenance remain **NOT_RUN**. Real Wavepeek VCD/FST was independently verified on mock-EDA output in Linux CI.

## Typed handoff to an external waveform consumer

`prepare_run_handoff(project_id, run_id, artifact_id, consumer)` returns a *local pointer* without invoking an analyzer. Only `wavepeek` and `wave-mcp` are accepted consumer names. The operator must enable `expose_artifact_paths=true`; otherwise `OPT_IN_REQUIRED` returns no path. Only allowlisted VCD/FST files in `HASHED` or `HASH_SKIPPED_LARGE_FILE` state may return `status=READY_FOR_EXTERNAL_CLIENT`. Native WLF/UCDB yield `UNSUPPORTED_NATIVE_FORMAT`; absent files yield `ARTIFACT_UNAVAILABLE`. The pointer includes path, format, size, optional SHA-256, `format_validated=false`, `vendor_attested=false`, and `external_execution=NOT_RUN`. The trusted external MCP client must open the file itself. This operation **does not prove** Wavepeek/wave-mcp actually parsed it or that signals are valid.

## Real external Wavepeek acceptance (2026-11-06)

[GitHub Actions](https://github.com/chinn-choppa/questa-mcp/actions/runs/42196936606): the official SHA-256-verified Wavepeek v3.2.0 read `tb.clk` from approved VCD and FST paths returned by **real MCP calls** `run_approved_regression` → `prepare_run_handoff`. The three DO phases used **mock subprocesses**, not Siemens. A valid FST was created via open-source GTKWave `vcd2fst` in CI only. Both `WAVEPEEK_PUBLIC_VCD=PASS` and `WAVEPEEK_PUBLIC_FST=PASS` were observed. This validates the **local handoff**, not actual Questa, vendor authorship, or overall RTL PASS. `wave-mcp`, WLF/UCDB and licensed EDA remain **NOT_RUN**.

Security improvement: missing artifacts and unsettled phases do not receive `observed_in_run_id`. Inherited `QUESTA_MCP_SEED`, `COCOTB_RESULTS_FILE` and `QUESTA_MCP_ARTIFACT_DIR` are cleared before setting trusted values for the current run.
