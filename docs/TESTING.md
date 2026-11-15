# Проверка проекта

## Быстрые проверки без EDA и внешней сети

```bash
uv run --locked pytest -q tests
uv run --locked python -m compileall -q src tests
```

PowerShell:

```powershell
uv run --locked pytest -q tests
uv run --locked python -m compileall -q src tests
```

## При наличии SDK MCP

```bash
uv sync --locked
uv run --locked questa-mcp
```

Подключить MCP Inspector либо клиент Codex/Claude/OpenCode, проверить реальный `tools/list`, затем вызвать `server_info` и `parse_diagnostics` на синтетических данных. Только после успешного фактического вызова инструмента можно фиксировать `MCP_TOOL_PASS`. Простой старт процесса или наличие пакета означает максимум `INSTALLED`.

## Реальное EDA-тестирование

**Пока не предусмотрено** в bootstrap. После появления команд выполняйте на публичных минимальных RTL-проектах: lint, негативный кейс, сбой лицензии/тайм-аут, успешное завершение по самопроверяющемуся тесту, повреждённый файл, неверный путь и ограничение каталогов. Записывайте версии и SHA используемых исходников.

## Pytest и закреплённые зависимости

Тестовый контракт — `uv sync --locked` и `uv run --locked pytest -q tests`.
Все текущие базовые unit-тесты — нативные pytest (`assert`, `raises`, `monkeypatch`, `tmp_path`, `parametrize`).
Проверка конструктора SDK не пропускается при его отсутствии; отсутствие зависимости — ошибка CI.
Реальная Questa/лицензия и команды из будущих PR проверяются отдельно.
