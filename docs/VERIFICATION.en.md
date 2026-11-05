# Verification evidence model (M3 / #5)

[Русский](VERIFICATION.md)

Successful process exit, testbench completion and passing assertions are **separate facts**. Track `compile`, `elaboration`, `simulation` independently from `checker`. Exit code 0 or a "TEST PASSED" line **does not establish verification PASS**.

## Structured data

The internal `questa_mcp.verification` model accepts `test_id`, optional `seed` (0…2³²−1), `tool` (`questa`/`modelsim`), `tool_version`, `os`, `artifacts` (name → SHA-256), `phases.compile|elaboration|simulation` and `checker`.

Each process stage has `started`, `completed`, `exit_code`, `timed_out`, `cancelled`, `log` and optional `tool` (`vlog`/`vcom`/`vsim`). States: `NOT_RUN`, `UNKNOWN`, `COMPLETED`, `FAILED`, `TIMEOUT`, `CANCELLED`. `COMPLETED` describes the **reported process**, not a passed test. Negative evidence retains exact original transcript lines and line numbers; a nonzero exit is an independent process failure signal.

The checker has `executed`, `completed`, `checks_run`, `failures`, `success_evidence={source_line,raw}` and `failure_evidence`. Zero checks or missing positive evidence cannot prove successful verification. Arbitrary `raw` strings do not authenticate an actual test.

## Trust boundary

MCP tools `assess_verification_run(record)` and `assess_regression(runs)` receive **caller-controlled** data. A reported positive result stays `UNKNOWN` and tagged `CALLER_SUPPLIED_UNVERIFIED` even with all zero exit codes and a positive checker marker. Recognized negative errors/fatals are `FAIL` with line evidence, but do not prove the commercial EDA was actually invoked.

The internal Python-only `attested=True` switch tests the `PASS` transition with **synthetic fixtures only**; it is unavailable to MCP clients. Actual PASS requires a future authenticated local collector with verified artifact provenance. The current approved DO runner (#4) does not yet certify any individual phase.

## Regression

Up to 32 records, unique (`test_id`, `seed`) pairs, per-test evidence and `PASS/FAIL/UNKNOWN/NOT_RUN` counts. A negative indication yields `FAIL`; full regression `PASS` requires **all** reports to be trusted and positively checked. Otherwise `UNKNOWN` or `NOT_RUN`.

Total request limit is 1 MiB. Names, hashes and versions supplied by the caller are **not validated local artifact provenance**. Never send private transcripts or credentials.

Even the internal synthetic PASS transition requires non-empty tool version, OS and artifact hash metadata; missing provenance yields `UNKNOWN`.
