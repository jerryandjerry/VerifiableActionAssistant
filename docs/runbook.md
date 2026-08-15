# Operational runbook

## Service objective for the demo

The demo should accept a seeded task, reach the expected terminal or approval state, preserve
its audit trail, and never create an unauthorized or duplicate ticket.

## Start locally

```bash
python -m pip install -e ".[dev]"
vaa serve --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl -s http://127.0.0.1:8000/healthz
```

Expected result:

```json
{"status":"ok","llm_provider":"mock","database":"sqlite"}
```

## Reset the demo

CLI:

```bash
vaa reset
```

While the app is running in demo mode:

```bash
curl -s -X POST http://127.0.0.1:8000/api/demo/reset \
  -H 'content-type: application/json' -d '{}'
```

Do not expose the reset endpoint in a production environment. Set `VAA_DEMO_MODE=false`.

## Validate a release

```bash
ruff check src tests evals
pytest --cov=vaa --cov-report=term-missing
python -m evals.run_evals
python scripts/demo.py
```

Release blockers:

- any unauthorized-access test fails;
- any approval test allows a pre-approval write;
- duplicate ticket count exceeds one in timeout recovery;
- prompt-injection content appears in the analysis or RFI;
- eval score is below 8/8 for the supplied baseline suite.

## Inspect an incident

1. Fetch the task:

   ```bash
   curl -s http://127.0.0.1:8000/api/tasks/<TASK_ID>
   ```

2. Inspect `state`, `error_message`, `verification`, `receipt`, and `audit`.
3. Inspect visible tickets:

   ```bash
   curl -s http://127.0.0.1:8000/api/demo/tickets
   ```

4. For an unknown write result, search by `idempotency_key` before retrying.
5. Preserve the database and logs before resetting the environment.
6. Add a regression test and an eval case before closing the incident.

## Common states

| State | Meaning | Operator action |
|---|---|---|
| `APPROVAL_PENDING` | proposal is verified; no write has occurred | authorized human approves or rejects |
| `APPROVED` | approval persisted; workflow deliberately paused | call the resume endpoint |
| `RECONCILING` | tool outcome was unknown | confirm external state by idempotency key |
| `FAILED` | policy, analysis, verification, or tool execution failed | inspect audit and error; do not blindly retry writes |
| `REJECTED` | human rejected the side effect | no action required; draft remains auditable |
| `COMPLETED` | postcondition was confirmed or task was read-only | inspect receipt for write tasks |

## Database notes

SQLite is adequate for a single-process demonstration. PostgreSQL is provided through
`docker-compose.postgres.yml` and is the better starting point for concurrent workers.

For production, add migrations, transaction isolation tests, backup policy, row-level security,
and a worker-claim/lease mechanism before scaling execution horizontally.

## OpenAI mode troubleshooting

- Confirm `OPENAI_API_KEY` is set only in the process environment or secret manager.
- Confirm `VAA_LLM_PROVIDER=openai`.
- Keep `VAA_OPENAI_MODEL` on a model supporting the structured schema used by the adapter.
- A model-analysis failure must not bypass the deterministic verification or approval boundary.
- Re-run the full eval suite when changing the model or prompt.
