from __future__ import annotations

from fastapi.testclient import TestClient


def test_rejection_produces_no_write(
    client: TestClient, action_payload: dict[str, str]
) -> None:
    task = client.post("/api/tasks", json=action_payload).json()
    rejected = client.post(
        f"/api/tasks/{task['id']}/reject",
        json={"actor_id": "alice", "comment": "Needs client clarification"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["state"] == "REJECTED"
    assert rejected.json()["receipt"] is None
    assert client.get("/api/workspace/tickets").json() == []


def test_viewer_cannot_request_write(client: TestClient, action_payload: dict[str, str]) -> None:
    action_payload["user_id"] = "viewer"
    response = client.post("/api/tasks", json=action_payload)
    assert response.status_code == 403
    assert response.json()["error"] == "policy_violation"


def test_viewer_cannot_approve(client: TestClient, action_payload: dict[str, str]) -> None:
    task = client.post("/api/tasks", json=action_payload).json()
    response = client.post(
        f"/api/tasks/{task['id']}/approve",
        json={"actor_id": "viewer"},
    )
    assert response.status_code == 403
    assert client.get("/api/workspace/tickets").json() == []
