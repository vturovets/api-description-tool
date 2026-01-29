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


def test_delete_job_removes_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    upload = _make_upload("spec.yaml", _sample_spec())
    upload_response = asyncio.run(app_module.upload_spec(upload))

    payload = ConvertRequest(upload_id=upload_response.upload_id, path="/pets", format="xlsx", validate=False)
    response = asyncio.run(app_module.convert_spec(payload))

    download_response = asyncio.run(app_module.download(response.job_id))
    output_path = Path(download_response.path)
    assert output_path.exists()

    delete_response = asyncio.run(app_module.delete_job(response.job_id))
    assert delete_response == {"status": "deleted"}
    assert not output_path.exists()
    assert not (tmp_path / upload_response.upload_id).exists()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.job_status(response.job_id))

    exc = exc_info.value
    assert exc.status_code == 404
    assert exc.detail == {"code": "JOB_NOT_FOUND", "message": "Job not found."}


def test_delete_job_handles_missing_job(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.delete_job("missing"))

    exc = exc_info.value
    assert exc.status_code == 404
    assert exc.detail == {"code": "JOB_NOT_FOUND", "message": "Job not found."}
