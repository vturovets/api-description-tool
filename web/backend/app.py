"""FastAPI application setup for the API Description Tool web backend."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
import uuid
import zipfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse

from api_description_tool.filter import FilteringError, apply_filters
from api_description_tool.parser import load_yaml, validate_openapi
from api_description_tool.tables import (
    build_request_body_table,
    build_request_params_table,
    build_response_body_table,
)
from api_description_tool.writer_csv import write_csv
from api_description_tool.writer_excel import write_excel

from .config import get_settings
from .errors import http_error
from .janitor import purge_expired
from .models import (
    ConvertRequest,
    ConvertResponse,
    HealthResponse,
    JobMetrics,
    JobRows,
    JobStatusResponse,
    UploadResponse,
)
from .services.jobs import job_registry
from .services.storage import ensure_root, ensure_upload_dir, safe_component_name


class JsonFormatter(logging.Formatter):
    """Format log records as JSON with service metadata."""

    def __init__(self, app_version: str, git_sha: str) -> None:
        super().__init__()
        self.app_version = app_version
        self.git_sha = git_sha

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "app_version": self.app_version,
            "git_sha": self.git_sha,
        }

        reserved = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in reserved:
                continue
            payload.setdefault(key, value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = record.stack_info

        return json.dumps(payload)


def configure_logging(formatter: JsonFormatter) -> None:
    """Configure root logging to emit JSON payloads."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


settings = get_settings()
configure_logging(JsonFormatter(settings.app_version, settings.git_sha))
logger = logging.getLogger(__name__)

app = FastAPI(title="API Description Tool Backend", version=settings.app_version)

_JANITOR_INTERVAL_SECONDS = 5 * 60
_ALLOWED_EXTENSIONS = {".yaml", ".yml"}
_ALLOWED_CONTENT_TYPES = {
    "application/yaml",
    "application/x-yaml",
    "text/yaml",
    "text/x-yaml",
    "application/octet-stream",
}
_HTTP_METHODS = ("get", "put", "post", "delete", "patch", "options", "head", "trace")
_ALLOWED_FORMATS = {"xlsx", "csv"}


class ValidationFailure(Exception):
    """Raised when OpenAPI validation fails."""


def _ensure_min_rows(rows: List[Dict[str, object]], kind: str) -> List[Dict[str, object]]:
    """Ensure writers always have at least headers to emit."""

    if rows:
        return rows

    if kind == "params":
        return [
            {
                "Name": "",
                "Mandatory": "",
                "Expected Value(s)": "",
                "In": "",
                "Description": "",
                "Examples": "",
            }
        ]
    if kind == "req":
        return [
            {
                "Path": "",
                "Property": "",
                "Mandatory": "",
                "Expected Value(s)": "",
                "Description": "",
                "Examples": "",
            }
        ]
    if kind == "res":
        return [
            {
                "Status": "",
                "Path": "",
                "Property": "",
                "Mandatory": "",
                "Expected Value(s)": "",
                "Description": "",
                "Examples": "",
            }
        ]
    return [{}]


def _load_upload_metadata(upload_dir: Path) -> Dict[str, str]:
    metadata_path = upload_dir / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_upload_metadata(upload_dir: Path, payload: Dict[str, str]) -> None:
    metadata_path = upload_dir / "metadata.json"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")


def _resolve_output_base(upload_dir: Path, original_filename: str) -> Path:
    base_name = "api_tab_desc"
    if original_filename:
        stem = Path(original_filename).stem
        if stem:
            base_name = f"{stem}_api_tab_desc"
    safe_base = safe_component_name(base_name, fallback="api_tab_desc")
    return upload_dir / safe_base


def _zip_csv_outputs(base_path: Path) -> Path:
    zip_path = base_path.with_suffix(".zip")
    csv_paths = [
        base_path.with_name(f"{base_path.name}_params.csv"),
        base_path.with_name(f"{base_path.name}_req_body.csv"),
        base_path.with_name(f"{base_path.name}_res_body.csv"),
    ]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for csv_path in csv_paths:
            zip_file.write(csv_path, arcname=csv_path.name)
    return zip_path


