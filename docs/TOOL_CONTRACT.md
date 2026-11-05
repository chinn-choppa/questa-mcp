    # Контракт MCP-инструментов v0

[English](TOOL_CONTRACT.en.md)

    На этом этапе контракт намеренно ограничен. Все операции возвращают JSON-совместимые структуры, не содержат скрытых сетевых обращений и не запускают EDA.

    ## `server_info()`

    Возвращает `server`, `version`, `vendor_tool`, `stage`, `operations`. `stage="bootstrap"` запрещает трактовать результаты как готовую автоматизацию Siemens Questa / ModelSim.

    ## `tool_status()`

    Проверяет наличие исполняемого файла, не запускает его. Поля: `tool`, `state`, `configured`, `executed=false`. Возможные состояния: `DETECTED_UNVERIFIED`, `NOT_FOUND`, `INVALID_OVERRIDE`. Не раскрывает полный путь, настройки лицензии или содержимое окружения.

    ## `parse_diagnostics(text, limit=200)`

    Принимает текст журнала до **1 МиБ**. Поддерживает не более 200 результатов в одном ответе. Возвращает `tool`, `count`, `truncated`, `items` с полями `severity`, `code`, `file`, `line`, `column`, `message`, `raw`. Неизвестные строки игнорируются, а не превращаются в выдуманные ошибки.

    Пример сообщения:

    ```text
    ** Error: (vsim-3601) Iteration limit reached
** Warning: (vlog-2240) Port connection mismatch
    ```

    Обратите внимание: `parse_diagnostics` возвращает лишь совпадения с известными шаблонами. Отсутствие совпадений **не означает** успешной сборки. Исходные строки сохраняются для проверки.

    ## Будущие команды

    Для запуска Siemens Questa / ModelSim потребуются отдельные аргументы с ограниченными перечислениями и путями, явное подтверждение побочных эффектов, ограничение времени и логов, код возврата процесса и атомарно создаваемые артефакты. Не добавлять параметр `command` со свободным текстом Tcl/DO/shell.

## Уточнение контракта после #2/#3

`parse_diagnostics(text, tool="vsim", limit=200)` принимает `tool` из `vsim`, `vlog`, `vcom`. Вход — до 1 048 576 байт UTF-8 без NUL, без суррогатных Unicode; лимит 1–200. Ответ дополнительно содержит `unrecognized_lines`, `parser_status=UNKNOWN|PARTIAL|RECOGNIZED`, `test_verdict=FAIL|UNKNOWN`, `failure_evidence_count`, `eda_executed=false`. Каждая запись: `severity`, `code`, `emitter`, `file`, `line`, `column`, `time`, `instance`, `message`, `source_line`, `raw`, `format`, `confidence`. Поле `raw` сохраняет исходную строку без символа перевода строки. `confidence=HIGH` означает распознанный шаблон, **не успешную верификацию**. Текстовые пути не открываются. Нулевой exit code и сообщение «TEST PASSED» не дают права на PASS.

Для защиты от чрезмерно длинных строк парсер отклоняет любую строку свыше **8192 символов**. Ошибочные входные типы возвращают ошибку инструмента, а не UNKNOWN/PASS.

Questa/ModelSim `** Error (suppressible):` и `** Warning (suppressible):` распознаются; записи содержат `qualifier="suppressible"` или `null`. Пометка suppressible **не переводит ошибку в успех**.
