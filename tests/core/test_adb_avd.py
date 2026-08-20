"""Test phát hiện đường dẫn adb và thông tin AVD."""
from app.core import adb


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


def test_emu_kill_builds_command(monkeypatch):
    captured = {}

    def fake_run(args, timeout=30):
        captured["args"] = args
        return ""

    monkeypatch.setattr(adb, "_run", fake_run)
    adb.emu_kill("emulator-5554")
    assert captured["args"] == [adb.adb_path(), "-s", "emulator-5554", "emu", "kill"]


def test_devices_parsing(monkeypatch):
    fake_out = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\toffline\n"
    monkeypatch.setattr(adb, "_run", lambda args, timeout=30: fake_out)
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