def _run_conversion(
    *,
    upload_dir: Path,
    original_filename: str,
    path: str,
    method: Optional[str],
    fmt: str,
    validate: bool,
    job_id: str,
) -> Dict[str, object]:
    job_registry.add_log(job_id, "info", "Loading OpenAPI spec")
    spec_path = upload_dir / "spec.yaml"
    spec = load_yaml(str(spec_path))

    if validate:
        job_registry.add_log(job_id, "info", "Validating OpenAPI spec")
        try:
            validate_openapi(spec)
        except ValueError as exc:
            raise ValidationFailure(str(exc)) from exc

    rules: Dict[str, Optional[str]] = {"path": path}
    if method:
        rules["method"] = method.upper()
    job_registry.add_log(job_id, "info", "Applying endpoint filter")
    spec = apply_filters(spec, rules)

    job_registry.add_log(job_id, "info", "Building tables")
    params = build_request_params_table(spec)
    req_body = build_request_body_table(spec)
    res_body = build_response_body_table(spec)

    params = _ensure_min_rows(params, "params")
    req_body = _ensure_min_rows(req_body, "req")
    res = _ensure_min_rows(res_body, "res")
    if res_body and all("Status" in row for row in res_body):
        res = res_body

    base_path = _resolve_output_base(upload_dir, original_filename)
    if fmt == "xlsx":
        output_path = base_path.with_suffix(".xlsx")
        write_excel(str(output_path), params, req_body, res)
    else:
        write_csv(str(base_path), params, req_body, res)
        output_path = _zip_csv_outputs(base_path)

    row_counts = JobRows(
        params=len(params),
        request_body=len(req_body),
        response_body=len(res),
    )

    return {
        "rows": row_counts,
        "output_path": output_path,
        "output_filename": output_path.name,
    }


def _normalise_content_type(value: Optional[str]) -> str:
    """Return the canonical content type without parameters."""

    if not value:
        return ""
    return value.split(";", 1)[0].strip().lower()


def _extract_paths(spec: object) -> Dict[str, List[str]]:
    """Return mapping of paths to supported HTTP methods from the OpenAPI spec."""

    if not isinstance(spec, dict):
        return {}

    raw_paths = spec.get("paths")
    if not isinstance(raw_paths, dict):
        return {}

    result: Dict[str, List[str]] = {}
    for path, operations in raw_paths.items():
        if not isinstance(path, str) or not isinstance(operations, dict):
            continue
        methods: List[str] = []
        seen: set[str] = set()
        for method_name, operation in operations.items():
            if not isinstance(method_name, str) or not isinstance(operation, dict):
                continue
            method_lower = method_name.lower()
            if method_lower not in _HTTP_METHODS or method_lower in seen:
                continue
            methods.append(method_lower)
            seen.add(method_lower)
        if methods:
            result[path] = methods
    return result


async def _janitor_worker(ttl_minutes: int) -> None:
    """Periodically invoke the janitor cleanup routine."""

    while True:
        try:
            purge_expired(ttl_minutes)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Janitor run failed", extra={"event": "JANITOR_ERROR"})
        await asyncio.sleep(_JANITOR_INTERVAL_SECONDS)


@app.on_event("startup")
async def _start_background_tasks() -> None:
    """Start background janitor task on application startup."""

    if getattr(app.state, "janitor_task", None):
        return
    task = asyncio.create_task(_janitor_worker(settings.ttl_minutes))
    app.state.janitor_task = task
    logger.info(
        "Background janitor started",
        extra={"event": "JANITOR_START", "interval_seconds": _JANITOR_INTERVAL_SECONDS},
    )


@app.on_event("shutdown")
async def _stop_background_tasks() -> None:
    """Cancel background janitor task during shutdown."""

    task: Optional[asyncio.Task] = getattr(app.state, "janitor_task", None)
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    app.state.janitor_task = None


