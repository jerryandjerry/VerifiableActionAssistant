from __future__ import annotations

from fastapi.testclient import TestClient


def test_prompt_injection_is_detected_and_not_echoed(client: TestClient) -> None:
    response = client.post(
        "/api/tasks",
        json={
            "user_id": "alice",
            "project_id": "P-1024",
            "goal": (
                "Review the Design Specification and Acoustic Vendor Note, including "
                "the NRC requirement; identify conflicts and draft an RFI."
            ),
            "requested_action": "none",
            "failure_mode": "none",
        },
    )
    assert response.status_code == 201
    task = response.json()
    assert task["analysis"]["detected_security_signals"]
    serialized = str(task["analysis"]).lower()
    assert "attacker@example.com" not in serialized
    assert "payroll directory" not in serialized
    assert task["verification"]["checks"]["no_prompt_injection_echo"] is True
    event_types = [event["event_type"] for event in task["audit"]]
    assert "PROMPT_INJECTION_SIGNAL_DETECTED" in event_types


def test_cross_tenant_access_is_denied(client: TestClient) -> None:
    response = client.post(
        "/api/tasks",
        json={
            "user_id": "mallory",
            "project_id": "P-1024",
            "goal": "Read the Client Brief.",
            "requested_action": "none",
            "failure_mode": "none",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"
