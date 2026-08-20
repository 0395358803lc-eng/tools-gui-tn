"""Đường dẫn cài đặt và dữ liệu runtime của ứng dụng."""
import os
import sys
from pathlib import Path

APP_DIR_NAME = "ToolsGuiTinWhatsApp"
DATA_DIR_ENV = "TOOLS_GUI_TN_DATA_DIR"


def install_dir() -> Path:
    """Thư mục chứa exe khi frozen, hoặc root dự án khi chạy source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path | None:
    """Thư mục tạm PyInstaller onefile nếu có."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def user_data_dir() -> Path:
    """Thư mục ghi runtime, ưu tiên override tường minh cho test/portable setup."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_DIR_NAME
        return Path.home() / "AppData" / "Local" / APP_DIR_NAME

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / APP_DIR_NAME
    return Path.home() / ".local" / "share" / APP_DIR_NAME


def config_dir() -> Path:
    return user_data_dir() / "config"


def logs_dir() -> Path:
    return user_data_dir() / "logs"


def reports_dir() -> Path:
    return user_data_dir() / "reports"


def legacy_config_dir() -> Path:
    """Vị trí settings cũ cạnh source/exe, chỉ dùng cho migration đọc một lần."""
    return install_dir() / "config"


def bundled_config_file(name: str) -> Path | None:
    root = bundle_dir()
    if root is None:
        return None
    return root / "config" / name


def installed_config_file(name: str) -> Path:
    return install_dir() / "config" / name
