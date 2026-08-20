"""Tests cho preflight local/device."""
from app.core import adb
from app.core import preflight as pf
from app.core.uiautomator import UiDump


def test_validate_broadcast_inputs_accepts_valid_data(tmp_path):
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"fake")

    result = pf.validate_broadcast_inputs(
        ["84987654321"],
        "hello",
        [str(image)],
        5,
    )

    assert result.ok is True
    assert result.errors == []


def test_validate_broadcast_inputs_rejects_invalid_phone_and_missing_content():
    result = pf.validate_broadcast_inputs(["abc", "123"], "", [], 0)

    assert result.ok is False
    codes = {check.code for check in result.errors}
    assert "phones_present" in codes
    assert "phones_valid" in codes
    assert "content_present" in codes


def test_duplicate_phones_are_warning_not_hard_failure():
    result = pf.validate_broadcast_inputs(
        ["84987654321", "84987654321"],
        "hello",
        [],
        5,
    )

    assert result.ok is True
    assert [warning.code for warning in result.warnings] == ["phones_unique"]


def test_missing_or_bad_image_is_hard_failure(tmp_path):
    bad = tmp_path / "file.txt"
    bad.write_text("x", encoding="utf-8")

    result = pf.validate_broadcast_inputs(
        ["84987654321"],
        "",
        [str(bad), str(tmp_path / "missing.jpg")],
        5,
    )

    codes = {check.code for check in result.errors}
    assert "images_exist" in codes
    assert "image_types" in codes


def test_device_preflight_stops_when_adb_unavailable(monkeypatch):
    monkeypatch.setattr(
        pf.adb,
        "run_command",
        lambda *args, **kwargs: adb.CommandResult(
            args=("adb", "version"),
            returncode=None,
            not_found=True,
        ),
    )

    result = pf.run_device_preflight("emulator-5554")

    assert result.ok is False
    assert [check.code for check in result.checks] == ["adb_available"]


def test_device_preflight_stops_when_device_offline(monkeypatch):
    monkeypatch.setattr(
        pf.adb,
        "run_command",
        lambda *args, **kwargs: adb.CommandResult(args=("adb", "version"), returncode=0),
    )
    monkeypatch.setattr(pf.adb, "devices", lambda: [])

    result = pf.run_device_preflight("emulator-5554")

    assert result.ok is False
    assert [check.code for check in result.checks] == ["adb_available", "device_online"]


def test_device_preflight_full_success_with_unicode_warning(monkeypatch):
    monkeypatch.setattr(
        pf.adb,
        "run_command",
        lambda *args, **kwargs: adb.CommandResult(args=("adb", "version"), returncode=0),
    )
    monkeypatch.setattr(pf.adb, "devices", lambda: ["emulator-5554"])
    monkeypatch.setattr(pf.adb, "is_boot_completed", lambda serial: True)

    def fake_shell_args(serial, args, timeout=30, check=False):
        if args[:2] == ["pm", "path"]:
            return "package:/data/app/com.whatsapp/base.apk"
        if args[:3] == ["ime", "list", "-s"]:
            return "com.android.inputmethod/.LatinIME"
        return ""

    monkeypatch.setattr(pf.adb, "shell_args", fake_shell_args)
    monkeypatch.setattr(
        pf.ui,
        "ui_dump",
        lambda *args, **kwargs: UiDump(serial="emulator-5554", xml="<hierarchy/>", nodes=[]),
    )

    result = pf.run_device_preflight("emulator-5554", require_unicode=True)

    assert result.ok is True
    assert [warning.code for warning in result.warnings] == ["adb_keyboard"]
