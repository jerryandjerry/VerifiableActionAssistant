#!/usr/bin/env python3
"""Run the complete approval and timeout-reconciliation flow without a web server."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from vaa.config import Settings
from vaa.main import create_app


def compact(task: dict[str, object]) -> dict[str, object]:
    evidence = task.get("evidence") or []
    receipt = task.get("receipt")
    return {
        "id": task["id"],
        "lane": task["lane"],
        "state": task["state"],
        "conflicts": [
            claim["claim_key"]
            for claim in evidence
            if claim["status"] == "conflicting"
        ],
        "security_signals": (task.get("analysis") or {}).get(
            "detected_security_signals", []
        ),
        "receipt": receipt,
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(
            Settings(
                database_url=f"sqlite:///{Path(tmp) / 'demo.db'}",
                llm_provider="mock",
                auto_seed=True,
                demo_mode=True,
            )
        )
        with TestClient(app) as client:
            created = client.post(
                "/api/tasks",
                json={
                    "user_id": "alice",
                    "project_id": "P-1024",
                    "goal": (
                        "Compare the latest Client Brief and Design Specification, "
                        "then draft an RFI for the workstation conflict."
                    ),
                    "requested_action": "create_jira_ticket",
                    "failure_mode": "timeout_after_success",
                },
            )
            created.raise_for_status()
            task = created.json()
            print("\n1. Verified proposal\n")
            print(json.dumps(compact(task), indent=2))

            approved = client.post(
                f"/api/tasks/{task['id']}/approve",
                json={"actor_id": "alice", "comment": "Headless demo approval"},
            )
            approved.raise_for_status()
            task = approved.json()
            print("\n2. Approved, executed, and reconciled\n")
            print(json.dumps(compact(task), indent=2))

            tickets = client.get("/api/demo/tickets")
            tickets.raise_for_status()
            print("\n3. Visible external tickets\n")
            print(json.dumps(tickets.json(), indent=2))

            assert task["state"] == "COMPLETED"
            assert task["receipt"]["reconciled_after_timeout"] is True
            assert len(tickets.json()) == 1
            print("\nPASS: unknown tool outcome produced exactly one confirmed ticket.\n")


if __name__ == "__main__":
    main()
