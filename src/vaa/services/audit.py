from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from vaa.models import AuditEvent


def record_event(
    session: Session,
    *,
    task_id: str | None,
    event_type: str,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        task_id=task_id,
        event_type=event_type,
        actor_id=actor_id,
        payload_json=payload or {},
    )
    session.add(event)
    return event
