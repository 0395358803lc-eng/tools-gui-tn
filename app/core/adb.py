"""Wrapper lệnh adb cơ bản - chỉ chứa thao tác với thiết bị Android.

Phân tích UI hierarchy (uiautomator dump) nằm ở module `uiautomator`.
"""
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

ENV_PATHS = ["ANDROID_HOME", "ANDROID_SDK_ROOT"]

# Ẩn cửa sổ console của tiến trình con khi chạy từ ứng dụng GUI (tránh flash màn hình đen/xanh)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Fallback mặc định cho máy đã cài Android SDK (nếu biến môi trường không có)
FALLBACK_SDK = Path(os.environ.get("USERPROFILE", "C:/Users/Admin")) / "AppData/Local/Android/Sdk"


def _sdk_root() -> Optional[Path]:
    for key in ENV_PATHS:
        val = os.environ.get(key)
        if val:
            return Path(val)
    cand = FALLBACK_SDK
    if cand.is_dir():
        return cand
    return None


def adb_path() -> str:
    root = _sdk_root()
    if root:
        return str(root / "platform-tools" / "adb.exe")
    return "adb"


def emulator_path() -> str:
    root = _sdk_root()
    if root:
        return str(root / "emulator" / "emulator.exe")
    return "emulator"


def _run(args: list[str], timeout: int = 30) -> str:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              creationflags=CREATE_NO_WINDOW)
        return (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return ""
    except subprocess.TimeoutExpired:
        return ""


def devices() -> list[str]:
    out = _run([adb_path(), "devices"])
    serials = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def shell(serial: str, cmd: str, timeout: int = 30) -> str:
    return _run([adb_path(), "-s", serial, "shell", cmd], timeout=timeout)


def exec_out(serial: str, cmd: str, timeout: int = 30) -> str:
    return _run([adb_path(), "-s", serial, "exec-out", cmd], timeout=timeout)


def is_boot_completed(serial: str) -> bool:
    out = shell(serial, "getprop sys.boot_completed", timeout=10).strip()
    return out == "1"


def booted_serials() -> list[str]:
    return [s for s in devices() if is_boot_completed(s)]


# ---------------------------------------------------------------------------
# Điều khiển UI
# ---------------------------------------------------------------------------

def tap(serial: str, x: int, y: int) -> None:
    shell(serial, f"input tap {x} {y}", timeout=15)


def swipe(serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
    shell(serial, f"input swipe {x1} {y1} {x2} {y2} {duration_ms}", timeout=15)


def input_text(serial: str, text: str) -> None:
    shell(serial, f"input text {text}", timeout=15)


def keyevent(serial: str, key: str) -> None:
    shell(serial, f"input keyevent {key}", timeout=15)


def back(serial: str) -> None:
    keyevent(serial, "KEYCODE_BACK")


def home(serial: str) -> None:
    keyevent(serial, "KEYCODE_HOME")


def emu_kill(serial: str, timeout: int = 15) -> None:
    """Tắt emulator từ host: adb -s <serial> emu kill."""
    _run([adb_path(), "-s", serial, "emu", "kill"], timeout=timeout)


# ---------------------------------------------------------------------------
# Thông tin activity
# ---------------------------------------------------------------------------

def wait_for_activity(serial: str, activity_part: str, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        out = shell(serial, "dumpsys activity activities", timeout=20)
        if activity_part in out:
            return True
        time.sleep(1.0)
    return False


def top_activity(serial: str) -> str:
    out = shell(serial, "dumpsys activity activities", timeout=20)
    m = re.search(r"topResumedActivity=ActivityRecord\{[^ ]* \w+ ([\w./]+)", out)
    return m.group(1) if m else ""
