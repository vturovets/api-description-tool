"""Pydantic models for the web backend."""
from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response payload for service health checks."""

    status: str
    version: str
    git_sha: str


class UploadResponse(BaseModel):
    """Response payload returned after a successful spec upload."""

    upload_id: str
    file_name: str
    size: int
    paths: Dict[str, List[str]]
