from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "sqlite:///./data/vaa.db"
    llm_provider: str = "mock"
    openai_model: str = "gpt-5.6"
    auto_seed: bool = True
    workspace_reset_enabled: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.getenv("VAA_DATABASE_URL", "sqlite:///./data/vaa.db"),
            llm_provider=os.getenv("VAA_LLM_PROVIDER", "mock").strip().lower(),
            openai_model=os.getenv("VAA_OPENAI_MODEL", "gpt-5.6"),
            auto_seed=_as_bool(os.getenv("VAA_AUTO_SEED"), True),
            workspace_reset_enabled=_as_bool(
                os.getenv("VAA_WORKSPACE_RESET_ENABLED"), True
            ),
            log_level=os.getenv("VAA_LOG_LEVEL", "INFO").upper(),
        )
