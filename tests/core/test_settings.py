"""Test settings - dùng thư mục tạm để tránh ảnh hưởng config thật."""
import json

import pytest

from app.core import settings
from app.core.exceptions import ConfigError


@pytest.fixture()
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "DEFAULT_SETTINGS_FILE", tmp_path / "default_settings.json")
    settings.ensure_config()
    return tmp_path


def test_ensure_config_creates_files(isolated_settings):
    settings.ensure_config()
    assert isolated_settings.exists()
    assert (isolated_settings / "settings.json").exists()


def test_defaults_when_no_file(isolated_settings):
    assert settings._defaults()["tab"] == 0
    assert settings._defaults()["devices"] == {}


def test_set_get_device_config(isolated_settings):
    settings.set_device_config("avd_a", {"numbers": "12052452095", "interval": 3})
    cfg = settings.get_device_config("avd_a")
    assert cfg["numbers"] == "12052452095"
    assert cfg["interval"] == 3
    assert settings.get_device_config("avd_b") == {}


def test_default_settings_override(isolated_settings):
    (isolated_settings / "default_settings.json").write_text(
        json.dumps({"logging_level": "DEBUG", "tab": 2}), encoding="utf-8")
    assert settings._defaults()["logging_level"] == "DEBUG"
    assert settings._defaults()["tab"] == 2


def test_window_state_roundtrip(isolated_settings):
    settings.set_window_state("QUJDRA==", 1)
    state = settings.get_window_state()
    assert state["geometry"] == "QUJDRA=="
    assert state["tab"] == 1


def test_ensure_config_reports_invalid_config_directory(tmp_path, monkeypatch):
    blocked = tmp_path / "config-is-a-file"
    blocked.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(settings, "CONFIG_DIR", blocked)
    monkeypatch.setattr(settings, "SETTINGS_FILE", blocked / "settings.json")
    monkeypatch.setattr(settings, "DEFAULT_SETTINGS_FILE", blocked / "default_settings.json")

    with pytest.raises(ConfigError, match="Không khởi tạo được cấu hình"):
        settings.ensure_config()


def test_load_settings_reports_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "DEFAULT_SETTINGS_FILE", tmp_path / "default_settings.json")
    (tmp_path / "settings.json").write_text("{invalid json", encoding="utf-8")

    with pytest.raises(ConfigError, match="Đọc settings.json lỗi"):
        settings.load_settings()


def test_ensure_config_uses_builtin_defaults_when_default_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "DEFAULT_SETTINGS_FILE", tmp_path / "missing-default.json")
    monkeypatch.setattr(settings, "_bundle_config", lambda name: None)

    settings.ensure_config()
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["tab"] == 0
    assert saved["devices"] == {}
