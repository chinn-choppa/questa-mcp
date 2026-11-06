# Approved phase runner and regression seeds (#5)

[Русский](PHASE_RUNNER.md)

## Purpose

`run_approved_regression(project_id)` executes three operator-approved DO files through local `vsim -c -do`: `compile`, `elaboration`, `simulation`. Separate files and SHA-256 hashes distinguish process completions, **not proof that the declared compile/elaborate/simulate action truly occurred inside Tcl**. The MCP client supplies only an allowed project ID; no arbitrary shell, Tcl, file paths or seeds.

## Local manifest

Extend an existing operator-approved project profile containing `workspace`, `executable`, `executable_sha256`, `do_script`, `do_sha256`, `operator_approved=true` and `disposable_workspace=true`:

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

These are **placeholder hashes**. All three DO files must exist under the workspace and match the operator's SHA-256; the `vsim` executable requires a pinned SHA-256 too. Only the fixed three phase names are allowed. The operator may specify 1–8 unique integer `regression_seeds` from 0 to 2³²−1. The default is `[0]`; absent `phase_scripts` returns `PHASES_NOT_CONFIGURED`.

Each subprocess receives `QUESTA_MCP_SEED` in its environment. **The adapter does not observe whether the trusted DO script actually consumed that seed.** The script author must deliberately read and apply it. A new private `COCOTB_RESULTS_FILE` is provided for each simulation phase when cocotb checking is configured. Compilation is repeated per seed for simple reproducibility; this is not an incremental-build optimization.

## Evidence and verdicts

Each configured seed produces a unique `run_id` with independent `phases.compile`, `phases.elaboration`, and `phases.simulation` records: `NOT_RUN`, `COMPLETED`, `FAILED`, `TIMEOUT` or `UNKNOWN`. A phase not completing stops later phases for that seed. Returned fields include process exit code, bounded stdout size and SHA-256, diagnostic count, failure indications and the approved DO hash. Raw log lines are withheld unless `expose_diagnostics=true` is operator-approved.

A `COMPLETED` phase only means the declared subprocess exited zero with no recognized failure. `phase_trust=OPERATOR_DECLARED_DO_PHASE_NOT_VENDOR_ATTESTED` explicitly disclaims authoritative vendor proof.

Valid cocotb JUnit establishes at most `checker_verdict=PASS` for the expected cocotb self-checks. Overall `test_verdict` and `regression_verdict` remain `UNKNOWN` unless observed negative evidence yields `FAIL`. Independent SystemVerilog assertions, actual seed consumption, and coverage remain unverified. No full RTL regression PASS is inferred.

## Security and acceptance boundary

Only administrator-approved fixed files are invoked. DO runs with the OS user's privileges; a disposable workspace **is not an OS sandbox**. Network/license-server access performed by the vendor tool or DO script requires the operator's consent. Cleanup on cancellation is protected, but complete descendant termination of a real `vsim` is not yet evidenced. Execution is limited to eight seeds × three phases, with per-process timeout and output limits.

Public CI uses synthetic DO and mock processes, negative config and seed tests, and a real MCP `tools/list`/`tools/call` roundtrip. Licensed Siemens Questa/ModelSim, actual HDL phases and native assertions remain **NOT_RUN**.
## New output directory per seed

Optional `run_artifacts_dir` and `run_artifacts` create a fresh directory for each run ID; approved Tcl receives `QUESTA_MCP_ARTIFACT_DIR`. Files are retained until manual cleanup; vendor provenance remains unverified. See [RUN_ARTIFACTS](RUN_ARTIFACTS.en.md).
