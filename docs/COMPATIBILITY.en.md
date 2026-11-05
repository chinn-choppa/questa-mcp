# Compatibility

[Русский](COMPATIBILITY.md)

| Layer | Tested evidence | Boundary |
| --- | --- | --- |
| Python | 3.11, 3.13 in Ubuntu/Windows GitHub Actions | Python 3.15 NOT_RUN |
| Official MCP Python SDK | 2.3.0, real in-process and stdio `tools/list`/`tools/call` | Other SDK versions NOT_RUN |
| Linux | Ubuntu GitHub Actions pure Python and MCP | Licensed EDA NOT_RUN |
| Windows | Windows GitHub Actions pure Python and MCP | Licensed EDA NOT_RUN |
| Siemens Questa / ModelSim | None | Vendor versions/editions NOT_RUN |
| Closed RTL projects | Not used | Never part of public CI |

Tool discovery does not check vendor version or licensing. Product compatibility claims require the exact product edition and version, operating system, license state and a recorded real RTL invocation.

The runtime never provides or downloads vendor binaries, IP, licenses or private artifacts. Native WLF has no presumed direct Wavepeek/wave-mcp support.
