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
