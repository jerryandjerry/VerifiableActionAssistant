from __future__ import annotations

from sqlalchemy.orm import Session

from vaa.enums import FailureMode, TaskState
from vaa.errors import ToolTimeoutAfterSuccess
from vaa.models import ExecutionAttempt, Task
from vaa.schemas import ActionPreview, ActionReceipt, TaskContract
from vaa.services.audit import record_event
from vaa.services.policy import enforce_tool_policy, require_write
from vaa.tools.fake_jira import FakeJira, TicketResult


def _receipt(
    *,
    task: Task,
    preview: ActionPreview,
    result: TicketResult,
    reconciled: bool,
) -> ActionReceipt:
    return ActionReceipt(
        task_id=task.id,
        tool_name=preview.tool_name,
        ticket_key=result.ticket_key,
        external_status=result.status,
        idempotency_key=result.idempotency_key,
        confirmed=True,
        reconciled_after_timeout=reconciled,
        replayed=result.replayed,
    )


def execute_jira_ticket(
    session: Session,
    *,
    task: Task,
    contract: TaskContract,
    preview: ActionPreview,
) -> ActionReceipt:
    enforce_tool_policy(task, contract, preview.tool_name)
    require_write(session, task.user_id, task.project_id)

    attempt = ExecutionAttempt(
        task_id=task.id,
        tool_name=preview.tool_name,
        idempotency_key=preview.idempotency_key,
        status="STARTED",
        request_json=preview.model_dump(mode="json"),
    )
    session.add(attempt)
    record_event(
        session,
        task_id=task.id,
        event_type="TOOL_CALL_STARTED",
        actor_id=task.user_id,
        payload={"tool": preview.tool_name, "idempotency_key": preview.idempotency_key},
    )
    session.commit()

    try:
        result = FakeJira.create_ticket(
            session,
            tenant_id=task.tenant_id,
            project_id=task.project_id,
            idempotency_key=preview.idempotency_key,
            title=preview.title,
            body=preview.body,
            simulate_timeout_after_success=(
                task.failure_mode == FailureMode.TIMEOUT_AFTER_SUCCESS.value
            ),
        )
    except ToolTimeoutAfterSuccess as exc:
        task.state = TaskState.RECONCILING.value
        attempt.status = "TIMEOUT_UNKNOWN"
        attempt.error = str(exc)
        record_event(
            session,
            task_id=task.id,
            event_type="TOOL_TIMEOUT_AFTER_POSSIBLE_SUCCESS",
            payload={"tool": preview.tool_name},
        )
        session.commit()

        existing = FakeJira.find_by_idempotency_key(session, preview.idempotency_key)
        if existing is None:
            attempt.status = "FAILED_UNCONFIRMED"
            session.commit()
            raise

        result = TicketResult(
            ticket_key=existing.ticket_key,
            status=existing.status,
            idempotency_key=existing.idempotency_key,
            replayed=True,
        )
        attempt.status = "RECONCILED"
        attempt.response_json = {
            "ticket_key": result.ticket_key,
            "status": result.status,
        }
        task.state = TaskState.CONFIRMING.value
        record_event(
            session,
            task_id=task.id,
            event_type="SIDE_EFFECT_RECONCILED",
            payload={"ticket_key": result.ticket_key},
        )
        session.commit()
        return _receipt(task=task, preview=preview, result=result, reconciled=True)

    attempt.status = "SUCCEEDED"
    attempt.response_json = {
        "ticket_key": result.ticket_key,
        "status": result.status,
        "replayed": result.replayed,
    }
    task.state = TaskState.CONFIRMING.value
    record_event(
        session,
        task_id=task.id,
        event_type="TOOL_CALL_SUCCEEDED",
        payload={"ticket_key": result.ticket_key, "replayed": result.replayed},
    )
    session.commit()
    return _receipt(task=task, preview=preview, result=result, reconciled=False)
