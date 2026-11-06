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

For Questa 2025.2+, cocotb documents a distinct QIS/Qrun path alongside the legacy vlog/vopt/vsim compatibility flow. This is **not** evidence that this MCP adapter supports Qrun. Test specific editions and versions before claiming support. See [cocotb simulator support](https://docs.cocotb.org/en/stable/simulator_support.html).

Opt-in approved DO execution is implemented with mock subprocesses but **not tested against real Siemens products**; neither command-line compatibility nor process-tree teardown has vendor-level acceptance yet.

The optional cocotb JUnit checker relies on `COCOTB_RESULTS_FILE`, a cocotb-defined environment variable; actual DO scripts and vendor editions have **NOT_RUN** acceptance. Its binary hash pin verifies the locally approved file's content, **not** Siemens authenticity, product licensing or OS sandboxing. Independent vendor SVA/coverage success is not inferred from cocotb's JUnit XML. See [JUnit collector](JUNIT_EVIDENCE.en.md).

## External analyzer compatibility (#6)

VCD/FST routes reflect documented Wavepeek and Tencent wave-mcp capabilities, **not an observed external invocation**. Native WLF is not considered directly supported; `wlf2vcd` is documented for specific older ModelSim versions but is not invoked here. UCDB requires vendor tooling. Windows/Linux CI validates metadata only, not installed external tool compatibility. See [manifest](ARTIFACT_HANDOFF.en.md).

Sequential `vsim -c -do` phases are mock-tested only, not proof that the particular Siemens/ModelSim edition provides a compatible vlog/vcom flow. Phase meaning is operator-declared via approved DO. Actual consumption of `QUESTA_MCP_SEED` by the simulator has not been verified. See [contract](PHASE_RUNNER.en.md).

Run-ID directories are tested only with Windows/Linux synthetic processes. Commercial DO must explicitly consume `QUESTA_MCP_ARTIFACT_DIR`. Actual Siemens and external VCD/FST/UCDB consumers remain `NOT_RUN`. See [mode](RUN_ARTIFACTS.en.md).
