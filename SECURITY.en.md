# Security policy

[Русский](SECURITY.md)

## Reporting vulnerabilities

Do not publish working exploits, tokens, private RTL or licensed data in public issues. Use GitHub's private vulnerability reporting if enabled; otherwise contact the maintainer through an established private channel.

## Threat model

MCP inputs are untrusted, even when the transport is local. By default tools only discover an installed simulator, parse bounded caller-supplied text, and analyze phase reports. An **explicit operator-approved profile** additionally enables local vsim execution of a pre-approved DO snapshot. There are no network listeners or automatic uploads. The server reads the approved DO, not RTL project source files.

- Tool discovery does not reveal the local executable path, license variables or environment.
- Parsing does not open filenames appearing in the transcript. Input is capped at 1 MiB; output at 200 diagnostics.
- `readOnlyHint` and other MCP annotations are **not** an access control mechanism.
- Logs themselves may contain private paths or secrets; users must sanitize them before sending them to a remote model.
- A local stdio host does not prevent its AI client from transmitting tool results elsewhere.

Future #4 process execution needs a separate threat-model review, administrator-managed allowlists, canonical paths, symlink/path traversal defense, no `shell=True`, controlled subprocess trees, explicit resource limits, and opt-in artifact output. **Even an allowlisted DO script can execute Tcl with the user's permissions**; only deliberately trusted scripts can be enabled.

No product/OS combination has yet been validated with a live licensed Questa run.

## Approved DO scripts

The operator must explicitly attest to a disposable workspace and reviewed script hash. **DO is executable Tcl and can escape the workspace.** This project is not an OS sandbox; use a separate restricted account or VM. Raw diagnostic disclosure is opt-in. See [Approved projects](docs/APPROVED_PROJECTS.en.md).

## #4 hardened boundary

A private snapshot of the SHA-256 checked DO file prevents later edits to the original from silently changing the launched script. Referenced files remain mutable and the snapshot is not a user/OS permission boundary. `TERMINATION_UNCONFIRMED` requires manual inspection/cleanup, not automatic retries. A disposable workspace alone is not isolation.

## Fresh JUnit collection (experimental)

The checker-enabled profile requires a pinned SHA-256 of the executable, checked before and after the local run. The generated XML is accepted only from a new private location; symlinks, DTD/entities and inconsistent counts are rejected. Failure to decode a transcript losslessly or parse it fully blocks any positive checker result. This is not cryptographic attestation of the vendor or an OS sandbox: an approved Tcl script, or another process with equivalent OS rights, may still falsify XML. No raw JUnit report is returned to the MCP client; see [threat boundary](docs/JUNIT_EVIDENCE.en.md).

During MCP cancellation, cleanup now handles repeated cancellation and a pending process spawn without abandoning the subprocess before the temporary DO snapshot is removed. OS-level child-tree termination remains best-effort and requires independent acceptance; avoid claiming a complete sandbox or guaranteed descendant shutdown.

## Waveform/coverage metadata (#6)

Only operator-declared relative artifacts may be read; MCP callers cannot supply arbitrary paths. No file contents are returned, at most 8 MiB per artifact is read for SHA-256 and large files are not hashed. Absolute paths are hidden unless the operator explicitly enables `expose_artifact_paths`, which may disclose infrastructure locations to a remote AI client. Symlink/workspace checks are portable best-effort **not a defense against same-user races or an OS sandbox**. No Wavepeek, wave-mcp or vendor converter is invoked. See [artifact threat model](docs/ARTIFACT_HANDOFF.en.md).

## Approved multi-phase execution security

The new MCP operation accepts no caller-supplied command, DO path or seed; all values are fixed in operator-local config. All three DO scripts and the executable must match SHA-256. Approved Tcl still runs as the current OS user and requires isolation. `QUESTA_MCP_SEED` is an environment variable, **not proof of simulator seed consumption**. See [phase-runner contract](docs/PHASE_RUNNER.en.md).

## Retained output directories

The operator prepares a safe root under workspace; the server creates random child directories without automatic deletion. The operator controls permissions, quotas and retention. The 8 MiB hashing cap does not constrain vendor disk writes. A same-user process may modify results. See [security boundary](docs/RUN_ARTIFACTS.en.md).
