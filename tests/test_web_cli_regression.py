from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from tempfile import SpooledTemporaryFile

import openpyxl
import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from web.backend.models import ConvertRequest


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "tests" / "data"
INPUT_SPEC = DATA_DIR / "NGS_ASC-an.yaml"


def _load_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("API_DESC_UPLOAD_ROOT", str(tmp_path))

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


def _workbook_contents(path: Path):
    workbook = openpyxl.load_workbook(path)
    try:
        contents = {}
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            contents[sheet_name] = [list(row) for row in worksheet.iter_rows(values_only=True)]
        return contents
    finally:
        workbook.close()


def test_web_output_matches_cli_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_module = _load_app(monkeypatch, tmp_path)

    spec_bytes = INPUT_SPEC.read_bytes()
    upload = _make_upload(INPUT_SPEC.name, spec_bytes)
    upload_response = asyncio.run(app_module.upload_spec(upload))

    payload = ConvertRequest(
        upload_id=upload_response.upload_id,
        path="/v1/packages/availability/departures",
        format="xlsx",
        validate=False,
    )
    response = asyncio.run(app_module.convert_spec(payload))

    download_response = asyncio.run(app_module.download(response.job_id))
    output_path = Path(download_response.path)
    assert output_path.exists()

    expected_file = DATA_DIR / "ngs_asc_airports.xlsx"
    assert expected_file.exists(), "Expected reference workbook is missing"

    generated_contents = _workbook_contents(output_path)
    expected_contents = _workbook_contents(expected_file)

    assert generated_contents == expected_contents
