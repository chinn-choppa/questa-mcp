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

- [Wavepeek](https://github.com/kleverhq/wavepeek) (Apache-2.0): the official **v3.2.0** binary is downloaded by Linux CI, SHA-256 `8dc788e7c8b065fc422e5274e54d9466ace52ed748c673f54d9b7aedb9b5b711`; **not bundled** with the repository. [Tencent wave-mcp](https://github.com/Tencent/wave-mcp) (Apache-2.0): documented consumer route only, **NOT_RUN**.
- [GTKWave vcd2fst](https://gtkwave.github.io/gtkwave/man/vcd2fst.1.html): open-source VCD→FST converter installed in a **separate Linux CI job**, never used at MCP runtime or bundled.
- [ModelSim wlf2vcd](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ProductDocuments/ReleaseNotes/modelsim_me_v105c_ref.pdf): specific vendor-edition reference only; the converter is never invoked.

