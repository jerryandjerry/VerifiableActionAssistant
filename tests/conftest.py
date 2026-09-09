from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from vaa.config import Settings
from vaa.main import create_app


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    app = create_app(
        Settings(
            database_url=database_url,
            llm_provider="mock",
            auto_seed=True,
            workspace_reset_enabled=True,
        )
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def action_payload() -> dict[str, str]:
    return {
        "user_id": "alice",
        "project_id": "P-1024",
        "goal": (
            "Compare the latest Client Brief, Design Specification, and Client "
            "Coordination Meeting Notes; identify conflicts and draft an RFI."
        ),
        "requested_action": "create_jira_ticket",
        "failure_mode": "none",
    }
