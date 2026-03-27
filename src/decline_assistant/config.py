"""Runtime settings, read from environment variables (and a local ``.env``)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MODEL = "claude-sonnet-4-5"
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def default_knowledge_dir() -> Path:
    """``knowledge/`` next to the package in a checkout, else ``./knowledge``."""
    candidate = _PACKAGE_ROOT / "knowledge"
    return candidate if candidate.is_dir() else Path.cwd() / "knowledge"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DECLINES_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    model: str = Field(
        default=DEFAULT_MODEL,
        validation_alias=AliasChoices("ANTHROPIC_MODEL", "DECLINES_MODEL"),
        description="Claude model id used for analysis and report summaries.",
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY"),
        description="Read here only to pick a backend; the SDK reads it from the environment.",
    )
    llm_backend: Literal["anthropic", "fake"] = Field(
        default="anthropic",
        description="'fake' runs the deterministic offline client (no network, no key).",
    )
    knowledge_dir: Path = Field(default_factory=default_knowledge_dir)
    max_tokens: int = Field(default=4096, ge=256, le=32_000)
    retrieval_k: int = Field(default=6, ge=1, le=20)
    max_tool_rounds: int = Field(default=6, ge=1, le=20)

    @property
    def can_use_anthropic(self) -> bool:
        return self.anthropic_api_key is not None and bool(
            self.anthropic_api_key.get_secret_value()
        )
