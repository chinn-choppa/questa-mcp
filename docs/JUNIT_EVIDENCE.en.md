# Fresh cocotb JUnit evidence

[Русский](JUNIT_EVIDENCE.md)

Experimental [#5](https://github.com/chinn-choppa/questa-mcp/issues/5) integration with the operator-approved **local runner** (#4). The existing cocotb JUnit XML format and `COCOTB_RESULTS_FILE` variable are reused; this adapter does not become a universal RTL test engine.

## Approved profile

Add the following to the administrator-authored file selected by `QUESTA_MCP_PROJECTS_CONFIG`:

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

The hashes above are **placeholders**. Supply SHA-256 values for the real reviewed simulator executable and approved DO file. On Windows, use `Get-FileHash -Algorithm SHA256 <path>`; on Linux, `sha256sum <path>`. The operator fixes the expected test names; missing expected names or a missing binary hash prevents activating the checker.

Only the pre-approved `vsim -c -do` operation is performed. Every run gets a new private temporary directory and the path to a nonexistent `results.xml` through `COCOTB_RESULTS_FILE`. The approved script must invoke cocotb and exit with a meaningful code. If cocotb does not run or does not honor the inherited environment, the file is missing and the outcome is `UNKNOWN`.

## Evaluation rules

- Only a regular file in the fresh directory is accepted; symlinks are rejected. XML is capped at 128 KiB and 256 testcases; DTD/ENTITY declarations are denied.
- Every `testcase` is inspected. The full set of names must exactly match `expected_tests` without duplicates, and the `tests/failures/errors/skipped` suite counts must agree with actual XML elements. Missing, skipped, inconsistent or malformed results yield `UNKNOWN`; registered test failures/errors yield a negative checker verdict.
- Positive checker evidence requires process exit 0, a complete captured transcript with no recognized fatal/errors, valid UTF-8 without replacement characters, a successfully parsed transcript, and an unchanged pinned executable hash before and after execution.
- Successful checking establishes **only `checker_verdict=PASS`**: the approved local process produced a fresh consistent cocotb report. Overall `test_verdict=UNKNOWN`; `assertions_verdict`, `regression_verdict`, and each phase remain `UNKNOWN`. External SystemVerilog assertions and coverage are not proven by this mechanism.
- A failed process, recognized fatal/error, or failed checker gives negative evidence (`test_verdict=FAIL`).
- Binary, DO, XML and captured-stdout hashes provide data provenance, **not cryptographic proof** of genuine Siemens execution or full test coverage.

By default the MCP response does not disclose the raw XML, local paths or transcript diagnostics. The fresh directory and report are deleted after the call. An approved DO remains privileged Tcl; use a restricted OS environment, a reviewed script, appropriate licensing and operator consent for any license-server connections.

## Acceptance state

Public CI uses **synthetic mock processes** with a fake `vsim` name, writing JUnit to the supplied path. It exercises success, fail, missing/stale, incomplete and tampered cases on Windows/Linux. **Live Questa/ModelSim, licenses, external assertions and a complete regression PASS remain NOT_RUN.** Version- and edition-specific cocotb behavior requires separate acceptance.

References: [cocotb JUnit](https://docs.cocotb.org/en/stable/junit.html), [format reference](https://docs.cocotb.org/en/stable/junit_reference.html), and [results checker](https://docs.cocotb.org/en/stable/_modules/cocotb_tools/check_results.html).
