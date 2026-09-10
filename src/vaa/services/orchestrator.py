from __future__ import annotations

import hashlib
import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from vaa.config import Settings
from vaa.enums import (
    ApprovalDecision,
    FailureMode,
    RequestedAction,
    RiskLane,
    TaskState,
)
from vaa.errors import InvalidStateError, NotFoundError, PolicyViolationError
from vaa.models import (
    Approval,
    AuditEvent,
    EvidenceRecord,
    ExternalTicket,
    Project,
    Task,
    User,
)
from vaa.schemas import (
    ActionPreview,
    ActionReceipt,
    AnalysisResult,
    ApprovalRequest,
    EvidenceClaim,
    TaskContract,
    TaskCreate,
    TaskRead,
    VerificationResult,
)
from vaa.services.analyzer import get_analyzer
from vaa.services.audit import record_event
from vaa.services.policy import require_approval, require_read
from vaa.services.retrieval import retrieve_documents
from vaa.services.router import build_contract, choose_lane
from vaa.services.tool_gateway import execute_jira_ticket
from vaa.services.verifier import verify_analysis
from vaa.tools.fake_jira import FakeJira


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _idempotency_key(
    *,
    tenant_id: str,
    project_id: str,
    tool_name: str,
    title: str,
    body: str,
) -> str:
    raw = "|".join(
        [
            tenant_id,
            project_id,
            tool_name,
            _normalise_text(title),
            _normalise_text(body),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _transition(
    session: Session,
    task: Task,
    state: TaskState,
    *,
    actor_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    previous = task.state
    task.state = state.value
    record_event(
        session,
        task_id=task.id,
        event_type="STATE_TRANSITION",
        actor_id=actor_id,
        payload={"from": previous, "to": state.value, **(payload or {})},
    )
    session.commit()


class Orchestrator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.analyzer = get_analyzer(settings)

    def create_task(self, session: Session, request: TaskCreate) -> Task:
        membership = require_read(session, request.user_id, request.project_id)
        # Fetch through the already validated user/project relationship.
        user = session.get(User, request.user_id)
        project = session.get(Project, request.project_id)
        assert user is not None and project is not None

        lane = choose_lane(request.goal, request.requested_action)
        if lane == RiskLane.ACTION_CONTROLLED and not membership.can_write:
            raise PolicyViolationError("The requesting user cannot perform project writes")

        task_id = f"task-{uuid4().hex[:12]}"
        contract = build_contract(
            task_id=task_id,
            goal=request.goal,
            lane=lane,
            tenant_id=user.tenant_id,
            project_id=project.id,
        )
        task = Task(
            id=task_id,
            tenant_id=user.tenant_id,
            project_id=project.id,
            user_id=user.id,
            goal=request.goal,
            requested_action=request.requested_action.value,
            failure_mode=request.failure_mode.value,
            lane=lane.value,
            state=TaskState.RECEIVED.value,
            contract_json=contract.model_dump(mode="json"),
        )
        session.add(task)
        record_event(
            session,
            task_id=task.id,
            event_type="TASK_RECEIVED",
            actor_id=user.id,
            payload={"lane": lane.value, "requested_action": request.requested_action.value},
        )
        session.commit()

        try:
            _transition(session, task, TaskState.CONTRACT_CREATED)

            _transition(session, task, TaskState.GATHERING)
            documents = retrieve_documents(
                session,
                tenant_id=task.tenant_id,
                project_id=task.project_id,
                query=task.goal,
            )
            document_ids = [document.id for document in documents]
            security_signals = sorted(
                {signal for document in documents for signal in document.security_signals}
            )
            record_event(
                session,
                task_id=task.id,
                event_type="DOCUMENTS_RETRIEVED",
                payload={"document_ids": document_ids, "count": len(document_ids)},
            )
            if security_signals:
                record_event(
                    session,
                    task_id=task.id,
                    event_type="PROMPT_INJECTION_SIGNAL_DETECTED",
                    payload={"signals": security_signals},
                )
            session.commit()

            _transition(session, task, TaskState.VERIFYING)
            analysis = self.analyzer.analyze(task.goal, documents)
            verification = verify_analysis(
                contract=contract,
                analysis=analysis,
                documents=documents,
            )
            task.analysis_json = analysis.model_dump(mode="json")
            task.verification_json = verification.model_dump(mode="json")
            for claim in analysis.claims:
                session.add(
                    EvidenceRecord(
                        task_id=task.id,
                        claim_key=claim.claim_key,
                        claim_text=claim.claim_text,
                        status=claim.status.value,
                        observed_values_json=claim.observed_values,
                        sources_json=[
                            source.model_dump(mode="json") for source in claim.sources
                        ],
                        conflicts_json=claim.conflicts,
                    )
                )
            session.commit()
            if not verification.passed:
                task.error_message = "Deterministic verification failed"
                _transition(
                    session,
                    task,
                    TaskState.FAILED,
                    payload={"checks": verification.checks},
                )
                return task

            if request.requested_action == RequestedAction.CREATE_JIRA_TICKET:
                key = _idempotency_key(
                    tenant_id=task.tenant_id,
                    project_id=task.project_id,
                    tool_name="jira.create_ticket",
                    title=analysis.rfi_subject,
                    body=analysis.rfi_draft,
                )
                preview = ActionPreview(
                    tool_name="jira.create_ticket",
                    title=analysis.rfi_subject,
                    body=analysis.rfi_draft,
                    project_id=task.project_id,
                    idempotency_key=key,
                )
                task.action_preview_json = preview.model_dump(mode="json")

            _transition(
                session,
                task,
                TaskState.PROPOSAL_READY,
                payload={"claim_count": len(analysis.claims)},
            )
            if request.requested_action == RequestedAction.NONE:
                _transition(session, task, TaskState.COMPLETED)
            else:
                _transition(session, task, TaskState.APPROVAL_PENDING)
            return task
        except Exception as exc:
            session.rollback()
            task = session.get(Task, task_id)
            if task is not None and task.state != TaskState.FAILED.value:
                task.error_message = str(exc)
                task.state = TaskState.FAILED.value
                record_event(
                    session,
                    task_id=task.id,
                    event_type="TASK_FAILED",
                    payload={"error_type": type(exc).__name__, "message": str(exc)},
                )
                session.commit()
            raise

    def approve_task(
        self,
        session: Session,
        task_id: str,
        request: ApprovalRequest,
    ) -> Task:
        task = self._get_task(session, task_id)
        if task.state == TaskState.COMPLETED.value:
            return task
        if task.state != TaskState.APPROVAL_PENDING.value:
            raise InvalidStateError(f"Task cannot be approved from state {task.state}")
        require_approval(session, request.actor_id, task.project_id)

        approval = Approval(
            task_id=task.id,
            decision=ApprovalDecision.APPROVED.value,
            actor_id=request.actor_id,
            comment=request.comment,
        )
        session.add(approval)

        record_event(
            session,
            task_id=task.id,
            event_type="ACTION_APPROVED",
            actor_id=request.actor_id,
            payload={"comment": request.comment},
        )
        session.commit()
        _transition(session, task, TaskState.APPROVED, actor_id=request.actor_id)

        if task.failure_mode == FailureMode.PAUSE_AFTER_APPROVAL.value:
            record_event(
                session,
                task_id=task.id,
                event_type="WORKER_PAUSED_AFTER_APPROVAL",
                payload={"resume_endpoint": f"/api/tasks/{task.id}/resume"},
            )
            session.commit()
            return task
        return self._execute_action(session, task)

    def reject_task(
        self,
        session: Session,
        task_id: str,
        request: ApprovalRequest,
    ) -> Task:
        task = self._get_task(session, task_id)
        if task.state != TaskState.APPROVAL_PENDING.value:
            raise InvalidStateError(f"Task cannot be rejected from state {task.state}")
        require_approval(session, request.actor_id, task.project_id)
        approval = Approval(
            task_id=task.id,
            decision=ApprovalDecision.REJECTED.value,
            actor_id=request.actor_id,
            comment=request.comment,
        )
        session.add(approval)
        record_event(
            session,
            task_id=task.id,
            event_type="ACTION_REJECTED",
            actor_id=request.actor_id,
            payload={"comment": request.comment},
        )
        session.commit()
        _transition(session, task, TaskState.REJECTED, actor_id=request.actor_id)
        return task

    def resume_task(
        self,
        session: Session,
        task_id: str,
        request: ApprovalRequest,
    ) -> Task:
        task = self._get_task(session, task_id)
        if task.state == TaskState.COMPLETED.value:
            return task
        if task.state != TaskState.APPROVED.value:
            raise InvalidStateError(f"Task cannot be resumed from state {task.state}")
        require_approval(session, request.actor_id, task.project_id)
        record_event(
            session,
            task_id=task.id,
            event_type="WORKFLOW_RESUMED",
            actor_id=request.actor_id,
        )
        session.commit()
        return self._execute_action(session, task)

    def _execute_action(self, session: Session, task: Task) -> Task:
        contract = TaskContract.model_validate(task.contract_json)

        if task.action_preview_json is None:
            raise InvalidStateError("Task has no action preview")
        preview = ActionPreview.model_validate(task.action_preview_json)
        _transition(session, task, TaskState.EXECUTING)
        receipt = execute_jira_ticket(
            session,
            task=task,
            contract=contract,
            preview=preview,
        )

        confirmed_ticket = FakeJira.find_by_idempotency_key(
            session, preview.idempotency_key
        )
        if confirmed_ticket is None or confirmed_ticket.ticket_key != receipt.ticket_key:
            raise InvalidStateError("Postcondition check could not confirm the external ticket")

        task.receipt_json = receipt.model_dump(mode="json")
        record_event(
            session,
            task_id=task.id,
            event_type="POSTCONDITION_CONFIRMED",
            payload={"ticket_key": receipt.ticket_key},
        )
        session.commit()
        _transition(
            session,
            task,
            TaskState.COMPLETED,
            payload={"ticket_key": receipt.ticket_key},
        )
        return task

    @staticmethod
    def _get_task(session: Session, task_id: str) -> Task:
        task = session.get(Task, task_id)
        if task is None:
            raise NotFoundError(f"Unknown task: {task_id}")
        return task


def task_to_read(session: Session, task: Task) -> TaskRead:
    evidence_rows = session.scalars(
        select(EvidenceRecord)
        .where(EvidenceRecord.task_id == task.id)
        .order_by(EvidenceRecord.id)
    ).all()
    evidence = [
        EvidenceClaim(
            claim_key=row.claim_key,
            claim_text=row.claim_text,
            status=row.status,
            observed_values=row.observed_values_json,
            sources=row.sources_json,
            conflicts=row.conflicts_json,
        )
        for row in evidence_rows
    ]
    audit_rows = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.task_id == task.id)
        .order_by(AuditEvent.id)
    ).all()
    audit = [
        {
            "id": row.id,
            "event_type": row.event_type,
            "actor_id": row.actor_id,
            "payload": row.payload_json,
            "created_at": row.created_at.isoformat(),
        }
        for row in audit_rows
    ]

    return TaskRead(
        id=task.id,
        tenant_id=task.tenant_id,
        project_id=task.project_id,
        user_id=task.user_id,
        goal=task.goal,
        requested_action=task.requested_action,
        failure_mode=task.failure_mode,
        lane=task.lane,
        state=task.state,
        contract=TaskContract.model_validate(task.contract_json),
        analysis=(
            AnalysisResult.model_validate(task.analysis_json)
            if task.analysis_json is not None
            else None
        ),
        verification=(
            VerificationResult.model_validate(task.verification_json)
            if task.verification_json is not None
            else None
        ),
        evidence=evidence,
        action_preview=(
            ActionPreview.model_validate(task.action_preview_json)
            if task.action_preview_json is not None
            else None
        ),
        receipt=(
            ActionReceipt.model_validate(task.receipt_json)
            if task.receipt_json is not None
            else None
        ),
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        audit=audit,
    )


def list_tickets(session: Session) -> list[dict[str, object]]:
    rows = session.scalars(select(ExternalTicket).order_by(ExternalTicket.id)).all()
    return [
        {
            "ticket_key": row.ticket_key,
            "project_id": row.project_id,
            "title": row.title,
            "status": row.status,
            "idempotency_key": row.idempotency_key,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
