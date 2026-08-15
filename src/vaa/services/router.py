from __future__ import annotations

from vaa.enums import RequestedAction, RiskLane
from vaa.schemas import Budgets, TaskContract


_RESEARCH_TERMS = {
    "compare",
    "conflict",
    "analyse",
    "analyze",
    "research",
    "review",
    "cross-check",
    "latest documents",
    "rfi",
}


def choose_lane(goal: str, requested_action: RequestedAction) -> RiskLane:
    if requested_action != RequestedAction.NONE:
        return RiskLane.ACTION_CONTROLLED
    lowered = goal.lower()
    if any(term in lowered for term in _RESEARCH_TERMS):
        return RiskLane.RESEARCH_VERIFIED
    return RiskLane.READ_FAST


def build_contract(
    *,
    task_id: str,
    goal: str,
    lane: RiskLane,
    tenant_id: str,
    project_id: str,
) -> TaskContract:
    tools = ["document.search", "document.read"]
    approval_policy = "none"
    required_evidence = lane != RiskLane.READ_FAST
    criteria = ["all returned documents pass tenant and project ACL checks"]

    if lane in {RiskLane.RESEARCH_VERIFIED, RiskLane.ACTION_CONTROLLED}:
        criteria.extend(
            [
                "all key claims are source-backed",
                "document conflicts are surfaced instead of silently resolved",
            ]
        )
    if lane == RiskLane.ACTION_CONTROLLED:
        tools.append("jira.create_ticket")
        approval_policy = "before_any_write"
        criteria.extend(
            [
                "no write occurs before approval",
                "the Jira side effect is idempotent",
                "ticket existence is confirmed after execution",
            ]
        )

    return TaskContract(
        task_id=task_id,
        goal=goal,
        lane=lane,
        tenant_id=tenant_id,
        project_id=project_id,
        allowed_tools=tools,
        required_evidence=required_evidence,
        approval_policy=approval_policy,
        budgets=Budgets(
            max_tool_calls=20 if lane != RiskLane.READ_FAST else 5,
            max_runtime_seconds=180 if lane != RiskLane.READ_FAST else 30,
            max_cost_usd=1.50 if lane == RiskLane.ACTION_CONTROLLED else 0.75,
        ),
        success_criteria=criteria,
    )
