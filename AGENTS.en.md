# Agent contract

[Русский](AGENTS.md)

This is an independent public MCP adapter, not a copy of agent-dev-toolkit.

- Read README, SECURITY, and TOOL_CONTRACT before editing; verify the current official MCP Python SDK.
- Research existing solutions first and implement the smallest tested change.
- Never infer verification PASS from Python import, tools/list, exit code 0, or missing errors.
- Never introduce a general shell/Tcl/DO execution capability. Side-effecting vendor operations need an explicit, reviewed design and negative tests.
- Use only public synthetic RTL and logs; never publish licenses, proprietary files, transcripts or secrets.
- Use uv in a project-local environment. Document Windows/Linux evidence separately from EDA validation.
- Each operation needs type, size and failure-path tests.
- Update Russian and English public documentation together.
- Check licenses before borrowing third-party code.