@app.post("/api/upload", response_model=UploadResponse)
async def upload_spec(file: UploadFile = File(...)) -> UploadResponse:
    """Accept an OpenAPI YAML file upload and return discovered paths."""

    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    content_type = _normalise_content_type(file.content_type)
    max_bytes = settings.max_upload_mb * 1024 * 1024

    raw_bytes = b""
    try:
        if extension not in _ALLOWED_EXTENSIONS:
            raise http_error(415, "UNSUPPORTED_MEDIA_TYPE", "Only YAML files (.yaml, .yml) are supported.")
        if content_type and content_type not in _ALLOWED_CONTENT_TYPES:
            raise http_error(415, "UNSUPPORTED_MEDIA_TYPE", "Only YAML files (.yaml, .yml) are supported.")

        raw_bytes = await file.read(max_bytes + 1)
    finally:
        await file.close()

    size = len(raw_bytes)
    if size > max_bytes:
        raise http_error(
            413,
            "FILE_TOO_LARGE",
            f"File exceeds maximum size of {settings.max_upload_mb} MB.",
        )

    try:
        text_content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise http_error(
            400,
            "YAML_SYNTAX_ERROR",
            "Failed to decode YAML as UTF-8.",
            details={"error": str(exc)},
        ) from exc

    try:
        spec = yaml.safe_load(text_content) if text_content else {}
    except yaml.YAMLError as exc:
        raise http_error(
            400,
            "YAML_SYNTAX_ERROR",
            "Failed to parse YAML content.",
            details={"error": str(exc)},
        ) from exc

    paths = _extract_paths(spec)

    upload_id = uuid.uuid4().hex
    upload_dir = ensure_upload_dir(upload_id)
    file_path = upload_dir / "spec.yaml"
    file_path.write_bytes(raw_bytes)

    reported_filename = filename or "spec.yaml"
    _write_upload_metadata(
        upload_dir,
        {"upload_id": upload_id, "file_name": reported_filename, "created_at": datetime.now(timezone.utc).isoformat()},
    )
    logger.info(
        "Spec uploaded",
        extra={
            "event": "UPLOAD_SUCCESS",
            "upload_id": upload_id,
            "file_name": reported_filename,
            "size_bytes": size,
        },
    )

    return UploadResponse(
        upload_id=upload_id,
        file_name=reported_filename,
        size=size,
        paths=paths,
    )


