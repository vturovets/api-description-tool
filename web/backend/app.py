"""FastAPI application setup for the API Description Tool web backend."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from fastapi import FastAPI, File, UploadFile

from .config import get_settings
from .errors import http_error
from .janitor import purge_expired
from .models import HealthResponse, UploadResponse
from .services.storage import ensure_upload_dir


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


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service status and version metadata."""

    logger.debug("Health check requested")
    return HealthResponse(status="ok", version=settings.app_version, git_sha=settings.git_sha)


logger.info("Backend service initialised", extra={"event": "SERVICE_START"})
