# Verifiable Action Assistant

**A policy-governed, evidence-grounded, and recoverable DesignOps agent.**

This repository is a runnable portfolio project for demonstrating production-minded agent
engineering. It does more than generate an answer: it selects a risk lane, creates a typed
task contract, retrieves only authorized document versions, builds an evidence ledger,
requires human approval before a write, executes the side effect idempotently, verifies the
postcondition, and records an audit trail.

The default mode is deterministic and requires **no API key**, so reviewers can reproduce the
same behavior locally, in CI, or in Docker. An optional OpenAI Structured Outputs adapter is
included for model-backed analysis.

![Verifiable Action Assistant demo dashboard](docs/demo-dashboard.png)

## What this project demonstrates

- **Three risk lanes:** `READ_FAST`, `RESEARCH_VERIFIED`, and `ACTION_CONTROLLED`.
- **Typed task contracts:** scope, tools, evidence requirements, approval policy, and budgets.
- **Evidence provenance:** every extracted claim maps to versioned project documents.
- **Conflict detection:** incompatible document values are surfaced rather than silently merged.
- **Application-layer authorization:** tenant, project, read, write, and approval checks do not
  depend on model behavior.
- **Prompt-injection containment:** retrieved files are treated as untrusted data and suspicious
  instruction-like lines are removed before analysis.
- **Human-in-the-loop execution:** no external write is allowed before an authorized approval.
- **Idempotency and reconciliation:** a timeout after a successful write does not create a
  duplicate ticket.
- **Recoverable state:** an approved workflow can pause, survive process boundaries, and resume.
- **Regression evaluations:** deterministic cases cover routing, evidence, approval, isolation,
  prompt injection, timeout recovery, and resume behavior.

## Run it locally

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

### 2. Start the app

```bash
vaa serve --reload
```

Open `http://127.0.0.1:8000`.

The app seeds fake users, projects, approved document versions, one malicious external
attachment, and a separate tenant. The web UI includes five ready-to-run scenarios.

### 3. Run tests and regression evaluations

```bash
make test
make eval
make lint
```

Expected regression score:

```text
Score: 8/8 (100%)
```

## Run with Docker

SQLite demo:

```bash
docker compose up --build
```

PostgreSQL demo:

```bash
docker compose -f docker-compose.postgres.yml up --build
```

Both expose the app at `http://127.0.0.1:8000`.

## Demo scenarios

| Scenario | Reliability question being tested | Expected result |
|---|---|---|
| Happy path | Can the assistant detect conflicting requirements and stop at an approval boundary? | `APPROVAL_PENDING`, then one confirmed ticket after approval |
| Malicious document | Can an external attachment change system instructions or exfiltrate data? | Security signal logged; malicious text is not echoed or executed |
| Timeout after success | What happens when Jira creates a ticket but the response times out? | Reconciliation finds the existing ticket; no duplicate write |
| Pause and resume | Can a workflow wait after approval and continue later? | Persisted `APPROVED` state resumes to `COMPLETED` |
| Research only | Can the system produce source-backed analysis without side effects? | `RESEARCH_VERIFIED` lane; no ticket created |

A seven-minute reviewer walkthrough is available in
[`docs/demo-script.md`](docs/demo-script.md).

## Architecture

```mermaid
flowchart TD
    U[Web / API Client] --> A[Authentication + Project ACL]
    A --> R[Risk Router]
    R --> C[Typed Task Contract]
    C --> W[Persisted Workflow State Machine]

    W --> D[Authorized Retrieval]
    D --> S[Untrusted Content Scanner]
    S --> N[Deterministic or OpenAI Analyzer]
    N --> E[Evidence Ledger]
    E --> V[Deterministic Verification Gate]

    V -->|read-only| O[Source-backed Result]
    V -->|write proposed| H[Human Approval]
    H -->|rejected| X[No Side Effect]
    H -->|approved| G[Policy-enforced Tool Gateway]
    G --> J[Idempotent Jira Simulator]
    J --> P[Postcondition Check / Reconciliation]
    P --> Q[Receipt + Audit Timeline]
```

The orchestration state machine is:

```text
RECEIVED
  → CONTRACT_CREATED
  → GATHERING
  → VERIFYING
  → PROPOSAL_READY
  → APPROVAL_PENDING
  → APPROVED
  → EXECUTING
  → CONFIRMING
  → COMPLETED

Exceptional paths: REJECTED, RECONCILING, FAILED
```

See [`docs/architecture.md`](docs/architecture.md) for component boundaries, data flow, and
sequence diagrams.

## Reliability controls

