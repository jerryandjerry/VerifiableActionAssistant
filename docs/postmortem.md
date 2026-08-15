# Sample postmortem: duplicate RFI risk after an unknown Jira result

> This is a teaching postmortem for the failure injected by the demo. No real customer incident
> occurred.

## Summary

A ticket-creation request completed in the external system, but the response timed out before
the assistant received the ticket key. A naive retry would have created a second RFI. The
reference implementation instead entered `RECONCILING`, queried the external system by a stable
idempotency key, found the existing ticket, and returned a confirmed receipt.

## Impact

- User-visible duplicate tickets: **0**.
- External tickets created: **1**.
- Workflow delay: one reconciliation lookup.
- Data exposure: none.

## Timeline

1. Task reached `APPROVAL_PENDING` with a verified action preview.
2. Authorized user approved the write.
3. Gateway persisted an execution attempt with status `STARTED`.
4. Jira simulator committed ticket `RFI-0001`.
5. The simulated response timed out.
6. Gateway recorded `TIMEOUT_UNKNOWN` and moved the task to `RECONCILING`.
7. Gateway searched external state using the same idempotency key.
8. Existing ticket `RFI-0001` was found.
9. Gateway returned a receipt with `reconciled_after_timeout=true`.
10. Task reached `COMPLETED`.

## Root cause in a naive design

The common but unsafe assumption is:

```text
no response == no side effect
```

For write APIs, a missing response means the result is **unknown**, not failed. Retrying without
reconciliation can duplicate irreversible or costly actions.

## Controls that prevented impact

- deterministic idempotency key derived from tenant, project, tool, title, and normalized body;
- unique external record keyed by that idempotency key;
- execution-attempt record persisted before the call;
- explicit `RECONCILING` state;
- lookup before retry;
- postcondition receipt identifying the actual external ticket.

## Corrective and preventive actions

The reference implementation already includes the core fix. A production follow-up would add:

- provider-native idempotency keys where available;
- a reconciliation queue with bounded retries and alerting;
- explicit timeout classes distinguishing connect, read, and unknown-result failures;
- a manual operator path for providers without reliable lookup;
- metrics for unknown outcomes and reconciliation latency;
- chaos tests against the real integration sandbox.

## Lesson

Reliability is not achieved by asking the model to be careful. It is achieved by modeling
uncertain outcomes and making side effects replay-safe in ordinary application code.
