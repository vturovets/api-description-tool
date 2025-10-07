"""Ephemeral storage helpers for uploaded specs and generated artifacts."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Optional

__all__ = [
    "UPLOAD_ROOT",
    "ensure_root",
    "ensure_upload_dir",
    "resolve_upload_path",
    "safe_component_name",
    "safe_filename",
]

_DEFAULT_ROOT = "/tmp/api-desc-uploads"
UPLOAD_ROOT = Path(os.getenv("API_DESC_UPLOAD_ROOT", _DEFAULT_ROOT))

_ALLOWED_PATTERN = re.compile(r"[^A-Za-z0-9._-]")
_MAX_COMPONENT_LENGTH = 255


def ensure_root() -> Path:
    """Ensure the upload root directory exists and return it."""

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOAD_ROOT


def safe_component_name(value: str, *, fallback: Optional[str] = None) -> str:
    """Return a filesystem-safe component name for directories."""

    value = (value or "").strip()
    cleaned = _ALLOWED_PATTERN.sub("_", value)
    cleaned = cleaned.strip("._")
    if not cleaned:
        cleaned = fallback or uuid.uuid4().hex
    return cleaned[:_MAX_COMPONENT_LENGTH]


def safe_filename(filename: str, *, fallback: str = "upload") -> str:
    """Return a safe filename component stripping directories and unsafe chars."""

    name = Path(filename or "").name
    safe_name = safe_component_name(name, fallback=fallback)
    # Avoid filenames that may resolve to parent directories after sanitisation.
    if safe_name in {"", ".", ".."}:
        safe_name = fallback
    return safe_name


def ensure_upload_dir(upload_id: str) -> Path:
    """Create (if needed) and return the directory for the given upload ID."""

    ensure_root()
    safe_id = safe_component_name(upload_id, fallback=uuid.uuid4().hex)
    upload_dir = UPLOAD_ROOT / safe_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def resolve_upload_path(upload_id: str, filename: str, *, fallback: str = "upload") -> Path:
    """Return a safe path for storing a file within an upload directory."""

    upload_dir = ensure_upload_dir(upload_id)
    safe_name = safe_filename(filename, fallback=fallback)
    return upload_dir / safe_name
