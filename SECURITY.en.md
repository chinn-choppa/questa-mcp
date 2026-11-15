# Security policy

[Русский](SECURITY.md)

## Reporting vulnerabilities

Do not publish working exploits, tokens, private RTL or licensed data in public issues. Use GitHub's private vulnerability reporting if enabled; otherwise contact the maintainer through an established private channel.

## Threat model

MCP inputs are untrusted, even when the transport is local. The current tools only inspect simulator availability and parse caller-supplied bounded text. There are **no vendor process launches, project file reads, network listeners, or automatic uploads**.

- Tool discovery does not reveal the local executable path, license variables or environment.
- Parsing does not open filenames appearing in the transcript. Input is capped at 1 MiB; output at 200 diagnostics.
- `readOnlyHint` and other MCP annotations are **not** an access control mechanism.
- Logs themselves may contain private paths or secrets; users must sanitize them before sending them to a remote model.
- A local stdio host does not prevent its AI client from transmitting tool results elsewhere.

Future #4 process execution needs a separate threat-model review, administrator-managed allowlists, canonical paths, symlink/path traversal defense, no `shell=True`, controlled subprocess trees, explicit resource limits, and opt-in artifact output. **Even an allowlisted DO script can execute Tcl with the user's permissions**; only deliberately trusted scripts can be enabled.

No product/OS combination has yet been validated with a live licensed Questa run.
