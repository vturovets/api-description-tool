"""In-memory job registry for conversion requests."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ..models import JobLogEntry, JobMetrics

__all__ = ["JobEntry", "JobRegistry", "job_registry"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobEntry:
    """In-memory representation of a conversion job."""

    job_id: str
    upload_id: str
    status: str = "queued"
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    logs: List[JobLogEntry] = field(default_factory=list)
    metrics: Optional[JobMetrics] = None
    output_path: Optional[Path] = None
    output_filename: Optional[str] = None


class JobRegistry:
    """Thread-safe registry for conversion jobs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, JobEntry] = {}

    def create_job(self, upload_id: str) -> JobEntry:
        job_id = uuid.uuid4().hex
        entry = JobEntry(job_id=job_id, upload_id=upload_id)
        with self._lock:
            self._jobs[job_id] = entry
        return entry

    def get_job(self, job_id: str) -> Optional[JobEntry]:
        with self._lock:
            return self._jobs.get(job_id)

    def delete_job(self, job_id: str) -> Optional[JobEntry]:
        with self._lock:
            return self._jobs.pop(job_id, None)

    def update_status(self, job_id: str, status: str) -> None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if entry:
                entry.status = status
                entry.updated_at = _utc_now()

    def add_log(self, job_id: str, level: str, message: str) -> None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if not entry:
                return
            entry.logs.append(
                JobLogEntry(
                    timestamp=_utc_now().isoformat(),
                    level=level,
                    message=message,
                )
            )
            entry.updated_at = _utc_now()

    def set_metrics(self, job_id: str, metrics: JobMetrics) -> None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if not entry:
                return
            entry.metrics = metrics
            entry.updated_at = _utc_now()

    def set_output(self, job_id: str, path: Path, filename: str) -> None:
        with self._lock:
            entry = self._jobs.get(job_id)
            if not entry:
                return
            entry.output_path = path
            entry.output_filename = filename
            entry.updated_at = _utc_now()

    def delete_jobs_for_upload(self, upload_id: str) -> int:
        """Remove all jobs tied to the given upload ID."""

        removed = 0
        with self._lock:
            job_ids = [job_id for job_id, job in self._jobs.items() if job.upload_id == upload_id]
            for job_id in job_ids:
                self._jobs.pop(job_id, None)
                removed += 1
        return removed

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.status == "running")


job_registry = JobRegistry()
