"""Lưu/nạp cấu hình JSON trong thư mục dữ liệu người dùng."""
import json

from . import paths
from .exceptions import ConfigError


BASE_DIR = paths.user_data_dir()
CONFIG_DIR = paths.config_dir()
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_SETTINGS_FILE = CONFIG_DIR / "default_settings.json"
LEGACY_SETTINGS_FILE = paths.legacy_config_dir() / "settings.json"

_DEFAULT_DATA = {
    "geometry": None,
    "tab": 0,
    "logging_level": "INFO",
    "devices": {},
}


def _bundle_config(name: str):
    """Wrapper giữ tương thích test/call-site cũ."""
    return paths.bundled_config_file(name)


def _installed_config(name: str):
    return paths.installed_config_file(name)


def _default_candidates():
    """Ưu tiên bản runtime, rồi bundle onefile, cuối cùng config của source/install."""
    return (
        DEFAULT_SETTINGS_FILE,
        _bundle_config("default_settings.json"),
        _installed_config("default_settings.json"),
    )


def _defaults() -> dict:
    for candidate in _default_candidates():
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


def _copy_default_to_runtime() -> None:
    if DEFAULT_SETTINGS_FILE.exists():
        return
    for candidate in (
        _bundle_config("default_settings.json"),
        _installed_config("default_settings.json"),
    ):
        if candidate is None:
            continue
        try:
            if candidate.exists():
                DEFAULT_SETTINGS_FILE.write_text(
                    candidate.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                return
        except OSError:
            continue


def _migrate_legacy_settings() -> bool:
    """Copy settings cũ cạnh source/exe sang user-data nếu hợp lệ; không xóa bản cũ."""
    if SETTINGS_FILE.exists():
        return False
    legacy = LEGACY_SETTINGS_FILE
    try:
        if not legacy.exists() or legacy.resolve() == SETTINGS_FILE.resolve():
            return False
        with open(legacy, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        save_settings(data)
        return True
    except (OSError, ValueError):
        return False


def ensure_config() -> None:
    """Khởi tạo config runtime và migrate settings cũ một lần nếu có."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _copy_default_to_runtime()
        if not SETTINGS_FILE.exists() and not _migrate_legacy_settings():
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
