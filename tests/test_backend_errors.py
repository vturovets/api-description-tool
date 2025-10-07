"""Tests for backend error helpers."""
from __future__ import annotations

from web.backend import errors


def test_http_error_payload_structure():
    """HTTP exceptions should include the standard payload structure."""

    exc = errors.http_error(422, "OPENAPI_VALIDATION_FAILED", "Validation failed", details={"field": "value"})

    assert exc.status_code == 422
    assert exc.detail == {
        "code": "OPENAPI_VALIDATION_FAILED",
        "message": "Validation failed",
        "details": {"field": "value"},
    }


def test_http_error_omits_details_when_missing():
    """Optional details should be omitted when not provided."""

    exc = errors.http_error(404, "JOB_NOT_FOUND", "Job was not found")

    assert exc.detail == {"code": "JOB_NOT_FOUND", "message": "Job was not found"}
