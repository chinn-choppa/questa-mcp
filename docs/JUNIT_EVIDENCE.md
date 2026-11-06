# Свежие JUnit-свидетельства cocotb

[English](JUNIT_EVIDENCE.en.md)

Экспериментальная интеграция задачи [#5](https://github.com/chinn-choppa/questa-mcp/issues/5) в доверенный **локальный исполнитель** задачи #4. Используются существующий формат JUnit XML cocotb и переменная `COCOTB_RESULTS_FILE` — отдельный универсальный анализатор RTL не создаётся.

## Разрешённый профиль

В файле, указанном оператором через `QUESTA_MCP_PROJECTS_CONFIG`, дополните профиль:

```json
{
  "projects": {
    "public-counter": {
      "workspace": "/absolute/disposable/workspace",
      "executable": "/absolute/questa/bin/vsim",
      "executable_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "do_script": "run.do",
      "do_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "operator_approved": true,
      "disposable_workspace": true,
      "timeout_seconds": 120,
      "checker": {
        "format": "cocotb-junit-v1",
        "expected_tests": ["check_counter"]
      }
    }
  }
}
```

Хеши в примере **фиктивны**. Подставьте SHA-256 реального одобренного бинарника и DO-файла. На Windows можно использовать `Get-FileHash -Algorithm SHA256 <путь>`, на Linux — `sha256sum <путь>`. Списки ожидаемых тестов задаёт оператор; без непустого списка и SHA-256 бинарника конфигурация отклоняется.

Сервер запускает только заранее утверждённый `vsim -c -do`. Для **каждого** запуска создаёт новый приватный временный каталог и передаёт путь к ещё не существующему `results.xml` через `COCOTB_RESULTS_FILE`. Утверждённый сценарий должен сам запускать cocotb и завершаться с корректным кодом возврата. Если сценарий не использует cocotb или cocotb не наследует переменную окружения, отчёт не появится — результат `UNKNOWN`.

## Условия оценки

- Читается только обычный файл внутри нового временного каталога; символьные ссылки отклоняются. Максимум 128 КиБ XML и 256 тестов; DTD/ENTITY запрещены.
- Проверяются сведения о каждом `testcase`, точное совпадение имён с `expected_tests`, отсутствие повторов, сопоставление счётчиков `tests/failures/errors/skipped` с реальными элементами и корректность XML. Любой пропуск или повреждение → `UNKNOWN`; зарегистрированный failure/error → `FAIL` для checker.
- Для положительной оценки требуется завершившийся с кодом 0 процесс, полный журнал без ошибок/fatal, UTF-8 без замены символов, успешный парсер диагностик и **неизменность** бинарника до/после запуска.
- Успешный результат означает только `checker_verdict=PASS`: самопроверки cocotb представлены свежим валидированным отчётом. **Общий `test_verdict=UNKNOWN`**, а `assertions_verdict`, `regression_verdict` и статус каждой отдельной фазы остаются `UNKNOWN`. Внешние SVA и покрытие этой проверкой не подтверждаются.
- Ненулевой код процесса, распознанная fatal/error или ошибка checker → отрицательное свидетельство `test_verdict=FAIL`.
- Хеши бинарника, DO, отчёта и захваченного stdout предназначены для происхождения данных; они не являются криптографической подписью, удостоверяющей Siemens или фактический охват проверок.

По умолчанию MCP не выдаёт сырые XML, локальные пути и тексты диагностик. Директория и отчёт удаляются после вызова. Управление EDA и DO остаётся привилегированным; необходимы доверенный DO, изоляция ОС, лицензия и одобрение оператора на возможные обращения к серверу лицензий.

## Состояние приёмки

Публичный CI имитирует процесс с именем `vsim`, создающий XML по переданному пути, и проверяет успешный, ошибочный, неполный, подменённый и пропущенный отчёты на Windows/Linux. **Реальная Questa/ModelSim, лицензия, внешние assertions и полный regression PASS: NOT_RUN.** Поддержка cocotb в конкретной версии продукта требует отдельной приёмки.

Источники: [cocotb JUnit](https://docs.cocotb.org/en/stable/junit.html), [справочник формата](https://docs.cocotb.org/en/stable/junit_reference.html), [cocotb test results](https://docs.cocotb.org/en/stable/_modules/cocotb_tools/check_results.html).
