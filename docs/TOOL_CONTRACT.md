# Контракт MCP-инструментов v0

[English](TOOL_CONTRACT.en.md)

Контракт ограничен: анализ журналов и фаз не выполняет EDA. Экспериментальный исполнитель DO включается **только** локальным манифестом оператора и запускает ограниченную команду vsim; скрытых сетевых обращений сервер не выполняет.

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

## Защищённое исполнение (#4)

Экспериментальный запуск Siemens Questa / ModelSim уже поддерживает ограниченные идентификаторы, заранее разрешённые пути, явное согласие оператора, ограничение времени и логов, код возврата процесса. Достоверные результаты тестов и аттестованные артефакты ещё не реализованы. Не добавлять параметр `command` со свободным текстом Tcl/DO/shell.

## Уточнение контракта после #2/#3

`parse_diagnostics(text, tool="vsim", limit=200)` принимает `tool` из `vsim`, `vlog`, `vcom`. Вход — до 1 048 576 байт UTF-8 без NUL, без суррогатных Unicode; лимит 1–200. Ответ дополнительно содержит `unrecognized_lines`, `parser_status=UNKNOWN|PARTIAL|RECOGNIZED`, `test_verdict=FAIL|UNKNOWN`, `failure_evidence_count`, `eda_executed=false`. Каждая запись: `severity`, `code`, `emitter`, `file`, `line`, `column`, `time`, `instance`, `message`, `source_line`, `raw`, `format`, `confidence`. Поле `raw` сохраняет исходную строку без символа перевода строки. `confidence=HIGH` означает распознанный шаблон, **не успешную верификацию**. Текстовые пути не открываются. Нулевой exit code и сообщение «TEST PASSED» не дают права на PASS.

Для защиты от чрезмерно длинных строк парсер отклоняет любую строку свыше **8192 символов**. Ошибочные входные типы возвращают ошибку инструмента, а не UNKNOWN/PASS.

## Контракт исполнителя разрешённых профилей (#4)

`list_approved_projects()` показывает только IDs или `NOT_CONFIGURED`/`INVALID_CONFIGURATION`. `run_approved_project(project_id: str)` возвращает `status`, `exit_code`, `eda_executed`, `test_verdict=FAIL|UNKNOWN`, пофазные `UNKNOWN`, число диагностик, необязательные явно разрешённые строки, размер и SHA-256 захваченного вывода, полноту журнала. Никаких Tcl/DO или путей от MCP; см. [конфигурацию](APPROVED_PROJECTS.md). Код 0 не становится PASS.

Исполнитель использует зафиксированный временный снимок DO, а не исходный файл после проверки SHA-256. `TERMINATION_UNCONFIRMED` — остановка дерева процессов не подтверждена; повторный запуск без осмотра запрещён. `DO_HASH_MISMATCH` и `INVALID_SCRIPT` не запускают EDA и имеют `eda_executed=false`.

## Фазовая модель верификации (#5)

Инструменты `assess_verification_run(record)` и `assess_regression(runs)` разделяют компиляцию, элаборацию, симуляцию, проверки и регрессии. Положительные заявления клиента **не повышаются до PASS**. См. [контракт верификации](VERIFICATION.md). Реальный Siemens EDA: **NOT_RUN**.

Questa/ModelSim `** Error (suppressible):` и `** Warning (suppressible):` распознаются; записи содержат `qualifier="suppressible"` или `null`. Пометка suppressible **не переводит ошибку в успех**.

## Экспериментальный сбор свежих JUnit (#5)

Если оператор разрешил `executable_sha256` и `checker={"format":"cocotb-junit-v1","expected_tests":[...]}`, `run_approved_project` задаёт новый приватный путь `COCOTB_RESULTS_FILE` для каждого запуска. Ответ включает `checker` (формат, состояние, причина, счётчики, SHA-256 XML), `checker_verdict=PASS|FAIL|UNKNOWN`, `assertions_verdict=UNKNOWN`, `regression_verdict=UNKNOWN`, `run_provenance`, `transcript_utf8_lossless`/`transcript_parser_complete`. **Общий `test_verdict=UNKNOWN` даже при checker PASS**, пока не подтверждены внешние assertions и полнота фаз. Негативные свидетельства процесса или checker позволяют `test_verdict=FAIL`. Хеш бинарника сверяется до и после запуска. MCP не принимает пути checker, XML, произвольные Tcl или команды исполнения. См. [правила](JUNIT_EVIDENCE.md). Неизвестные дополнительные JSON-поля SDK может игнорировать, но не трактует как команды.

## Read-only артефакты (#6)

`list_approved_artifacts(project_id: str)` выбирает только разрешённый профиль и его список `artifacts` (не более 8). Без разрешения — `DENIED`/`NOT_CONFIGURED`; неверная конфигурация — `INVALID_CONFIGURATION`. Каждая запись содержит `id`, `format`, `declared_time_unit`, `time_unit_source`, `size_bytes`, `sha256` (если файл до 8 МиБ), `state`, `format_validated=false`, `origin=EXISTING_WORKSPACE_FILE_NOT_ATTESTED`, `produced_by_run_id=null`, `external_execution=NOT_RUN`, `paths_disclosed`, опциональный `local_path` и `routes`. Путь и содержимое клиент передавать не может. WLF требует отдельной конвертации, UCDB — vendor-native coverage. Подробности: [манифест](ARTIFACT_HANDOFF.md).

## `run_approved_regression(project_id)` (#5)

Только разрешённый ID. Профиль требует точно три `phase_scripts` (`compile`, `elaboration`, `simulation`), каждое с `do_script` и `do_sha256`, а также `executable_sha256`; необязательные `regression_seeds` содержат 1–8 уникальных целых 0…2³²−1. Ответ: `status`, `regression_verdict=FAIL|UNKNOWN|NOT_RUN`, `test_count`, `counts`, `runs[].run_id`, `runs[].seed`, `runs[].phases`, `runs[].checker_verdict`, `runs[].test_verdict`, `runs[].assertions_verdict`, `provenance`. Завершённая фаза обозначает завершение заявленного процесса, а не доказательство операции внутри DO. Положительный checker не приводит к общему PASS. См. [подробный контракт](PHASE_RUNNER.md).

## `list_run_artifacts(project_id, run_id)` (#6)

Read-only инструмент принимает ID разрешённого проекта и ровно 24 lowercase hex символа run_id. Локальный профиль задаёт безопасный каталог `run_artifacts_dir` и непустой список `run_artifacts`. Поля `observed_in_run_id`, `origin=OBSERVED_IN_RUN_DIRECTORY_NOT_VENDOR_ATTESTED`, `produced_by_run_id=null`, `format_validated=false`. Некорректные ID дают `DENIED`, отсутствующий каталог — `RUN_NOT_FOUND`. Абсолютные пути по умолчанию скрыты. См. [контракт](RUN_ARTIFACTS.md).

## `prepare_run_handoff(project_id, run_id, artifact_id, consumer)` (#6)

Только разрешённый `project_id`, 24-hex `run_id`, разрешённый `artifact_id` и `consumer=wavepeek|wave-mcp`. Без локального согласия на путь — `OPT_IN_REQUIRED`. Только VCD/FST; WLF/UCDB — `UNSUPPORTED_NATIVE_FORMAT`. `READY_FOR_EXTERNAL_CLIENT` означает наличие локального указателя, **не успешный запуск анализатора**. Ответ без секретов, кроме отдельно разрешённого абсолютного пути. См. [подробности](RUN_ARTIFACTS.md).
