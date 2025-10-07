"""Tests for backend storage helpers."""
from __future__ import annotations

from web.backend.services import storage


def test_ensure_upload_dir_creates_directory(tmp_path, monkeypatch):
    """Ensure upload directories are created under the configured root."""

    root = tmp_path / "uploads"
    monkeypatch.setattr(storage, "UPLOAD_ROOT", root)

    upload_dir = storage.ensure_upload_dir("../strange-id")

    assert upload_dir.parent == root
    assert upload_dir.exists()
    assert all(part not in {"..", ""} for part in upload_dir.parts)


def test_resolve_upload_path_sanitises_filename(tmp_path, monkeypatch):
    """Sanitise filenames and constrain them to the upload directory."""

    root = tmp_path / "uploads"
    monkeypatch.setattr(storage, "UPLOAD_ROOT", root)

    resolved = storage.resolve_upload_path("upload-1", "../../evil?.yaml")

    assert resolved.parent.exists()
    assert resolved.parent == root / storage.safe_component_name("upload-1", fallback="fallback")
    assert resolved.name == "evil_.yaml"


def test_safe_filename_fallback_when_empty():
    """Empty filenames should fall back to the provided default."""

    assert storage.safe_filename("", fallback="default.txt") == "default.txt"
