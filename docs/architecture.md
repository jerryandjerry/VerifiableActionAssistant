# Architecture

## 1. Design goal

The assistant must answer a project question and, when requested, create an external ticket.
The difficult part is not text generation. The difficult part is preserving system invariants
when evidence conflicts, permissions differ, retrieved files contain hostile instructions, a
human rejects the action, or a tool succeeds but its response is lost.

The reference implementation therefore separates probabilistic analysis from deterministic
control.

## 2. Trust boundaries

```mermaid
flowchart LR
    subgraph Trusted application boundary
      API[FastAPI API]
      ACL[Policy and ACL checks]
      WF[Persisted workflow]
      VER[Deterministic verifier]
      GW[Tool gateway]
      DB[(SQL database)]
    end

    USER[Authenticated user input] --> API
    DOCS[Retrieved documents\nuntrusted content] --> ACL
    ACL --> WF
    WF --> VER
    VER --> GW
    GW --> EXT[External tools\nuntrusted availability]
    API <--> DB
    WF <--> DB
    GW <--> DB
```

The model is not a security boundary. It may analyze only the data supplied to it and returns a
validated schema. It cannot grant itself access, alter the task contract, approve an action, or
write directly to the external system.

## 3. Components

### API layer

`src/vaa/api/` exposes task creation, inspection, approval, rejection, resume, demo reset, and
fake-ticket inspection. Domain errors are converted to explicit HTTP responses.

### Risk router

`services/router.py` selects one of three lanes:

- `READ_FAST`: low-risk, read-only lookup.
- `RESEARCH_VERIFIED`: evidence-heavy comparison or review.
- `ACTION_CONTROLLED`: any task requesting a write.

The router also creates `TaskContract`, which records allowed tools, evidence requirements,
approval policy, budgets, tenant, project, and success criteria.

### Policy layer

`services/policy.py` enforces:

1. user and project exist;
2. user and project share a tenant;
3. the user has project membership;
4. read, write, and approve capabilities are checked separately;
5. a tool is listed in the task contract;
6. a write occurs only from an approved workflow state.

### Retrieval and provenance

`services/retrieval.py` selects the latest approved document per document type inside the
already-authorized tenant and project. It returns typed records containing source ID, title,
version, trust level, approval time, sanitized content, security signals, and a simple relevance
score.

The lexical retriever is deliberately small and inspectable. It can later be replaced by hybrid
search without changing the policy or evidence interfaces.

### Untrusted-content scanner

`services/security.py` identifies a compact set of instruction-override, exfiltration,
system-prompt, and concealment patterns. Matching lines are replaced before they reach either
analyzer. Signals are preserved in the task audit.

This is defense in depth, not a complete prompt-injection solution. The main protection is that
retrieved data cannot expand permissions or tool scope.

### Analyzer

`services/analyzer.py` has two adapters:

- `DeterministicAnalyzer`: reproducible extraction of workstation counts, aisle widths,
  handover dates, and acoustic NRC values.
- `OpenAIAnalyzer`: optional Structured Outputs analysis using the same `AnalysisResult`
  boundary.

Both return claims, observed values, source references, conflicts, an RFI draft, and security
signals. Neither can perform a side effect.

### Verification gate

`services/verifier.py` checks:

- every cited source was actually retrieved;
- every claim has a source;
- conflict labels agree with the observed value cardinality;
- malicious instructions were not echoed into the proposal;
- required evidence exists;
- the contract contains the correct write policy.

A failed gate transitions the task to `FAILED` before approval or execution.

### Orchestrator

`services/orchestrator.py` persists every state transition and coordinates retrieval, analysis,
verification, approval, execution, reconciliation, and completion. The state lives in SQL rather
than an in-memory model loop.

```mermaid
stateDiagram-v2
    [*] --> RECEIVED
    RECEIVED --> CONTRACT_CREATED
    CONTRACT_CREATED --> GATHERING
    GATHERING --> VERIFYING
    VERIFYING --> PROPOSAL_READY: verification passed
    VERIFYING --> FAILED: verification failed
    PROPOSAL_READY --> COMPLETED: read-only task
    PROPOSAL_READY --> APPROVAL_PENDING: write proposed
    APPROVAL_PENDING --> REJECTED: rejected
    APPROVAL_PENDING --> APPROVED: approved
    APPROVED --> EXECUTING: immediate or resumed
    EXECUTING --> RECONCILING: timeout / unknown result
    EXECUTING --> CONFIRMING: tool returned
    RECONCILING --> CONFIRMING: side effect found
    CONFIRMING --> COMPLETED: postcondition confirmed
```

### Tool gateway

`services/tool_gateway.py` is the only path to the write-capable tool. It rechecks contract and
write permission, records an execution attempt, sends a stable idempotency key, handles an
unknown timeout result, reconciles against external state, and returns a typed receipt.

### Fake Jira

`tools/fake_jira.py` simulates an external API while preserving the important behavior: the
write is stored before a timeout can be injected. A unique idempotency key makes repeated calls
return the existing ticket instead of creating another visible side effect.

## 4. Happy-path sequence

```mermaid
sequenceDiagram
    actor User
    participant API
    participant Policy
    participant Retrieval
    participant Analyzer
    participant Verifier
    participant DB
    participant Gateway
    participant Jira

    User->>API: Create task
    API->>Policy: Check tenant + read/write membership
    Policy-->>API: Allowed
    API->>DB: Persist task + contract
    API->>Retrieval: Fetch current authorized documents
    Retrieval-->>Analyzer: Sanitized documents + provenance
    Analyzer-->>Verifier: Structured claims + RFI draft
    Verifier-->>API: Passed
    API->>DB: Persist evidence + APPROVAL_PENDING
    API-->>User: Preview and evidence
    User->>API: Approve
    API->>Policy: Check approval capability
    API->>Gateway: Execute approved preview
    Gateway->>Jira: Create with idempotency key
    Jira-->>Gateway: Ticket result
    Gateway->>DB: Persist receipt and audit
    API-->>User: COMPLETED + confirmed receipt
```

## 5. Timeout-after-success sequence

```mermaid
sequenceDiagram
    participant Gateway
    participant Jira
    participant DB

    Gateway->>DB: Execution attempt STARTED
    Gateway->>Jira: Create ticket with idempotency key
    Jira->>DB: Persist external ticket
    Jira--xGateway: Response times out
    Gateway->>DB: Mark TIMEOUT_UNKNOWN + RECONCILING
    Gateway->>Jira: Lookup by idempotency key
    Jira-->>Gateway: Existing ticket RFI-0001
    Gateway->>DB: Mark RECONCILED + confirmed receipt
```

The system does not blindly retry an unknown write. It first asks whether the side effect is
already visible.

## 6. Data model

Key tables:

- `users`, `projects`, `project_memberships`: authorization context.
- `documents`: versioned source material and trust level.
- `tasks`: contract, state, analysis, verification, preview, receipt, and error.
- `evidence_records`: claim-level provenance.
- `approvals`: one decision per task.
- `external_tickets`: simulated external state, uniquely keyed by idempotency key.
- `execution_attempts`: tool request, status, response, and error.
- `audit_events`: actor, event type, payload, and timestamp.

## 7. Extension points

Each important boundary has a stable interface:

- replace lexical retrieval with hybrid retrieval;
- replace fake Jira with a typed Jira or MCP adapter;
- replace SQL state transitions with Temporal, DBOS, or another durable engine;
- export audit and span data through OpenTelemetry;
- add policy-as-code without exposing decisions to the model;
- add new domain extractors while preserving `AnalysisResult` and `VerificationResult`.
