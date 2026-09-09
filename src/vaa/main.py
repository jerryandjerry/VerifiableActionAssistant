from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vaa.api.tasks import router as tasks_router
from vaa.api.workspace import router as workspace_router
from vaa.config import Settings
from vaa.db import create_database_engine, create_session_factory, init_database
from vaa.errors import DomainError
from vaa.schemas import HealthRead
from vaa.seed import seed_reference_data
from vaa.services.orchestrator import Orchestrator


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))

    if settings.database_url.startswith("sqlite:///./"):
        database_path = settings.database_url.removeprefix("sqlite:///./")
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        init_database(engine)
        if settings.auto_seed:
            with session_factory() as session:
                seed_reference_data(session)
        yield
        engine.dispose()

    app = FastAPI(
        title="Verifiable Action Assistant",
        version="0.1.0",
        description=(
            "A policy-governed, evidence-grounded and durable DesignOps assistant."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.orchestrator = Orchestrator(settings)

    app.include_router(tasks_router)
    app.include_router(workspace_router)

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": str(exc)},
        )

    @app.get("/healthz", response_model=HealthRead, tags=["system"])
    def health() -> HealthRead:
        database_kind = settings.database_url.split(":", maxsplit=1)[0]
        return HealthRead(
            llm_provider=settings.llm_provider,
            database=database_kind,
        )

    web_root = Path(__file__).parent / "web"
    app.mount("/static", StaticFiles(directory=web_root / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(web_root / "index.html")

    return app


app = create_app()
