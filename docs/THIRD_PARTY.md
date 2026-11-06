# Сторонние компоненты и происхождение

[English](THIRD_PARTY.en.md)

Репозиторий `questa-mcp` является самостоятельной оригинальной реализацией. Начальный код не копировался из сторонних серверов MCP.

- [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk): зависимость `mcp==2.3.0`, отдельная лицензия Apache-2.0.
- [GitHub Actions checkout](https://github.com/actions/checkout): версия v7.0.1, закреплённая SHA.
- [GitHub Actions setup-python](https://github.com/actions/setup-python): версия v7.1.0, закреплённая SHA.
- EDA-продукт устанавливается пользователем отдельно; исполняемые файлы и лицензии производителей не поставляются.

Перед заимствованием исходного кода, шаблонов и примеров из сторонних проектов необходимо проверить совместимость лицензий и оформить атрибуцию.

- [setup-uv](https://github.com/astral-sh/setup-uv): действие CI, тег v7.

- [cocotb](https://github.com/cocotb/cocotb): использован публичный формат JUnit XML и документированная переменная `COCOTB_RESULTS_FILE`, проект BSD-3-Clause. Код cocotb не копируется и пакет не требуется для самого MCP-сервера; тесты используют оригинальный синтетический XML.

- [Wavepeek](https://github.com/kleverhq/wavepeek) (Apache-2.0) и [Tencent wave-mcp](https://github.com/Tencent/wave-mcp) (Apache-2.0): использованы только сведения о поддержке VCD/FST/FSDB и внешних маршрутах; код и анализаторы не копируются/не встраиваются.
- [ModelSim wlf2vcd](https://ww1.microchip.com/downloads/aemdocuments/documents/fpga/ProductDocuments/ReleaseNotes/modelsim_me_v105c_ref.pdf): ссылка на руководство отдельной редакции; команда не вызывается.


- [Wavepeek](https://github.com/kleverhq/wavepeek) v3.2.0: официальный бинарник загружается **только в Linux CI**, SHA-256 `8dc788e7c8b065fc422e5274e54d9466ace52ed748c673f54d9b7aedb9b5b711`, не копируется в репозиторий и не исполняется самим MCP.
- [GTKWave vcd2fst](https://gtkwave.github.io/gtkwave/man/vcd2fst.1.html): открытый конвертер VCD→FST, устанавливается через `apt` только в интеграционном CI. Лицензируемые компоненты Siemens отсутствуют.
