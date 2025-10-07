"""Configuration helpers for the web backend."""
from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_git_sha() -> str:
    """Return the current git SHA (short form) if available."""
    env_override = os.getenv("GIT_SHA")
    if env_override:
        return env_override

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"

    git_sha = completed.stdout.strip()
    return git_sha or "unknown"


class Settings(BaseModel):
    """Application settings derived from environment variables."""

    max_upload_mb: int = Field(10)
    ttl_minutes: int = Field(30)
    max_concurrent_jobs: int = Field(2)
    job_timeout_seconds: int = Field(120)
    app_version: str = Field(default_factory=lambda: os.getenv("APP_VERSION", "0.1.0-web"))
    git_sha: str = Field(default_factory=_resolve_git_sha)

    @classmethod
    def from_env(cls) -> "Settings":
        raw: Dict[str, Any] = {}
        env_to_field = {
            "MAX_UPLOAD_MB": "max_upload_mb",
            "TTL_MIN": "ttl_minutes",
            "MAX_CONCURRENT_JOBS": "max_concurrent_jobs",
            "JOB_TIMEOUT_SEC": "job_timeout_seconds",
        }

        for env_var, field_name in env_to_field.items():
            value = os.getenv(env_var)
            if value is None:
                continue
            try:
                raw[field_name] = int(value)
            except ValueError:
                raise ValueError(
                    f"Environment variable {env_var} must be an integer, got: {json.dumps(value)}"
                ) from None

        settings = cls(**raw)
        return settings


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings.from_env()
