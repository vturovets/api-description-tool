"""Pydantic models for the web backend."""
from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response payload for service health checks."""

    status: str
    version: str
    git_sha: str
