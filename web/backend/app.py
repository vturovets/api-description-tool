"""FastAPI application setup for the API Description Tool web backend."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI

from .config import get_settings
from .janitor import purge_expired
from .models import HealthResponse


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


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service status and version metadata."""

    logger.debug("Health check requested")
    return HealthResponse(status="ok", version=settings.app_version, git_sha=settings.git_sha)


logger.info("Backend service initialised", extra={"event": "SERVICE_START"})
