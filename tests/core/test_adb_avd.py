"""Test phát hiện đường dẫn adb, thực thi lệnh và thông tin AVD."""
import subprocess

import pytest

from app.core import adb
from app.core.exceptions import ADBError


def test_adb_path_with_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path))
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    assert adb.adb_path() == str(tmp_path / "platform-tools" / "adb.exe")
    assert adb.emulator_path() == str(tmp_path / "emulator" / "emulator.exe")


def test_adb_path_fallback_no_env(monkeypatch, tmp_path):
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    monkeypatch.setattr(adb, "FALLBACK_SDK", tmp_path / "khong_co_sdk")
    assert adb.adb_path() == "adb"


def test_run_command_success(monkeypatch):
    completed = subprocess.CompletedProcess(
        args=["adb", "devices"], returncode=0, stdout="ok\n", stderr="")
    monkeypatch.setattr(adb.subprocess, "run", lambda *args, **kwargs: completed)

    result = adb.run_command(["adb", "devices"])

    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout == "ok\n"
    assert result.stderr == ""
    assert result.output == "ok\n"


def test_run_command_nonzero_is_explicit(monkeypatch):
    completed = subprocess.CompletedProcess(
        args=["adb", "bad"], returncode=1, stdout="", stderr="bad command")
    monkeypatch.setattr(adb.subprocess, "run", lambda *args, **kwargs: completed)

    result = adb.run_command(["adb", "bad"])

    assert result.ok is False
    assert result.returncode == 1
    assert result.stderr == "bad command"
    with pytest.raises(ADBError, match="exit=1"):
        result.raise_for_error()


def test_run_command_not_found_is_explicit(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("adb missing")

    monkeypatch.setattr(adb.subprocess, "run", fake_run)
    result = adb.run_command(["adb", "devices"])

    assert result.ok is False
    assert result.not_found is True
    assert result.returncode is None
    with pytest.raises(ADBError, match="Không tìm thấy"):
        result.raise_for_error()


def test_run_command_timeout_is_explicit(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["adb", "devices"], timeout=3, output="partial", stderr="slow")

    monkeypatch.setattr(adb.subprocess, "run", fake_run)
    result = adb.run_command(["adb", "devices"], timeout=3)

    assert result.ok is False
    assert result.timed_out is True
    assert result.stdout == "partial"
    assert result.stderr == "slow"
    with pytest.raises(ADBError, match="hết thời gian"):
        result.raise_for_error()


def test_run_check_raises_on_failure(monkeypatch):
    result = adb.CommandResult(args=("adb", "bad"), returncode=2, stderr="failed")
    monkeypatch.setattr(adb, "run_command", lambda args, timeout=30: result)

    with pytest.raises(ADBError, match="exit=2"):
        adb._run(["adb", "bad"], check=True)


def test_emu_kill_builds_command(monkeypatch):
    captured = {}

    def fake_run(args, timeout=30, **kwargs):
        captured["args"] = args
        captured["check"] = kwargs.get("check")
        return ""

    monkeypatch.setattr(adb, "_run", fake_run)
    adb.emu_kill("emulator-5554")
    assert captured["args"] == [adb.adb_path(), "-s", "emulator-5554", "emu", "kill"]
    assert captured["check"] is True


def test_devices_parsing(monkeypatch):
    fake_out = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\toffline\n"
    monkeypatch.setattr(adb, "_run", lambda args, timeout=30, **kwargs: fake_out)
    assert adb.devices() == ["emulator-5554"]


def test_avd_fill_info(tmp_path):
    from app.core import avd_manager as am

    (tmp_path / "pixel.ini").write_text('path = C:\\android\\pixel.avd\n', encoding="utf-8")
    avd_dir = tmp_path / "pixel.avd"
    avd_dir.mkdir()
    (avd_dir / "config.ini").write_text(
        "hw.device.name = pixel_9\nhw.device.manufacturer = Google\n"
        "image.sysdir.1 = system-images/android-36/google_apis/x86_64\n",
        encoding="utf-8")

    avd = am.AVDInfo(name="pixel")
    am._fill_info(avd, tmp_path)
    assert avd.device == "Google pixel_9"
    assert "google_apis" in avd.target
    assert "android" in avd.path


def test_is_running_headless_matching():
    from app.core import avd_manager as am

    ctrl = am.AVDController()
    cmd_lines = [
        'C:\\...\\emulator.exe -avd whatsapp_device_01 -no-window -no-audio',
        'C:\\...\\emulator.exe -avd whatsapp_device_010 -no-window',
        'C:\\...\\emulator.exe -avd whatsapp_device_02',
    ]
    assert ctrl.is_running_headless("whatsapp_device_01", cmd_lines) is True
    assert ctrl.is_running_headless("whatsapp_device_02", cmd_lines) is False
    assert ctrl.is_running_headless("whatsapp_device_010", cmd_lines) is True
