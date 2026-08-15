from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from vaa.db import get_session, init_database
from vaa.errors import PolicyViolationError
from vaa.models import Base, Document, Project, User
from vaa.schemas import DemoContext
from vaa.seed import seed_demo
from vaa.services.orchestrator import list_tickets

router = APIRouter(prefix="/api/demo", tags=["demo"])


_PRESETS = [
    {
        "id": "happy-path",
        "label": "Happy path",
        "goal": (
            "Compare the latest Client Brief, Design Specification, and Client "
            "Coordination Meeting Notes; identify conflicts and draft an RFI."
        ),
        "requested_action": "create_jira_ticket",
        "failure_mode": "none",
    },
    {
        "id": "malicious-document",
        "label": "Malicious document",
        "goal": (
            "Review the Design Specification and Acoustic Vendor Note, including the "
            "NRC requirement; identify conflicts and draft an RFI."
        ),
        "requested_action": "create_jira_ticket",
        "failure_mode": "none",
    },
    {
        "id": "timeout-recovery",
        "label": "Timeout after success",
        "goal": (
            "Compare the latest Client Brief and Design Specification, then draft an "
            "RFI for the workstation conflict."
        ),
        "requested_action": "create_jira_ticket",
        "failure_mode": "timeout_after_success",
    },
    {
        "id": "durable-resume",
        "label": "Pause and resume",
        "goal": (
            "Compare the latest project documents, identify conflicts, and draft an RFI."
        ),
        "requested_action": "create_jira_ticket",
        "failure_mode": "pause_after_approval",
    },
    {
        "id": "research-only",
        "label": "Research only",
        "goal": (
            "Compare the latest Client Brief, Design Specification, and Meeting Notes; "
            "identify every requirement conflict."
        ),
        "requested_action": "none",
        "failure_mode": "none",
    },
]


@router.get("/context", response_model=DemoContext)
def demo_context(session: Session = Depends(get_session)) -> DemoContext:
    users = session.scalars(select(User).order_by(User.id)).all()
    projects = session.scalars(select(Project).order_by(Project.id)).all()
    documents = session.scalars(
        select(Document).where(Document.status == "approved").order_by(Document.project_id)
    ).all()
    return DemoContext(
        users=[
            {"id": user.id, "tenant_id": user.tenant_id, "name": user.name, "role": user.role}
            for user in users
        ],
        projects=[
            {"id": project.id, "tenant_id": project.tenant_id, "name": project.name}
            for project in projects
        ],
        documents=[
            {
                "id": document.id,
                "project_id": document.project_id,
                "title": document.title,
                "version": document.version,
                "trust_level": document.trust_level,
            }
            for document in documents
        ],
        presets=_PRESETS,
    )


@router.get("/tickets")
def demo_tickets(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    return list_tickets(session)


@router.post("/reset")
def reset_demo(request: Request) -> dict[str, str]:
    if not request.app.state.settings.demo_mode:
        raise PolicyViolationError("Demo reset is disabled")
    engine = request.app.state.engine
    Base.metadata.drop_all(engine)
    init_database(engine)
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        seed_demo(session)
    return {"status": "reset"}
