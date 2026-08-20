"""Tests cho đường dẫn install/user-data."""
from pathlib import Path

from app.core import paths


def test_user_data_dir_honors_explicit_override(tmp_path, monkeypatch):
    override = tmp_path / "custom-data"
    monkeypatch.setenv(paths.DATA_DIR_ENV, str(override))
    assert paths.user_data_dir() == override.resolve()


def test_windows_user_data_dir_uses_localappdata(tmp_path, monkeypatch):
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert paths.user_data_dir() == tmp_path / paths.APP_DIR_NAME
    assert paths.config_dir() == tmp_path / paths.APP_DIR_NAME / "config"
    assert paths.logs_dir() == tmp_path / paths.APP_DIR_NAME / "logs"


def test_non_windows_user_data_dir_uses_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv(paths.DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    assert paths.user_data_dir() == tmp_path / paths.APP_DIR_NAME


def test_bundle_dir_returns_none_without_meipass(monkeypatch):
    monkeypatch.delattr(paths.sys, "_MEIPASS", raising=False)
    assert paths.bundle_dir() is None


def test_bundled_config_file_uses_meipass(tmp_path, monkeypatch):
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.bundled_config_file("default_settings.json") == (
        Path(tmp_path) / "config" / "default_settings.json"
    )
