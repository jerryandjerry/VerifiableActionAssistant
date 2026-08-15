from __future__ import annotations

from enum import StrEnum


class RiskLane(StrEnum):
    READ_FAST = "READ_FAST"
    RESEARCH_VERIFIED = "RESEARCH_VERIFIED"
    ACTION_CONTROLLED = "ACTION_CONTROLLED"


class TaskState(StrEnum):
    RECEIVED = "RECEIVED"
    CONTRACT_CREATED = "CONTRACT_CREATED"
    GATHERING = "GATHERING"
    VERIFYING = "VERIFYING"
    PROPOSAL_READY = "PROPOSAL_READY"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    RECONCILING = "RECONCILING"
    CONFIRMING = "CONFIRMING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class EvidenceStatus(StrEnum):
    SUPPORTED = "supported"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class FailureMode(StrEnum):
    NONE = "none"
    TIMEOUT_AFTER_SUCCESS = "timeout_after_success"
    PAUSE_AFTER_APPROVAL = "pause_after_approval"


class RequestedAction(StrEnum):
    NONE = "none"
    CREATE_JIRA_TICKET = "create_jira_ticket"
