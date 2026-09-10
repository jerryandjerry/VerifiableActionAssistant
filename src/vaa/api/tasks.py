from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from vaa.db import get_session
from vaa.models import Task
from vaa.schemas import ApprovalRequest, TaskCreate, TaskRead
from vaa.services.orchestrator import Orchestrator, task_to_read

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    request: Request,
    session: Session = Depends(get_session),
) -> TaskRead:
    task = _orchestrator(request).create_task(session, payload)
    return task_to_read(session, task)


@router.get("", response_model=list[TaskRead])
def list_tasks(session: Session = Depends(get_session)) -> list[TaskRead]:
    tasks = session.scalars(select(Task).order_by(Task.created_at.desc())).all()
    return [task_to_read(session, task) for task in tasks]


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, session: Session = Depends(get_session)) -> TaskRead:
    task = Orchestrator._get_task(session, task_id)
    return task_to_read(session, task)


@router.post("/{task_id}/approve", response_model=TaskRead)
def approve_task(
    task_id: str,
    payload: ApprovalRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> TaskRead:
    task = _orchestrator(request).approve_task(session, task_id, payload)
    return task_to_read(session, task)


@router.post("/{task_id}/reject", response_model=TaskRead)
def reject_task(
    task_id: str,
    payload: ApprovalRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> TaskRead:
    task = _orchestrator(request).reject_task(session, task_id, payload)
    return task_to_read(session, task)


@router.post("/{task_id}/resume", response_model=TaskRead)
def resume_task(
    task_id: str,
    payload: ApprovalRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> TaskRead:
    task = _orchestrator(request).resume_task(session, task_id, payload)
    return task_to_read(session, task)
