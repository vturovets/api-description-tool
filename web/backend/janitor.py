"""Background cleanup utilities for ephemeral upload storage."""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .services import storage

__all__ = ["purge_expired"]

logger = logging.getLogger(__name__)


def _get_path_mtime(path: Path) -> datetime:
    stat = path.stat()
    return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)


def purge_expired(ttl_min: int, *, now: Optional[datetime] = None) -> int:
    """Delete upload directories older than the provided TTL."""

    root = storage.UPLOAD_ROOT
    if not root.exists():
        return 0

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max(ttl_min, 0))
    removed = 0

    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        try:
            mtime = _get_path_mtime(entry)
        except FileNotFoundError:
            continue

        if mtime > cutoff:
            continue

        try:
            shutil.rmtree(entry)
        except FileNotFoundError:
            continue
        except Exception:  # pragma: no cover - defensive logging
            logger.exception(
                "Failed to delete expired upload directory",
                extra={"event": "JANITOR_ERROR", "upload_id": entry.name, "path": str(entry)},
            )
            continue

        removed += 1
        logger.info(
            "Deleted expired upload directory",
            extra={"event": "JANITOR_DELETE", "upload_id": entry.name, "path": str(entry)},
        )

    return removed