| Failure mode | Control in this repository | Proof |
|---|---|---|
| Model chooses an unauthorized tool | Allowed tools are part of `TaskContract`; gateway enforces them in Python | `test_approval.py`, policy checks |
| User accesses another tenant | Tenant and membership checks precede retrieval | `cross-tenant-denied` eval |
| Old document overrides latest policy | Retrieval selects the latest approved version per document type | seeded `brief-v3` vs `brief-v4` |
| Retrieved PDF contains instructions | Content is scanned and instruction-like lines are replaced | `test_security.py` |
| Claim cites a nonexistent source | Deterministic verifier validates every source ID | verification gate |
| Write occurs without consent | Approval permission and workflow state are checked before tool execution | `test_approval.py` |
| API times out after creating a ticket | Stable idempotency key plus lookup-based reconciliation | `test_idempotency.py` |
| Worker pauses or restarts | Task state and approval are persisted in the database | `test_recovery.py` |
| Prompt or code change regresses behavior | Unit tests plus an eight-case eval suite run in CI | `.github/workflows/ci.yml` |

## API example

Create an action-controlled task:

```bash
curl -s http://127.0.0.1:8000/api/tasks \
  -H 'content-type: application/json' \
  -d '{
    "user_id": "alice",
    "project_id": "P-1024",
    "goal": "Compare the latest Client Brief and Design Specification and draft an RFI.",
    "requested_action": "create_jira_ticket",
    "failure_mode": "none"
  }'
```

Approve it using the returned task ID:

```bash
curl -s -X POST http://127.0.0.1:8000/api/tasks/<TASK_ID>/approve \
  -H 'content-type: application/json' \
  -d '{"actor_id":"alice","comment":"Reviewed and approved"}'
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Optional OpenAI mode

The repository runs in deterministic `mock` mode by default. To use the included Structured
Outputs analyzer:

```bash
python -m pip install -e ".[openai]"
export OPENAI_API_KEY="..."
export VAA_LLM_PROVIDER="openai"
export VAA_OPENAI_MODEL="gpt-5.6"
vaa serve
```

The model is limited to structured document analysis. Authorization, approval, tool policy,
idempotency, and postcondition verification remain ordinary application code.

## Repository map

```text
src/vaa/
├── api/                 # Task and demo endpoints
├── services/
│   ├── analyzer.py      # Deterministic baseline + optional Structured Outputs adapter
│   ├── orchestrator.py  # Persisted workflow transitions
│   ├── policy.py        # Tenant, project, write, approval, and tool checks
│   ├── retrieval.py     # Latest-approved retrieval with provenance
│   ├── security.py      # Untrusted-content scanning
│   ├── tool_gateway.py  # Side-effect boundary and reconciliation
│   └── verifier.py      # Deterministic evidence and policy checks
├── tools/fake_jira.py   # Database-backed idempotent tool simulator
└── web/                 # Zero-build demo dashboard

tests/                   # Focused behavioral tests
evals/                   # Portfolio regression dataset and grader
docs/                    # Architecture, threat model, runbook, demo, postmortem
scripts/                 # Headless demo and smoke test
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VAA_DATABASE_URL` | `sqlite:///./data/vaa.db` | SQLite or PostgreSQL SQLAlchemy URL |
| `VAA_LLM_PROVIDER` | `mock` | `mock` or `openai` |
| `VAA_OPENAI_MODEL` | `gpt-5.6` | Model used by the optional analyzer |
| `VAA_AUTO_SEED` | `true` | Seed safe demo data on startup |
| `VAA_DEMO_MODE` | `true` | Permit the demo reset endpoint |
| `VAA_LOG_LEVEL` | `INFO` | Application log level |

## Honest scope and production upgrades

This is a **reference implementation**, not a claim of production certification. The local
retriever is lexical, the Jira integration is simulated, and the prompt-injection scanner is a
small defensive layer rather than a complete security solution. The code intentionally makes
those boundaries visible instead of hiding them behind framework abstractions.

A production deployment would add a real identity provider, row-level database policies,
object storage, hybrid retrieval, a hardened MCP or API gateway, secret management, OpenTelemetry,
a durable workflow engine, rate limits, data retention controls, and broader adversarial evals.
The migration plan is documented in
[`docs/production-upgrades.md`](docs/production-upgrades.md).

## Suggested portfolio statement

> Built a policy-governed DesignOps agent with version-aware evidence retrieval, typed task
> contracts, human approval, idempotent side-effect execution, timeout reconciliation, durable
> resume, and regression evaluations. Demonstrated zero duplicate writes across injected timeout
> tests and blocked cross-tenant access in the provided adversarial suite.

## Documentation

- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Operational runbook](docs/runbook.md)
- [Sample incident postmortem](docs/postmortem.md)
- [Reviewer demo script](docs/demo-script.md)
- [Production upgrade path](docs/production-upgrades.md)
- [Validation report](docs/validation.md)
- [学员学习指南](docs/learner-guide.zh-CN.md)
- [完整项目任务书（Notion 版）](docs/project-brief.zh-CN.md)

## License

MIT. The demo contains only synthetic users, projects, documents, and tickets.
