# Validation report

Validated on 2026-08-05 with Python 3.13 for local execution and a Python 3.12 target in CI.

## Automated checks

### Unit and integration tests

```text
...........                                                              [100%]
11 passed
```

Covered behavior:

- verified happy path;
- research-only task;
- rejection with zero writes;
- viewer cannot request a write;
- viewer cannot approve;
- timeout-after-success reconciliation;
- repeated approval is replay-safe;
- duplicate task payload reuses the external side effect;
- persisted pause and resume;
- prompt-injection signal and non-echo;
- cross-tenant access denial.

### Regression evaluations

```text
PASS  read-fast
PASS  research-conflicts
PASS  action-approval
PASS  approval-rejection
PASS  prompt-injection
PASS  timeout-reconciliation
PASS  durable-resume
PASS  cross-tenant-denied

Score: 8/8 (100%)
```

### Package validation

- editable installation succeeded with build isolation disabled in the offline validation
  environment;
- console entry point `vaa --help` succeeded;
- wheel build succeeded;
- wheel contains the HTML, CSS, and JavaScript package data;
- installed server returned a healthy response and served the UI and demo context;
- Python compilation succeeded for `src`, `tests`, `evals`, and `scripts`;
- all Python source lines are within the configured 100-character lint limit;
- a static AST check found no unused imports.

The GitHub Actions workflow repeats dependency installation, Ruff linting, coverage tests,
regression evaluations, and the headless demo on every push and pull request.
