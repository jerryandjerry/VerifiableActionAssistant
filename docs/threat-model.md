# Threat model

## Scope

This threat model covers the reference application's document-analysis and ticket-creation
workflow. It focuses on authorization, untrusted retrieved content, unsafe side effects,
duplicate execution, and auditability.

## Assets

- private project documents;
- tenant and project boundaries;
- approval authority;
- external-system write capability;
- source provenance and document versions;
- task history and audit records;
- API credentials in a production deployment.

## Actors

- authorized project lead;
- read-only project viewer;
- user from another tenant;
- malicious document author;
- compromised or unreliable external tool;
- fallible model or analyzer;
- operator debugging an incident.

## Security invariants

1. A user cannot retrieve a project outside their tenant or membership.
2. Read permission does not imply write or approval permission.
3. Retrieved content cannot add tools, change scope, or approve an action.
4. No write occurs without an explicit authorized approval.
5. Retrying an unknown write cannot create a duplicate visible side effect.
6. Every material claim in a verified research task maps to a retrieved source.
7. Every state transition and tool attempt is auditable.

## Threats and controls

| Threat | Example | Implemented control | Residual risk |
|---|---|---|---|
| Cross-tenant data access | Mallory requests project `P-1024` | tenant equality and membership checks before retrieval | production systems also need identity verification and database row policies |
| Privilege escalation | Viewer asks to create a ticket | separate read/write/approve flags | compromised admin accounts remain dangerous |
| Indirect prompt injection | Vendor PDF says to email payroll data | retrieved content marked untrusted, suspicious lines removed, tool list fixed by contract | obfuscated attacks can bypass pattern scans; tool isolation remains essential |
| Tool-scope expansion | Model invents `email.send` | gateway accepts only contract-listed tools | schema bugs or unsafe future tools can reintroduce risk |
| Unapproved side effect | Model calls Jira during planning | analyzer has no write interface; gateway checks approved state | application bugs require testing and review |
| Duplicate side effect | Jira succeeds, response times out, client retries | stable idempotency key and reconciliation lookup | real APIs may lack idempotency or consistent lookup semantics |
| False provenance | Model cites a document it never received | verifier checks source IDs against retrieved records | source text can still be misleading or stale |
| Silent conflict resolution | brief says 24 seats, spec says 20 | conflicts are represented explicitly in evidence ledger | domain-specific equivalence can require expert review |
| Sensitive data in logs | model or tool payload contains secrets | demo uses synthetic data; credentials are not passed to model | production logging needs redaction, retention, and access controls |
| Denial of service | oversized task or repeated tool calls | contract records budgets | current demo does not enforce every budget at runtime |

## Abuse cases exercised by tests

- unauthorized cross-tenant request returns HTTP 403;
- write proposal remains pending until approval;
- rejection creates zero tickets;
- malicious attachment produces security signals and no malicious output echo;
- timeout-after-success produces exactly one ticket and a reconciled receipt;
- pause-after-approval can resume from persisted state.

## Explicit non-goals

This repository does not claim:

- immunity to all prompt-injection techniques;
- cryptographic non-repudiation;
- hardened multi-region availability;
- compliance with a specific regulatory framework;
- safe handling of arbitrary code execution;
- complete enforcement of cost and time budgets;
- production identity, secret, or key management.

Those omissions are intentional and should be discussed in a technical interview rather than
hidden.
