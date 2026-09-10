from __future__ import annotations

from fastapi.testclient import TestClient


def test_workflow_can_pause_after_approval_and_resume(
    client: TestClient, action_payload: dict[str, str]
) -> None:
    action_payload["failure_mode"] = "pause_after_approval"
    task = client.post("/api/tasks", json=action_payload).json()

    paused = client.post(
        f"/api/tasks/{task['id']}/approve",
        json={"actor_id": "alice"},
    ).json()
    assert paused["state"] == "APPROVED"
    assert paused["receipt"] is None
    assert client.get("/api/workspace/tickets").json() == []

    resumed = client.post(
        f"/api/tasks/{task['id']}/resume",
        json={"actor_id": "alice"},
    ).json()
    assert resumed["state"] == "COMPLETED"
    assert resumed["receipt"]["confirmed"] is True
    assert len(client.get("/api/workspace/tickets").json()) == 1
