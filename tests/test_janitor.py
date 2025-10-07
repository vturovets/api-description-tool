"""Tests for janitor cleanup logic."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from web.backend import janitor
from web.backend.services import storage


@pytest.fixture()
def _patched_root(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    monkeypatch.setattr(storage, "UPLOAD_ROOT", root)
    yield root


def test_purge_expired_removes_old_directories(_patched_root, caplog, monkeypatch):
    """Old upload directories should be removed while newer ones remain."""

    monkeypatch.setattr(janitor.storage, "UPLOAD_ROOT", storage.UPLOAD_ROOT)

    recent_dir = storage.ensure_upload_dir("recent")
    old_dir = storage.ensure_upload_dir("old")

    now = datetime.now(timezone.utc)
    recent_time = (now - timedelta(minutes=10)).timestamp()
    old_time = (now - timedelta(minutes=90)).timestamp()

    os.utime(recent_dir, (recent_time, recent_time))
    os.utime(old_dir, (old_time, old_time))

    caplog.set_level("INFO")
    removed = janitor.purge_expired(ttl_min=30, now=now)

    assert removed == 1
    assert recent_dir.exists()
    assert not old_dir.exists()
    assert any(record.__dict__.get("event") == "JANITOR_DELETE" for record in caplog.records)
