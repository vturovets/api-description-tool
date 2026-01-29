"""Pydantic models for the web backend."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

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


class ConvertRequest(BaseModel):
    """Payload for conversion requests."""

    upload_id: str
    path: str
    method: Optional[str] = None
    format: Literal["xlsx", "csv"] = "xlsx"
    validate: bool = False


class JobRows(BaseModel):
    """Row counts for generated tables."""

    params: int
    request_body: int
    response_body: int


class JobMetrics(BaseModel):
    """Metrics captured for a conversion job."""

    duration_ms: int
    rows: JobRows
    validate_enabled: bool
    format: Literal["xlsx", "csv"]


class JobLogEntry(BaseModel):
    """Log entry captured for a conversion job."""

    timestamp: str
    level: str
    message: str


class ConvertResponse(BaseModel):
    """Response payload returned after conversion finishes."""

    job_id: str
    status: str
    rows: JobRows
    download_url: str


class JobStatusResponse(BaseModel):
    """Response payload for job status polling."""

    job_id: str
    status: str
    logs: List[JobLogEntry]
    metrics: Optional[JobMetrics] = None
    download_url: Optional[str] = None
