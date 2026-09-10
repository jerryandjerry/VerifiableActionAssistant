from __future__ import annotations

from fastapi.testclient import TestClient


def test_timeout_after_success_is_reconciled_without_duplicate(
    client: TestClient, action_payload: dict[str, str]
) -> None:
    action_payload["failure_mode"] = "timeout_after_success"
    task = client.post("/api/tasks", json=action_payload).json()
    completed = client.post(
        f"/api/tasks/{task['id']}/approve",
        json={"actor_id": "alice"},
    ).json()

    assert completed["state"] == "COMPLETED"
    assert completed["receipt"]["reconciled_after_timeout"] is True
    assert completed["receipt"]["confirmed"] is True
    assert len(client.get("/api/workspace/tickets").json()) == 1
    event_types = [event["event_type"] for event in completed["audit"]]
    assert "WRITE_RECONCILED" in event_types


def test_repeated_approval_does_not_repeat_ticket_write(
    client: TestClient, action_payload: dict[str, str]
) -> None:
    task = client.post("/api/tasks", json=action_payload).json()
    first = client.post(
        f"/api/tasks/{task['id']}/approve",
        json={"actor_id": "alice"},
    )
    second = client.post(
        f"/api/tasks/{task['id']}/approve",
        json={"actor_id": "alice"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["receipt"]["ticket_key"] == second.json()["receipt"]["ticket_key"]
    assert len(client.get("/api/workspace/tickets").json()) == 1


def test_duplicate_task_payload_reuses_idempotency_key(
    client: TestClient, action_payload: dict[str, str]
) -> None:
    first = client.post("/api/tasks", json=action_payload).json()
    first_done = client.post(
        f"/api/tasks/{first['id']}/approve", json={"actor_id": "alice"}
    ).json()

    second = client.post("/api/tasks", json=action_payload).json()
    second_done = client.post(
        f"/api/tasks/{second['id']}/approve", json={"actor_id": "alice"}
    ).json()

    assert first_done["receipt"]["idempotency_key"] == second_done["receipt"]["idempotency_key"]
    assert second_done["receipt"]["replayed"] is True
    assert len(client.get("/api/workspace/tickets").json()) == 1
