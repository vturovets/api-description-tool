from __future__ import annotations

import asyncio
import importlib
import textwrap
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Dict

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from web.backend.models import ConvertRequest


def _load_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: Dict[str, str] | None = None):
    env = env or {}
    monkeypatch.setenv("API_DESC_UPLOAD_ROOT", str(tmp_path))
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from web.backend import config as config_module
    from web.backend.services import jobs as jobs_module
    from web.backend.services import storage as storage_module

    importlib.reload(jobs_module)
    importlib.reload(storage_module)
    config_module.get_settings.cache_clear()

    from web.backend import app as app_module

    importlib.reload(app_module)

    return app_module


def _make_upload(filename: str, content: bytes, content_type: str = "application/x-yaml") -> UploadFile:
    buffer = SpooledTemporaryFile()
    buffer.write(content)
    buffer.seek(0)
    headers = Headers({"content-type": content_type})
    return UploadFile(filename=filename, file=buffer, headers=headers)


def _sample_spec() -> bytes:
    spec_text = textwrap.dedent(
        """
        openapi: 3.0.1
        info:
          title: Sample
          version: 1.0.0
        paths:
          /pets:
            get:
              responses:
                "200":
                  description: ok
        """
    ).strip()
    return spec_text.encode("utf-8")


def test_convert_success_returns_download_and_metrics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    upload = _make_upload("spec.yaml", _sample_spec())
    upload_response = asyncio.run(app_module.upload_spec(upload))

    payload = ConvertRequest(upload_id=upload_response.upload_id, path="/pets", format="xlsx", validate=False)
    response = asyncio.run(app_module.convert_spec(payload))

    assert response.status == "succeeded"
    assert response.download_url == f"/api/download/{response.job_id}"
    assert response.rows.params >= 1
    assert response.rows.request_body >= 1
    assert response.rows.response_body >= 1

    status = asyncio.run(app_module.job_status(response.job_id))
    assert status.job_id == response.job_id
    assert status.status == "succeeded"
    assert status.metrics is not None
    assert status.download_url == response.download_url
    assert status.logs

    download_response = asyncio.run(app_module.download(response.job_id))
    assert download_response.filename.endswith(".xlsx")
    assert Path(download_response.path).exists()


def test_convert_rejects_invalid_format(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    payload = ConvertRequest(upload_id="missing", path="/pets", format="csv", validate=False)
    payload.format = "pdf"  # type: ignore[assignment]

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.convert_spec(payload))

    exc = exc_info.value
    assert exc.status_code == 422
    assert exc.detail == {"code": "INVALID_FORMAT", "message": "Unsupported format: pdf"}


def test_convert_rejects_missing_upload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    payload = ConvertRequest(upload_id="missing", path="/pets", format="xlsx", validate=False)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.convert_spec(payload))

    exc = exc_info.value
    assert exc.status_code == 404
    assert exc.detail == {"code": "JOB_NOT_FOUND", "message": "Upload not found for the provided upload_id."}


def test_convert_reports_filtering_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    upload = _make_upload("spec.yaml", _sample_spec())
    upload_response = asyncio.run(app_module.upload_spec(upload))

    payload = ConvertRequest(upload_id=upload_response.upload_id, path="/missing", format="xlsx", validate=False)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.convert_spec(payload))

    exc = exc_info.value
    assert exc.status_code == 422
    assert exc.detail["code"] == "PATH_OR_METHOD_NOT_FOUND"


def test_job_endpoints_handle_missing_job(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.job_status("missing"))

    exc = exc_info.value
    assert exc.status_code == 404
    assert exc.detail == {"code": "JOB_NOT_FOUND", "message": "Job not found."}

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.download("missing"))

    exc = exc_info.value
    assert exc.status_code == 404
    assert exc.detail == {"code": "JOB_NOT_FOUND", "message": "Job output not found."}
