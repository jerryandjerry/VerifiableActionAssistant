from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vaa.errors import ToolTimeoutAfterSuccess
from vaa.models import ExternalTicket


@dataclass(frozen=True, slots=True)
class TicketResult:
    ticket_key: str
    status: str
    idempotency_key: str
    replayed: bool


class FakeJira:
    """A database-backed Jira simulator with exactly-once visible behavior."""

    @staticmethod
    def find_by_idempotency_key(
        session: Session, idempotency_key: str
    ) -> ExternalTicket | None:
        return session.scalar(
            select(ExternalTicket).where(
                ExternalTicket.idempotency_key == idempotency_key
            )
        )

    @classmethod
    def create_ticket(
        cls,
        session: Session,
        *,
        tenant_id: str,
        project_id: str,
        idempotency_key: str,
        title: str,
        body: str,
        simulate_timeout_after_success: bool = False,
    ) -> TicketResult:
        existing = cls.find_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            return TicketResult(
                ticket_key=existing.ticket_key,
                status=existing.status,
                idempotency_key=idempotency_key,
                replayed=True,
            )

        count = session.scalar(select(func.count(ExternalTicket.id))) or 0
        ticket = ExternalTicket(
            tenant_id=tenant_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
            ticket_key=f"RFI-{count + 1:04d}",
            title=title,
            body=body,
            status="OPEN",
        )
        session.add(ticket)
        session.commit()

        if simulate_timeout_after_success:
            raise ToolTimeoutAfterSuccess(
                "The ticket was created, but the tool response timed out"
            )

        return TicketResult(
            ticket_key=ticket.ticket_key,
            status=ticket.status,
            idempotency_key=idempotency_key,
            replayed=False,
        )
