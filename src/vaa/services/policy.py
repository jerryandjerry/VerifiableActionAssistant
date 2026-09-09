from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vaa.errors import AuthorizationError, NotFoundError, PolicyViolationError
from vaa.models import Project, ProjectMembership, Task, User
from vaa.schemas import TaskContract


def get_user_and_project(session: Session, user_id: str, project_id: str) -> tuple[User, Project]:
    user = session.get(User, user_id)
    project = session.get(Project, project_id)
    if user is None:
        raise NotFoundError(f"Unknown user: {user_id}")
    if project is None:
        raise NotFoundError(f"Unknown project: {project_id}")
    if user.tenant_id != project.tenant_id:
        raise AuthorizationError("Cross-tenant project access is not allowed")
    return user, project


def get_membership(session: Session, user_id: str, project_id: str) -> ProjectMembership:
    membership = session.scalar(
        select(ProjectMembership).where(
            ProjectMembership.user_id == user_id,
            ProjectMembership.project_id == project_id,
        )
    )
    if membership is None:
        raise AuthorizationError("User is not a member of this project")
    return membership


def require_read(session: Session, user_id: str, project_id: str) -> ProjectMembership:
    get_user_and_project(session, user_id, project_id)
    membership = get_membership(session, user_id, project_id)
    if not membership.can_read:
        raise AuthorizationError("Read access is required")
    return membership


def require_write(session: Session, user_id: str, project_id: str) -> ProjectMembership:
    membership = require_read(session, user_id, project_id)
    if not membership.can_write:
        raise AuthorizationError("Write access is required")
    return membership


def require_approval(session: Session, user_id: str, project_id: str) -> ProjectMembership:
    membership = require_read(session, user_id, project_id)
    if not membership.can_approve:
        raise AuthorizationError("Approval permission is required")
    return membership


def enforce_tool_policy(task: Task, contract: TaskContract, tool_name: str) -> None:
    if tool_name not in contract.allowed_tools:
        raise PolicyViolationError(f"Tool {tool_name!r} is outside the task contract")
    approved_states = {
        "APPROVED",
        "EXECUTING",
        "RECONCILING",
        "CONFIRMING",
        "COMPLETED",
    }
    if contract.approval_policy == "before_any_write" and task.state not in approved_states:
        raise PolicyViolationError("A write tool cannot run before approval")
