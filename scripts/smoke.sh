#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "Health:"
curl -fsS "$BASE_URL/healthz"
echo

echo "Create research-only task:"
curl -fsS "$BASE_URL/api/tasks" \
  -H 'content-type: application/json' \
  -d '{
    "user_id":"alice",
    "project_id":"P-1024",
    "goal":"Compare the latest Client Brief and Design Specification for conflicts.",
    "requested_action":"none",
    "failure_mode":"none"
  }'
echo
