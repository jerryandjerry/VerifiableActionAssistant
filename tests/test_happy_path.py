from __future__ import annotations

from fastapi.testclient import TestClient


def test_happy_path_requires_approval_then_confirms_side_effect(
    client: TestClient, action_payload: dict[str, str]
) -> None:
    created = client.post("/api/tasks", json=action_payload)
    assert created.status_code == 201
    task = created.json()

    assert task["lane"] == "ACTION_CONTROLLED"
    assert task["state"] == "APPROVAL_PENDING"
    assert task["verification"]["passed"] is True
    assert any(claim["status"] == "conflicting" for claim in task["evidence"])
    assert client.get("/api/demo/tickets").json() == []

    approved = client.post(
        f"/api/tasks/{task['id']}/approve",
        json={"actor_id": "alice", "comment": "Validated against the design review"},
    )
    assert approved.status_code == 200
    completed = approved.json()
    assert completed["state"] == "COMPLETED"
    assert completed["receipt"]["confirmed"] is True
    assert completed["receipt"]["ticket_key"] == "RFI-0001"
    assert len(client.get("/api/demo/tickets").json()) == 1


def test_read_only_research_completes_without_action(client: TestClient) -> None:
    response = client.post(
        "/api/tasks",
        json={
            "user_id": "alice",
            "project_id": "P-1024",
            "goal": "Compare the Client Brief and Design Specification for conflicts.",
            "requested_action": "none",
            "failure_mode": "none",
        },
    )
    assert response.status_code == 201
    task = response.json()
    assert task["lane"] == "RESEARCH_VERIFIED"
    assert task["state"] == "COMPLETED"
    assert task["action_preview"] is None
    assert task["receipt"] is None
