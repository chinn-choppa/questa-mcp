# Third-party components and provenance

[Русский](THIRD_PARTY.md)

This is an independently implemented MCP adapter. No source code was copied from other EDA MCP servers.

- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk): pinned `mcp==2.3.0`, separate Apache-2.0 license.
- [GitHub Actions checkout](https://github.com/actions/checkout): v7.0.1 by SHA.
- [GitHub Actions setup-python](https://github.com/actions/setup-python): v7.1.0 by SHA.
- [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv): v7 tag in CI.
- Questa/ModelSim binaries and licenses are user-provided and never redistributed.

Review licenses and provide attribution before incorporating any external source code, templates or examples.

- [cocotb](https://github.com/cocotb/cocotb): external JUnit XML report format and `COCOTB_RESULTS_FILE` documented interface, BSD-3-Clause project; no cocotb code bundled or dependency required by the MCP server. Tests use original synthetic XML.

- [Wavepeek](https://github.com/kleverhq/wavepeek) (Apache-2.0) and [Tencent wave-mcp](https://github.com/Tencent/wave-mcp) (Apache-2.0): only documented VCD/FST/FSDB support is used to describe external routes; no code is copied or integrated.
- [ModelSim wlf2vcd](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ProductDocuments/ReleaseNotes/modelsim_me_v105c_ref.pdf): specific vendor-edition reference only; the converter is never invoked.

