from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from vaa.enums import EvidenceStatus, FailureMode, RequestedAction, RiskLane, TaskState


class Budgets(BaseModel):
    max_tool_calls: int = 20
    max_runtime_seconds: int = 180
    max_cost_usd: float = 1.50


class TaskContract(BaseModel):
    task_id: str
    goal: str
    lane: RiskLane
    tenant_id: str
    project_id: str
    allowed_tools: list[str]
    required_evidence: bool
    approval_policy: Literal["none", "before_any_write"]
    budgets: Budgets
    success_criteria: list[str]


class SourceRef(BaseModel):
    document_id: str
    title: str
    version: int
    section: str
    excerpt: str
    trust_level: str


class EvidenceClaim(BaseModel):
    claim_key: str
    claim_text: str
    status: EvidenceStatus
    observed_values: list[str | float | int]
    sources: list[SourceRef]
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    summary: str
    key_findings: list[str]
    claims: list[EvidenceClaim]
    rfi_subject: str
    rfi_draft: str
    detected_security_signals: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    passed: bool
    checks: dict[str, bool]
    warnings: list[str] = Field(default_factory=list)


class ActionPreview(BaseModel):
    tool_name: str
    title: str
    body: str
    project_id: str
    requires_approval: bool = True
    idempotency_key: str


class ActionReceipt(BaseModel):
    task_id: str
    tool_name: str
    ticket_key: str
    external_status: str
    idempotency_key: str
    confirmed: bool
    reconciled_after_timeout: bool = False
    replayed: bool = False


class TaskCreate(BaseModel):
    user_id: str = "alice"
    project_id: str = "P-1024"
    goal: str = (
        "Compare the latest client brief, design specification, and meeting notes; "
        "identify conflicts and draft an RFI."
    )
    requested_action: RequestedAction = RequestedAction.CREATE_JIRA_TICKET
    failure_mode: FailureMode = FailureMode.NONE


class ApprovalRequest(BaseModel):
    actor_id: str = "alice"
    comment: str | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    project_id: str
    user_id: str
    goal: str
    requested_action: RequestedAction
    failure_mode: FailureMode
    lane: RiskLane
    state: TaskState
    contract: TaskContract
    analysis: AnalysisResult | None
    verification: VerificationResult | None
    evidence: list[EvidenceClaim]
    action_preview: ActionPreview | None
    receipt: ActionReceipt | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    audit: list[dict[str, Any]] = Field(default_factory=list)


class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"
    llm_provider: str
    database: str


class DemoContext(BaseModel):
    users: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    presets: list[dict[str, Any]]
