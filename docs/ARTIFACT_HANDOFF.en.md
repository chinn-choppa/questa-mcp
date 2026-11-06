# Waveform and coverage handoff to external analyzers (#6)

[Русский](ARTIFACT_HANDOFF.md)

This is a **read-only artifact manifest**, not a waveform decoder or external-command runner. The MCP tool `list_approved_artifacts(project_id)` inspects only the files explicitly listed by a human operator in a local approved project profile. No caller-supplied paths, shell, or analyzer commands are accepted.

## Approved profile example

Add the following fields to an existing profile with mandatory `workspace`, `executable`, `do_script`, `do_sha256` and operator approval:

```json
{
  "artifacts": [
    {"id": "tb_vcd", "path": "waves/tb.vcd", "format": "vcd",
     "declared_time_unit": "ns"},
    {"id": "tb_fst", "path": "waves/tb.fst", "format": "fst"},
    {"id": "tb_wlf", "path": "waves/tb.wlf", "format": "wlf"},
    {"id": "coverage", "path": "reports/coverage.ucdb", "format": "ucdb"}
  ],
  "expose_artifact_paths": false
}
```

Up to 8 entries. IDs are bounded safe names; relative paths use `/` separators, without `..`, `\`, `:`, or symlinks. Optional `declared_time_unit` is one of `fs/ps/ns/us/ms/s`, **operator-supplied and not parsed or validated** against the waveform. An existing file does not prove it came from the latest approved run: all entries carry `origin=EXISTING_WORKSPACE_FILE_NOT_ATTESTED` and `produced_by_run_id=null`.

By default the MCP response **does not disclose absolute paths**. Only a human operator can enable `expose_artifact_paths=true` in the local profile to facilitate a trusted local agent passing the path to an external analyzer. Do not enable it for unapproved remote/cloud clients handling confidential designs. No file contents are returned.

## Status and consumer routes

- Regular files up to 8 MiB are bounded and SHA-256 hashed; larger files report size only as `HASH_SKIPPED_LARGE_FILE`. That status does not indicate decoding success or provenance.
- Missing files, symlinks, inaccessible objects and files changed during inspection yield separate states. Workspace traversal is denied within portable Python constraints; this is **not an OS sandbox** against another process with equivalent permissions.
- `format_validated=false` and `external_execution=NOT_RUN` always: a file suffix/hash is not a validated waveform and does not prove an external tool ran.
- VCD/FST: possible routes to [Wavepeek](https://github.com/kleverhq/wavepeek) and optional [Tencent wave-mcp](https://github.com/Tencent/wave-mcp), **not invoked by this server**.
- WLF: `NOT_SUPPORTED_DIRECTLY` by Wavepeek/wave-mcp. Some older ModelSim installations expose a vendor `wlf2vcd` command for manual conversion after closing the simulation; this adapter **does not invoke it** or assume its availability in a particular Siemens edition.
- UCDB: proprietary coverage database; metadata indicates `VENDOR_UCDB_EXTERNAL_ONLY`. No coverage analysis is implemented.

## Acceptance evidence

Public CI uses a small synthetic VCD and placeholder FST/WLF/UCDB files. It verifies **only the manifest**: path restrictions, size/hash bounds, privacy, typed routes and real MCP tools/call. The placeholders are **not valid FST/WLF** evidence. Running actual Wavepeek/wave-mcp, converting WLF, interpreting coverage or executing licensed Questa remains **NOT_RUN**.

References: [Wavepeek](https://github.com/kleverhq/wavepeek), [wave-mcp](https://github.com/Tencent/wave-mcp), [ModelSim Command Reference, wlf2vcd](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ProductDocuments/ReleaseNotes/modelsim_me_v105c_ref.pdf).

## Run-specific artifact directories

A separate `list_run_artifacts(project_id, run_id)` reads a newly created output directory for a given seed. The original `list_approved_artifacts` continues to describe unrelated pre-existing files. Directory association does not prove the file was produced by Siemens. See [RUN_ARTIFACTS](RUN_ARTIFACTS.en.md).
