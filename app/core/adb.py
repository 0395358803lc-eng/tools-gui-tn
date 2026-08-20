"""Wrapper lệnh adb cơ bản - chỉ chứa thao tác với thiết bị Android.

Phân tích UI hierarchy (uiautomator dump) nằm ở module `uiautomator`.
"""
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .exceptions import ADBError

ENV_PATHS = ["ANDROID_HOME", "ANDROID_SDK_ROOT"]

# Ẩn cửa sổ console của tiến trình con khi chạy từ ứng dụng GUI (tránh flash màn hình đen/xanh)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Fallback mặc định cho máy đã cài Android SDK (nếu biến môi trường không có)
FALLBACK_SDK = Path(os.environ.get("USERPROFILE", "C:/Users/Admin")) / "AppData/Local/Android/Sdk"


@dataclass(frozen=True)
class CommandResult:
    """Kết quả thực thi lệnh host, giữ riêng stdout/stderr và trạng thái lỗi."""

    args: tuple[str, ...]
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    not_found: bool = False

    @property
    def output(self) -> str:
        return (self.stdout or "") + (self.stderr or "")

    @property
    def ok(self) -> bool:
        return not self.timed_out and not self.not_found and self.returncode == 0

    def raise_for_error(self) -> None:
        if self.ok:
            return
        command = " ".join(self.args)
        if self.not_found:
            raise ADBError(f"Không tìm thấy chương trình khi chạy lệnh: {command}")
        if self.timed_out:
            raise ADBError(f"Lệnh hết thời gian chờ: {command}")
        detail = (self.stderr or self.stdout or "không có output").strip()
        raise ADBError(
            f"Lệnh thất bại (exit={self.returncode}): {command}: {detail[:500]}")


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


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_command(args: Sequence[str], timeout: int = 30) -> CommandResult:
    """Chạy lệnh và luôn trả về kết quả có cấu trúc, không nuốt loại lỗi."""
    normalized = tuple(str(arg) for arg in args)
    try:
        proc = subprocess.run(
            list(normalized),
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return CommandResult(
            args=normalized,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
    except FileNotFoundError as exc:
        return CommandResult(
            args=normalized,
            returncode=None,
            stderr=str(exc),
            not_found=True,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            args=normalized,
            returncode=None,
            stdout=_as_text(exc.stdout),
            stderr=_as_text(exc.stderr),
            timed_out=True,
        )


def _run(args: list[str], timeout: int = 30, *, check: bool = False) -> str:
    """Wrapper tương thích cũ; `check=True` để lỗi lệnh được raise thành ADBError."""
    result = run_command(args, timeout=timeout)
    if check:
        result.raise_for_error()
    return result.output


def devices() -> list[str]:
    out = _run([adb_path(), "devices"])
    serials = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def shell(serial: str, cmd: str, timeout: int = 30, *, check: bool = False) -> str:
    """Chạy command string cố định trên Android shell.

    Với dữ liệu do người dùng nhập, ưu tiên `shell_args()` để không tự ghép/escape shell.
    """
    return _run([adb_path(), "-s", serial, "shell", cmd], timeout=timeout, check=check)


def shell_args(serial: str, args: Sequence[str], timeout: int = 30, *, check: bool = False) -> str:
    """Chạy Android shell bằng argument tách biệt, phù hợp cho dữ liệu người dùng."""
    cmd = [adb_path(), "-s", serial, "shell", *(str(arg) for arg in args)]
    return _run(cmd, timeout=timeout, check=check)


def exec_out(serial: str, cmd: str, timeout: int = 30, *, check: bool = False) -> str:
    return _run([adb_path(), "-s", serial, "exec-out", cmd], timeout=timeout, check=check)


def is_boot_completed(serial: str) -> bool:
    out = shell(serial, "getprop sys.boot_completed", timeout=10).strip()
    return out == "1"


def booted_serials() -> list[str]:
    return [s for s in devices() if is_boot_completed(s)]


# ---------------------------------------------------------------------------
# Điều khiển UI
# ---------------------------------------------------------------------------

def tap(serial: str, x: int, y: int) -> None:
    shell(serial, f"input tap {x} {y}", timeout=15, check=True)


def swipe(serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
    shell(serial, f"input swipe {x1} {y1} {x2} {y2} {duration_ms}", timeout=15, check=True)


def input_text(serial: str, text: str) -> None:
    """Nhập text bằng argument riêng thay vì nội suy trực tiếp vào shell command."""
    shell_args(serial, ["input", "text", text], timeout=15, check=True)


def keyevent(serial: str, key: str) -> None:
    shell(serial, f"input keyevent {key}", timeout=15, check=True)


def back(serial: str) -> None:
    keyevent(serial, "KEYCODE_BACK")


def home(serial: str) -> None:
    keyevent(serial, "KEYCODE_HOME")


def emu_kill(serial: str, timeout: int = 15) -> None:
    """Tắt emulator từ host: adb -s <serial> emu kill."""
    _run([adb_path(), "-s", serial, "emu", "kill"], timeout=timeout, check=True)


# ---------------------------------------------------------------------------
# Thông tin activity
# ---------------------------------------------------------------------------

def wait_for_activity(serial: str, activity_part: str, timeout: float = 20.0,
                      cancelled: Optional[Callable[[], bool]] = None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cancelled is not None and cancelled():
            return False
        out = shell(serial, "dumpsys activity activities", timeout=20)
        if activity_part in out:
            return True
        if cancelled is not None and cancelled():
            return False
        time.sleep(1.0)
    return False


def top_activity(serial: str) -> str:
    out = shell(serial, "dumpsys activity activities", timeout=20)
    m = re.search(r"topResumedActivity=ActivityRecord\{[^ ]* \w+ ([\w./]+)", out)
    return m.group(1) if m else ""
