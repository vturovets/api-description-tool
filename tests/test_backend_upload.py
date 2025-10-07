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


def _load_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: Dict[str, str] | None = None):
    """Reload backend modules with isolated environment settings."""

    env = env or {}
    monkeypatch.setenv("API_DESC_UPLOAD_ROOT", str(tmp_path))
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from web.backend import config as config_module
    from web.backend.services import storage as storage_module

    importlib.reload(storage_module)
    config_module.get_settings.cache_clear()

    from web.backend import app as app_module

    importlib.reload(app_module)

    return app_module


def _make_upload(filename: str, content: bytes, content_type: str = "application/x-yaml") -> UploadFile:
    """Create an UploadFile instance backed by an in-memory buffer."""

    buffer = SpooledTemporaryFile()
    buffer.write(content)
    buffer.seek(0)
    headers = Headers({"content-type": content_type})
    upload = UploadFile(filename=filename, file=buffer, headers=headers)
    return upload


def test_upload_success_returns_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)
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
            post:
              responses:
                "200":
                  description: ok
          /owners:
            get:
              responses:
                "200":
                  description: ok
        """
    ).strip()

    upload = _make_upload("spec.yaml", spec_text.encode("utf-8"))

    response = asyncio.run(app_module.upload_spec(upload))

    data = response.model_dump()
    assert set(data.keys()) == {"upload_id", "file_name", "size", "paths"}
    assert data["file_name"] == "spec.yaml"
    assert data["size"] == len(spec_text.encode("utf-8"))
    assert data["paths"] == {"/pets": ["get", "post"], "/owners": ["get"]}

    upload_dir = tmp_path / data["upload_id"]
    saved_file = upload_dir / "spec.yaml"
    assert saved_file.exists()
    assert saved_file.read_bytes() == spec_text.encode("utf-8")


def test_upload_rejects_large_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path, env={"MAX_UPLOAD_MB": "0"})

    upload = _make_upload("spec.yaml", b"a")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.upload_spec(upload))

    exc = exc_info.value
    assert exc.status_code == 413
    assert exc.detail == {
        "code": "FILE_TOO_LARGE",
        "message": "File exceeds maximum size of 0 MB.",
    }


def test_upload_rejects_wrong_extension(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    upload = _make_upload("spec.txt", b"not yaml", content_type="text/plain")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.upload_spec(upload))

    exc = exc_info.value
    assert exc.status_code == 415
    assert exc.detail == {
        "code": "UNSUPPORTED_MEDIA_TYPE",
        "message": "Only YAML files (.yaml, .yml) are supported.",
    }


def test_upload_handles_yaml_syntax_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    upload = _make_upload("spec.yaml", b"openapi: [")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(app_module.upload_spec(upload))

    exc = exc_info.value
    assert exc.status_code == 400
    assert exc.detail["code"] == "YAML_SYNTAX_ERROR"
    assert exc.detail["message"] == "Failed to parse YAML content."
    assert "error" in exc.detail["details"]
