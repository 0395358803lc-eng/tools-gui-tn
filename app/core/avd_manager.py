"""Quản lý máy ảo Android Studio (AVD) qua lớp AVDController.

Gồm: danh sách AVD, khởi động ẩn/có màn hình, trạng thái, tắt máy.
"""
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import adb
from .adb import CREATE_NO_WINDOW

HEADLESS_FLAGS = ["-no-window", "-no-audio", "-no-boot-anim", "-no-snapshot",
                  "-gpu", "swiftshader_indirect", "-no-metrics"]


@dataclass
class AVDInfo:
    name: str
    device: str = ""
    target: str = ""
    path: str = ""
    serial: str = ""          # serial adb nếu đang chạy (emulator-XXXX)
    status: str = "Đang dừng"  # Đang dừng / Đang khởi động / Đang chạy
    headless: bool = False


class EmulatorProcess:
    """Theo dõi tiến trình emulator đã khởi động."""

    def __init__(self, avd_name: str, proc: subprocess.Popen):
        self.avd_name = avd_name
        self.proc = proc

    @property
    def is_alive(self) -> bool:
        return self.proc.poll() is None

    def terminate(self) -> None:
        if self.is_alive:
            self.proc.terminate()


def _fill_info(avd: AVDInfo, avd_root) -> None:
    """Đọc thêm model/target từ file .ini và config.ini của AVD."""
    avd_root = Path(avd_root)
    ini = avd_root / f"{avd.name}.ini"
    try:
        content = ini.read_text(encoding="utf-8")
        m = re.search(r"path\s*=\s*(.+)", content)
        if m:
            avd.path = m.group(1).strip().strip('"')
    except (OSError, ValueError):
        pass
    config = avd_root / f"{avd.name}.avd" / "config.ini"
    try:
        content = config.read_text(encoding="utf-8")
        for key in ("hw.device.name", "hw.device.manufacturer", "image.sysdir.1"):
            m = re.search(rf"{re.escape(key)}\s*=\s*(.+)", content)
            if m:
                val = m.group(1).strip()
                if key == "hw.device.name":
                    avd.device = val
                elif key == "hw.device.manufacturer":
                    avd.device = f"{val} {avd.device}".strip()
                else:
                    avd.target = val
    except (OSError, ValueError):
        pass


def _map_serial_by_emulator_name() -> dict[str, str]:
    """Map tên AVD -> serial (qua emu avd name hoặc getprop avd_name)."""
    result: dict[str, str] = {}
    for serial in adb.devices():
        name = ""
        out = adb._run([adb.adb_path(), "-s", serial, "emu", "avd", "name"], timeout=10)
        first = (out or "").splitlines()
        if first:
            name = first[0].strip()
        if not name or name.lower().startswith("error"):
            name = adb.shell(serial, "getprop ro.kernel.qemu.avd_name", timeout=10).strip()
        if name:
            result[name] = serial
    return result


def _emulator_command_lines() -> list[str]:
    """Lấy toàn bộ command line của tiến trình emulator.exe đang chạy."""
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='emulator.exe'", "get", "CommandLine"],
            capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW,
        ).stdout
        lines = [ln.strip() for ln in (out or "").splitlines() if "-avd" in ln]
        if lines:
            return lines
    except Exception:  # noqa: BLE001 - wmic có thể không tồn tại
        pass
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"name='emulator.exe'\" | "
             "Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW,
        ).stdout
        return [ln.strip() for ln in (out or "").splitlines() if "-avd" in ln]
    except Exception:  # noqa: BLE001
        return []


class AVDController:
    """Điều khiển lifecycle của toàn bộ máy ảo AVD."""

    def __init__(self):
        self._processes: dict[str, EmulatorProcess] = {}

    # ------------------------------------------------------------------
    # Danh sách & trạng thái
    # ------------------------------------------------------------------
    def list_avds(self, cmd_lines: Optional[list[str]] = None) -> list[AVDInfo]:
        """Đọc danh sách AVD + trạng thái.

        `cmd_lines` nên được truyền từ ngoài (lấy 1 lần) để tránh gọi wmic/PowerShell
        nhiều lần trong cùng một chu kỳ refresh.
        """
        out = adb._run([adb.emulator_path(), "-list-avds"])
        names = [ln.strip() for ln in out.splitlines() if ln.strip()]
        avds = [AVDInfo(name=n) for n in names]

        avd_root = Path.home() / ".android" / "avd"
        serial_by_emulator = _map_serial_by_emulator_name()
        if cmd_lines is None:
            cmd_lines = self.emulator_command_lines()

        for avd in avds:
            avd.serial = serial_by_emulator.get(avd.name, "")
            if avd.serial:
                if adb.is_boot_completed(avd.serial):
                    avd.status = "Đang chạy"
                else:
                    avd.status = "Đang khởi động"
            avd.headless = self.is_running_headless(avd.name, cmd_lines)
            _fill_info(avd, avd_root)
        return avds

    # ------------------------------------------------------------------
    # Khởi động / tắt
    # ------------------------------------------------------------------
    def launch(self, avd_name: str, headless: bool = True,
               extra_flags: Optional[list[str]] = None) -> EmulatorProcess:
        """Khởi động AVD. headless=True -> chạy ẩn không màn hình (`-no-window`)."""
        cmd = [adb.emulator_path(), "-avd", avd_name]
        if headless:
            cmd.extend(HEADLESS_FLAGS)
        else:
            cmd.extend(["-no-audio", "-no-boot-anim"])
        if extra_flags:
            cmd.extend(extra_flags)

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=CREATE_NO_WINDOW)
        ep = EmulatorProcess(avd_name, proc)
        self._processes[avd_name] = ep
        return ep

    def kill(self, avd_name: str, serial: str = "") -> None:
        if serial:
            adb.emu_kill(serial)
        ep = self._processes.get(avd_name)
        if ep and ep.is_alive:
            ep.terminate()
            return
        if not serial:
            for s in adb.devices():
                name = adb.shell(s, "getprop ro.kernel.qemu.avd_name", timeout=10).strip()
                if name == avd_name:
                    adb.emu_kill(s)
                    return

    # ------------------------------------------------------------------
    # Chế độ chạy
    # ------------------------------------------------------------------
    def emulator_command_lines(self) -> list[str]:
        return _emulator_command_lines()

    def is_running_headless(self, avd_name: str, cmd_lines: Optional[list[str]] = None) -> bool:
        """Kiểm tra emulator của AVD đang chạy có flag -no-window hay không.

        Khớp chính xác `-avd <tên>` (ngăn nhầm AVD có tên tương tự).
        """
        if cmd_lines is None:
            cmd_lines = _emulator_command_lines()
        rx = re.compile(rf"-avd\s+{re.escape(avd_name)}(?:\s|$)")
        for line in cmd_lines:
            if rx.search(line) and "-no-window" in line:
                return True
        return False

    # ------------------------------------------------------------------
    # Chờ boot
    # ------------------------------------------------------------------
    def wait_boot(self, serial: str, timeout: float = 300.0, interval: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if serial in adb.devices() and adb.is_boot_completed(serial):
                return True
            time.sleep(interval)
        return False

    def wait_serial(self, avd_name: str, timeout: float = 180.0, interval: float = 2.0) -> str:
        """Chờ tới khi tìm được serial adb cho AVD."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for s in adb.devices():
                name = adb.shell(s, "getprop ro.kernel.qemu.avd_name", timeout=10).strip()
                if name == avd_name:
                    return s
            time.sleep(interval)
        return ""


# Singleton dùng chung cho toàn ứng dụng
manager = AVDController()
