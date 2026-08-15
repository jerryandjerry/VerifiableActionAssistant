# Production upgrade path

The repository is designed so that the teaching implementation can be upgraded component by
component without changing the core reliability invariants.

## Phase 1 — Harden the single-service deployment

- PostgreSQL with migrations and transactional tests;
- OIDC identity provider and short-lived sessions;
- row-level tenant policies in addition to application checks;
- object storage for original files and immutable source hashes;
- secret manager; no credential material in model context;
- rate limits, request-size limits, and enforced task budgets;
- structured logs with sensitive-field redaction;
- OpenTelemetry traces and service-level dashboards;
- deletion, retention, and export workflows.

## Phase 2 — Replace demo retrieval

- parse files into versioned sections with stable source IDs;
- combine lexical search, embeddings, and metadata filters;
- filter tenant, project, access level, status, and validity before ranking;
- store retrieval snapshots so a completed task remains reproducible;
- add source freshness, authority, and contradiction features;
- evaluate retrieval separately from answer generation.

Keep the current `RetrievedDocument` and `EvidenceClaim` boundaries so the verifier remains
independent of the retrieval backend.

## Phase 3 — Real tool gateway

- typed Jira, Linear, Slack, email-draft, or MCP adapters;
- separate read and write credentials and scopes;
- tool-level policy, schema validation, domain allowlists, and rate limits;
- provider-native idempotency where supported;
- reconciliation adapters for unknown outcomes;
- preview/diff before mutation;
- compensation only for actions that are truly reversible;
- immutable action receipts and external resource identifiers.

A model should never receive raw OAuth refresh tokens or decide its own scopes.

## Phase 4 — Durable orchestration

Move long-running tasks to Temporal, DBOS, Restate, or an equivalent workflow system when the
service needs multiple workers, timers, retries, or long approval waits.

Required semantics:

- activity retries only where replay is safe;
- idempotency key survives workflow retries;
- approval is an external signal, not a model-generated event;
- unknown write results route to reconciliation;
- workflow versioning supports deployments while runs are in flight;
- terminal state and receipts remain queryable from the product database.

## Phase 5 — Evaluation and release safety

Expand the current JSONL suite into:

- routing evals;
- retrieval recall and source-authority evals;
- claim-to-source entailment evals;
- approval and policy property tests;
- prompt-injection and exfiltration red-team cases;
- tool-selection and argument-validation evals;
- fault-injection tests for timeout, restart, stale reads, and partial dependency failure;
- cost and latency budgets by lane;
- shadow and canary comparison before model or prompt rollout.

A release should fail closed when policy invariants regress, even when average answer quality
improves.

## Phase 6 — Organization controls

- reviewed policy ownership and change management;
- per-tool risk classification;
- incident response and audit access roles;
- data-classification labels propagated through retrieval and tools;
- customer-specific retention and residency rules;
- regular adversarial exercises using realistic documents;
- human-review analytics to identify approval fatigue or rubber-stamping.

## Invariants that must survive every upgrade

1. authorization is evaluated outside the model;
2. retrieved content is data, never authority;
3. writes require explicit policy and approval;
4. unknown side-effect outcomes are reconciled, not blindly retried;
5. claims and actions have inspectable provenance;
6. model, prompt, tool, and policy changes pass regression gates.
