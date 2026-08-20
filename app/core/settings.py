"""Lưu/nạp cấu hình JSON - tự khởi tạo mặc định, khôi phục cấu hình riêng từng thiết bị."""
import json
import sys
from pathlib import Path

from .exceptions import ConfigError


def _base_dir() -> Path:
    """Thư mục gốc chứa config: cạnh exe khi đóng băng, nếu không là thư mục dự án."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _bundle_config(name: str) -> Path | None:
    """Đường dẫn file cấu hình trong bundle _MEIPASS khi chạy dạng exe onefile."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "config" / name
    return None


BASE_DIR = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_SETTINGS_FILE = CONFIG_DIR / "default_settings.json"

_DEFAULT_DATA = {
    "geometry": None,
    "tab": 0,
    "logging_level": "INFO",
    "devices": {},
}


def _defaults() -> dict:
    # Ưu tiên bản mặc định cạnh exe, fallback sang bản trong bundle (khi exe onefile)
    for candidate in (DEFAULT_SETTINGS_FILE, _bundle_config("default_settings.json")):
        if candidate is None:
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {**_DEFAULT_DATA, **data}
        except (OSError, ValueError):
            continue
    return dict(_DEFAULT_DATA)


def ensure_config() -> None:
    """Tạo thư mục config/ và settings.json (nếu chưa có) với giá trị mặc định.

    Khi chạy exe onefile: sao chép bản `default_settings.json` từ bundle sang cạnh exe
    nếu chưa có, để thư mục config cạnh exe luôn đủ cả 2 file.
    """
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not DEFAULT_SETTINGS_FILE.exists():
            bundled = _bundle_config("default_settings.json")
            if bundled is not None and bundled.exists():
                DEFAULT_SETTINGS_FILE.write_text(
                    bundled.read_text(encoding="utf-8"), encoding="utf-8")
        if not SETTINGS_FILE.exists():
            save_settings(_defaults())
    except OSError as e:
        raise ConfigError(f"Không khởi tạo được cấu hình: {e}") from e


def load_settings() -> dict:
    data = _defaults()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            data = _merge(data, saved)
    except (OSError, ValueError) as e:
        raise ConfigError(f"Đọc settings.json lỗi: {e}") from e
    return data


def save_settings(data: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise ConfigError(f"Ghi settings.json lỗi: {e}") from e


def get_device_config(avd_name: str) -> dict:
    return load_settings().get("devices", {}).get(avd_name, {})


def set_device_config(avd_name: str, cfg: dict) -> None:
    data = load_settings()
    data.setdefault("devices", {})
    data["devices"][avd_name] = cfg
    save_settings(data)


def get_window_state() -> dict:
    data = load_settings()
    return {"geometry": data.get("geometry"), "tab": data.get("tab", 0)}


def set_window_state(geometry: str | None, tab: int) -> None:
    data = load_settings()
    data["geometry"] = geometry
    data["tab"] = tab
    save_settings(data)


def get_logging_level() -> str:
    return str(load_settings().get("logging_level", "INFO"))


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# Khởi tạo config mặc định ngay khi import (đảm bảo config/settings.json luôn tồn tại)
try:
    ensure_config()
except ConfigError:
    pass
