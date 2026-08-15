# Seven-minute reviewer demo

## 0:00–0:45 — Frame the problem

Open the dashboard and say:

> This assistant compares versioned project documents and can create an RFI ticket. The project
> is about the reliability boundary around the model: evidence, authorization, approval,
> idempotency, recovery, and evaluation.

Point out that the default analyzer is deterministic, so the reviewer does not need an API key.

## 0:45–2:00 — Happy path and evidence

Select **Happy path** and run it.

Show:

- lane is `ACTION_CONTROLLED` because a write was requested;
- task contract lists the only allowed tools and requires approval;
- evidence ledger surfaces 24 vs 20 workstations and 1.5 m vs 1.2 m aisle width;
- each value links to a document ID, version, section, and excerpt;
- task stops at `APPROVAL_PENDING`.

Approve the action. Show the confirmed ticket receipt and the full audit trail.

## 2:00–3:10 — Prompt injection

Reset, select **Malicious document**, and run it.

Explain that the vendor attachment contains a fake system instruction asking the assistant to
search payroll data and email it externally. Show:

- security signal in the analysis and audit;
- the malicious line was removed before analysis;
- the task contract never included payroll or email tools;
- no attacker address appears in the output.

The important claim is not that pattern matching solves prompt injection. The important claim is
that untrusted content cannot increase authorization or tool scope.

## 3:10–4:30 — Timeout after success

Reset, select **Timeout after success**, run, and approve.

Show:

- Jira created the ticket before the simulated response timed out;
- workflow entered `RECONCILING`;
- gateway looked up the same idempotency key;
- receipt says `reconciled_after_timeout=true`;
- the ticket list contains exactly one ticket.

## 4:30–5:30 — Durable pause and resume

Reset, select **Pause and resume**, run, and approve.

The task remains `APPROVED`. Explain that approval is persisted rather than held in an in-memory
model loop. Click **Resume workflow** and show completion.

For a stronger live demo, stop and restart the server while the task is paused, then call the
resume endpoint using the persisted task ID.

## 5:30–6:15 — Isolation and tests

Run:

```bash
pytest
python -m evals.run_evals
```

Point out the cross-tenant denial case, rejection case, and eight deterministic regression cases.

## 6:15–7:00 — Honest production boundary

Close with:

> The local retriever and Jira integration are intentionally simple. In production I would swap
> in hybrid retrieval, a real identity provider, a hardened tool gateway, Postgres, a durable
> workflow engine, OpenTelemetry, and a larger adversarial eval suite. The interfaces are already
> separated for those upgrades.

This framing demonstrates engineering judgment rather than pretending a portfolio demo is a
finished enterprise platform.
