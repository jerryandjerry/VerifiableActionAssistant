.PHONY: install dev test eval verify-workflow reset docker lint

install:
	python -m pip install -e ".[dev]"

dev:
	uvicorn vaa.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

eval:
	python -m evals.run_evals

verify-workflow:
	python scripts/verify_workflow.py

reset:
	python -m vaa.seed --reset

lint:
	ruff check src tests evals scripts

docker:
	docker compose up --build
