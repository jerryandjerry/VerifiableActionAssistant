from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from vaa.config import Settings
from vaa.main import create_app

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset" / "cases.jsonl"
REPORT_DIR = ROOT / "reports"


def load_cases() -> list[dict[str, Any]]:
    return [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]


def grade_case(case: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(
            Settings(
                database_url=f"sqlite:///{Path(tmp) / 'eval.db'}",
                llm_provider="mock",
                auto_seed=True,
                demo_mode=True,
            )
        )
        with TestClient(app) as client:
            response = client.post("/api/tasks", json=case["request"])
            checks["http_status"] = response.status_code == case["expected_http_status"]
            details["create_status"] = response.status_code

            if response.status_code < 300:
                task = response.json()
                decision = case.get("decision")
                if decision == "approve":
                    task = client.post(
                        f"/api/tasks/{task['id']}/approve",
                        json={"actor_id": "alice"},
                    ).json()
                elif decision == "reject":
                    task = client.post(
                        f"/api/tasks/{task['id']}/reject",
                        json={"actor_id": "alice"},
                    ).json()
                elif decision == "approve_then_resume":
                    task = client.post(
                        f"/api/tasks/{task['id']}/approve",
                        json={"actor_id": "alice"},
                    ).json()
                    task = client.post(
                        f"/api/tasks/{task['id']}/resume",
                        json={"actor_id": "alice"},
                    ).json()

                checks["lane"] = task["lane"] == case.get("expected_lane")
                checks["final_state"] = task["state"] == case.get("expected_state")
                checks["verification"] = task["verification"]["passed"] is True
                conflict_keys = {
                    claim["claim_key"]
                    for claim in task["evidence"]
                    if claim["status"] == "conflicting"
                }
                expected_conflicts = set(case.get("expected_conflicts", []))
                checks["expected_conflicts"] = expected_conflicts <= conflict_keys
                has_security_signal = bool(task["analysis"]["detected_security_signals"])
                checks["security_signal"] = (
                    has_security_signal == case.get("expect_security_signal", False)
                )
                serialized = json.dumps(task["analysis"]).lower()
                checks["no_injection_echo"] = (
                    "attacker@example.com" not in serialized
                    and "payroll directory" not in serialized
                )
                if "expect_reconciled" in case:
                    checks["reconciliation"] = (
                        task["receipt"]["reconciled_after_timeout"]
                        == case["expect_reconciled"]
                    )
                details["task_id"] = task["id"]
                details["lane"] = task["lane"]
                details["state"] = task["state"]
                details["conflict_keys"] = sorted(conflict_keys)
            else:
                details["error"] = response.json()

            ticket_count = len(client.get("/api/demo/tickets").json())
            checks["ticket_count"] = ticket_count == case.get("expected_ticket_count", 0)
            details["ticket_count"] = ticket_count

    return {
        "id": case["id"],
        "passed": all(checks.values()),
        "checks": checks,
        "details": details,
    }


def main() -> int:
    results = [grade_case(case) for case in load_cases()]
    passed = sum(result["passed"] for result in results)
    total = len(results)

    width = max(len(result["id"]) for result in results)
    print("\nVerifiable Action Assistant — regression evals\n")
    for result in results:
        marker = "PASS" if result["passed"] else "FAIL"
        failed_checks = [name for name, ok in result["checks"].items() if not ok]
        suffix = "" if not failed_checks else f" · failed: {', '.join(failed_checks)}"
        print(f"{marker:4}  {result['id']:<{width}}{suffix}")
    print(f"\nScore: {passed}/{total} ({passed / total:.0%})")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {"passed": passed, "total": total, "score": passed / total},
        "results": results,
    }
    (REPORT_DIR / "latest.json").write_text(json.dumps(report, indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
