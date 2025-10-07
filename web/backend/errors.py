"""Error helpers for consistent API responses."""
from __future__ import annotations

from typing import Any, Optional, TypedDict

try:  # pragma: no cover - import guard for environments without FastAPI
    from fastapi import HTTPException
except ModuleNotFoundError:  # pragma: no cover - fallback when FastAPI missing
    class HTTPException(Exception):
        """Minimal HTTPException stand-in for testing environments."""

        def __init__(self, status_code: int, detail: Any) -> None:
            super().__init__(str(detail))
            self.status_code = status_code
            self.detail = detail

__all__ = ["ErrorPayload", "build_error_payload", "http_error"]


class ErrorPayload(TypedDict, total=False):
    """Standard error payload schema returned by the API."""

    code: str
    message: str
    details: Any


def build_error_payload(code: str, message: str, details: Optional[Any] = None) -> ErrorPayload:
    """Create a standardised error payload dictionary."""

    payload: ErrorPayload = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return payload


def http_error(status_code: int, code: str, message: str, details: Optional[Any] = None) -> HTTPException:
    """Return an HTTPException with the standard error payload."""

    payload = build_error_payload(code, message, details)
    return HTTPException(status_code=status_code, detail=payload)
