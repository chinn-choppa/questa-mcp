# Разрешённый пофазный запуск и регрессии (#5)

[English](PHASE_RUNNER.en.md)

## Назначение

`run_approved_regression(project_id)` выполняет три заранее утверждённых оператором DO-сценария через локальный `vsim -c -do`: `compile`, `elaboration`, `simulation`. Отдельные сценарии и хеши позволяют различать завершение процессов, но **не доказывают, что внутри DO действительно выполнялась соответствующая операция**. Исполнитель доверяет только выбору разрешённого идентификатора и не принимает Tcl, shell-команды, пути или seed из MCP.

## Конфигурация

Добавьте поля к существующему профилю с `workspace`, `executable`, `executable_sha256`, `do_script`, `do_sha256`, `operator_approved=true`, `disposable_workspace=true`:

```json
{
  "phase_scripts": {
    "compile": {"do_script": "compile.do", "do_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    "elaboration": {"do_script": "elaborate.do", "do_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
    "simulation": {"do_script": "simulate.do", "do_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"}
  },
  "regression_seeds": [101, 102],
  "checker": {"format": "cocotb-junit-v1", "expected_tests": ["check_counter"]}
}
```

Хеши **демонстрационные**. Каждый DO должен существовать под рабочим каталогом и проходить SHA-256; бинарник `vsim` также должен быть закреплён SHA-256. Разрешены только три фиксированные фазы. Список `regression_seeds` задаёт оператор: 1–8 уникальных целых значений в диапазоне 0…2³²−1. Без списка используется `[0]`; без `phase_scripts` инструмент возвращает `PHASES_NOT_CONFIGURED`.

Каждый процесс получает `QUESTA_MCP_SEED` через окружение. **Фактическое использование seed DO-сценарием не проверяется**. Автор доверенного DO обязан сам прочитать это значение и передать его симулятору. Для `simulation` автоматически создаётся свежий приватный `COCOTB_RESULTS_FILE` (при настроенном checker). Исполнитель повторяет компиляцию для каждого seed; это простая, воспроизводимая базовая реализация, не оптимизированный инкрементальный build.

## Результаты

Каждый seed имеет `run_id` и три независимых записи `phases`: `NOT_RUN`, `COMPLETED`, `FAILED`, `TIMEOUT` или `UNKNOWN`. После состояния, отличного от `COMPLETED`, следующие фазы не запускаются. Сохраняются код возврата, SHA-256 и размер вывода, число диагностик, ограниченные признаки ошибок и SHA-256 сценария. Исходные строки диагностик скрыты, пока оператор не включит `expose_diagnostics=true`.

Завершение `compile` или `elaboration` означает только завершение **утверждённого процесса с кодом 0 и без распознанных ошибок**. Метка `phase_trust=OPERATOR_DECLARED_DO_PHASE_NOT_VENDOR_ATTESTED` не является подтверждением результатов производителя.

Корректный JUnit XML даёт `checker_verdict=PASS` только для самопроверок cocotb. Общий `test_verdict` каждого прогона и `regression_verdict` остаются `UNKNOWN`, если не обнаружено отрицательное свидетельство (`FAIL`). Независимые SVA, реально применённые seeds и coverage пока не подтверждаются. `PASS` всей RTL-регрессии не заявляется.

## Безопасность и статус

Работают только оператором разрешённые фиксированные файлы. Процессы имеют права запустившего пользователя: одноразовый workspace **не песочница ОС**. Внешние лицензии и любой сетевой доступ DO остаются зоной явного согласия оператора. Отмена операций выполняет защищённую очистку, но полная остановка потомков реального `vsim` не доказана. Число запусков ограничено восьмью seed × три фазы; тайм-аут и вывод ограничены для каждого процесса.

Публичный CI проверяет искусственные DO, макетный процесс, сценарии успеха, отказов, недопустимых seed и настоящий MCP `tools/list`/`tools/call`. Лицензируемая Questa/ModelSim, реальные VHDL/SystemVerilog фазы и аппаратные assertions — **NOT_RUN**.
## Новые каталоги файлов по seed

Опциональные `run_artifacts_dir` и `run_artifacts` создают новый каталог на каждый run_id; доверенный DO получает `QUESTA_MCP_ARTIFACT_DIR`. Файлы сохраняются до ручного удаления, но их подлинность не подтверждается. См. [RUN_ARTIFACTS](RUN_ARTIFACTS.md).
