"""Regression tests cho nhập text WhatsApp/ADB, đặc biệt Unicode và ký tự shell."""
from app.core import adb
from app.core.whatsapp_bot import _Base


def test_type_text_preserves_special_characters_without_adbkeyboard(monkeypatch):
    controller = _Base("emulator-5554")
    monkeypatch.setattr(controller, "_is_adbkeyboard", lambda: False)
    captured = {}

    def fake_input_text(serial, text):
        captured["serial"] = serial
        captured["text"] = text

    monkeypatch.setattr(adb, "input_text", fake_input_text)
    text = "Xin chào! I'm here & A | B; <tag> 100% (ok)"

    controller.type_text(text)

    assert captured == {"serial": "emulator-5554", "text": text}


def test_type_text_empty_string_does_nothing(monkeypatch):
    controller = _Base("emulator-5554")
    monkeypatch.setattr(controller, "_is_adbkeyboard", lambda: False)
    called = []
    monkeypatch.setattr(adb, "input_text", lambda *args, **kwargs: called.append(args))

    controller.type_text("")

    assert called == []


def test_adbkeyboard_broadcast_preserves_exact_text(monkeypatch):
    controller = _Base("emulator-5554")
    captured = {}

    def fake_shell_args(serial, args, timeout=30, *, check=False):
        captured["serial"] = serial
        captured["args"] = args
        captured["timeout"] = timeout
        captured["check"] = check
        return "Broadcast completed"

    monkeypatch.setattr(adb, "shell_args", fake_shell_args)
    text = "Tiếng Việt: 'xin chào' & A|B; 100%"

    controller._broadcast_adbkeyboard(text)

    assert captured["serial"] == "emulator-5554"
    assert captured["args"][-1] == text
    assert captured["args"][:6] == ["am", "broadcast", "-a", "ADB_INPUT_TEXT", "--es", "msg"]
    assert captured["timeout"] == 10
    assert captured["check"] is True


def test_type_text_prefers_adbkeyboard_when_available(monkeypatch):
    controller = _Base("emulator-5554")
    monkeypatch.setattr(controller, "_is_adbkeyboard", lambda: True)
    broadcast = []
    fallback = []
    monkeypatch.setattr(controller, "_broadcast_adbkeyboard", broadcast.append)
    monkeypatch.setattr(adb, "input_text", lambda *args: fallback.append(args))

    controller.type_text("Xin chào")

    assert broadcast == ["Xin chào"]
    assert fallback == []


def test_input_text_uses_separate_shell_arguments(monkeypatch):
    captured = {}

    def fake_shell_args(serial, args, timeout=30, *, check=False):
        captured["serial"] = serial
        captured["args"] = args
        captured["timeout"] = timeout
        captured["check"] = check
        return ""

    monkeypatch.setattr(adb, "shell_args", fake_shell_args)
    text = "I'm here & A | B"

    adb.input_text("emulator-5554", text)

    assert captured == {
        "serial": "emulator-5554",
        "args": ["input", "text", text],
        "timeout": 15,
        "check": True,
    }