@app.post("/api/convert", response_model=ConvertResponse)
async def convert_spec(payload: ConvertRequest) -> ConvertResponse:
    """Run conversion for a previously uploaded spec."""

    fmt = (payload.format or "").strip().lower()
    if fmt not in _ALLOWED_FORMATS:
        raise http_error(422, "INVALID_FORMAT", f"Unsupported format: {payload.format}")

    if job_registry.running_count() >= settings.max_concurrent_jobs:
        raise http_error(429, "TOO_MANY_JOBS", "Too many conversion jobs are running.")

    upload_root = ensure_root()
    upload_dir = upload_root / safe_component_name(payload.upload_id, fallback=payload.upload_id)
    spec_path = upload_dir / "spec.yaml"
    if not spec_path.exists():
        raise http_error(404, "JOB_NOT_FOUND", "Upload not found for the provided upload_id.")

    metadata = _load_upload_metadata(upload_dir)
    original_filename = metadata.get("file_name", "spec.yaml")

    job = job_registry.create_job(payload.upload_id)
    job_registry.update_status(job.job_id, "running")
    job_registry.add_log(job.job_id, "info", "Conversion started")

    start_time = time.monotonic()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _run_conversion,
                upload_dir=upload_dir,
                original_filename=original_filename,
                path=payload.path,
                method=payload.method,
                fmt=fmt,
                validate=payload.validate,
                job_id=job.job_id,
            ),
            timeout=settings.job_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        job_registry.update_status(job.job_id, "failed")
        job_registry.add_log(job.job_id, "error", "Conversion timed out")
        raise http_error(504, "JOB_TIMEOUT", "Conversion timed out.") from exc
    except FilteringError as exc:
        job_registry.update_status(job.job_id, "failed")
        job_registry.add_log(job.job_id, "error", str(exc))
        raise http_error(422, "PATH_OR_METHOD_NOT_FOUND", str(exc)) from exc
    except ValidationFailure as exc:
        job_registry.update_status(job.job_id, "failed")
        job_registry.add_log(job.job_id, "error", str(exc))
        raise http_error(422, "OPENAPI_VALIDATION_FAILED", str(exc)) from exc
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        job_registry.update_status(job.job_id, "failed")
        job_registry.add_log(job.job_id, "error", "YAML syntax error")
        raise http_error(400, "YAML_SYNTAX_ERROR", "Failed to parse YAML content.", details={"error": str(exc)}) from exc
    except FileNotFoundError as exc:
        job_registry.update_status(job.job_id, "failed")
        job_registry.add_log(job.job_id, "error", "Spec file missing")
        raise http_error(404, "JOB_NOT_FOUND", "Uploaded spec is missing.") from exc
    except Exception as exc:
        job_registry.update_status(job.job_id, "failed")
        job_registry.add_log(job.job_id, "error", "Unexpected conversion error")
        raise http_error(500, "INTERNAL_ERROR", "Unexpected conversion error.") from exc

    duration_ms = int((time.monotonic() - start_time) * 1000)
    metrics = JobMetrics(
        duration_ms=duration_ms,
        rows=result["rows"],
        validate_enabled=payload.validate,
        format=fmt,
    )
    job_registry.set_metrics(job.job_id, metrics)
    job_registry.set_output(job.job_id, result["output_path"], result["output_filename"])
    job_registry.update_status(job.job_id, "succeeded")
    job_registry.add_log(job.job_id, "info", "Conversion completed")

    return ConvertResponse(
        job_id=job.job_id,
        status="succeeded",
        rows=result["rows"],
        download_url=f"/api/download/{job.job_id}",
    )


@app.get("/api/job/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str) -> JobStatusResponse:
    """Return current status for a conversion job."""

    job = job_registry.get_job(job_id)
    if not job:
        raise http_error(404, "JOB_NOT_FOUND", "Job not found.")

    download_url = f"/api/download/{job.job_id}" if job.output_path else None
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        logs=job.logs,
        metrics=job.metrics,
        download_url=download_url,
    )


@app.get("/api/download/{job_id}")
async def download(job_id: str) -> FileResponse:
    """Download a completed conversion artifact."""

    job = job_registry.get_job(job_id)
    if not job or not job.output_path:
        raise http_error(404, "JOB_NOT_FOUND", "Job output not found.")
    if not job.output_path.exists():
        raise http_error(404, "JOB_NOT_FOUND", "Job output not found.")

    media_type = "application/octet-stream"
    if job.output_path.suffix == ".xlsx":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif job.output_path.suffix == ".zip":
        media_type = "application/zip"

    return FileResponse(path=str(job.output_path), filename=job.output_filename, media_type=media_type)


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str) -> Dict[str, str]:
    """Delete job artifacts and remove job state."""

    job = job_registry.delete_job(job_id)
    if not job:
        raise http_error(404, "JOB_NOT_FOUND", "Job not found.")

    if job.output_path and job.output_path.exists():
        job.output_path.unlink(missing_ok=True)

    upload_root = ensure_root()
    upload_dir = upload_root / safe_component_name(job.upload_id, fallback=job.upload_id)
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)

    return {"status": "deleted"}


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service status and version metadata."""

    logger.debug("Health check requested")
    return HealthResponse(status="ok", version=settings.app_version, git_sha=settings.git_sha)


logger.info("Backend service initialised", extra={"event": "SERVICE_START"})
