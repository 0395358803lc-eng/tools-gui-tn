"""Unit tests cho orchestration WhatsAppBot và ContactManager."""
import pytest

from app.core import whatsapp_bot as wb
from app.core.exceptions import WhatsAppError
from app.core.uiautomator import Node, UiDump


def test_whatsapp_bot_text_workflow_order():
    events = []
    bot = wb.WhatsAppBot("emulator-5554")

    class App:
        def _ensure_not_cancelled(self):
            pass

        def open_app(self):
            events.append("open_app")

        def ensure_onboarded(self):
            events.append("ensure_onboarded")

        def open_contact_picker(self):
            events.append("open_contact_picker")

    class Contacts:
        def create_contact(self, phone):
            events.append(("create_contact", phone))

        def open_chat(self, phone):
            events.append(("open_chat", phone))

    class Messenger:
        def send_text(self, message):
            events.append(("send_text", message))

        def send_with_image(self, images, message):
            events.append(("send_media", images, message))

    bot.app = App()
    bot.contacts = Contacts()
    bot.messenger = Messenger()
    bot.send_bulk("84900000001", "hello", [])

    assert events == [
        "open_app",
        "ensure_onboarded",
        "open_contact_picker",
        ("create_contact", "84900000001"),
        ("open_chat", "84900000001"),
        ("send_text", "hello"),
    ]


def test_whatsapp_bot_media_workflow_routes_to_media_sender():
    events = []
    bot = wb.WhatsAppBot("emulator-5554")

    class App:
        def _ensure_not_cancelled(self):
            pass

        def open_app(self):
            events.append("open_app")

        def ensure_onboarded(self):
            events.append("ensure_onboarded")

        def open_contact_picker(self):
            events.append("open_contact_picker")

    class Contacts:
        def create_contact(self, phone):
            events.append("create_contact")

        def open_chat(self, phone):
            events.append("open_chat")

    class Messenger:
        def send_text(self, message):
            events.append("send_text")

        def send_with_image(self, images, message):
            events.append(("send_media", images, message))

    bot.app = App()
    bot.contacts = Contacts()
    bot.messenger = Messenger()
    bot.send_bulk("84900000001", "caption", ["a.jpg", "b.jpg"])

    assert events[-1] == ("send_media", ["a.jpg", "b.jpg"], "caption")
    assert "send_text" not in events


def test_whatsapp_bot_stops_before_opening_app_when_cancelled():
    bot = wb.WhatsAppBot("emulator-5554", cancelled=lambda: True)
    with pytest.raises(WhatsAppError, match="Đã dừng"):
        bot.send_bulk("84900000001", "hello", [])


def test_wait_wrapper_passes_cancel_callback(monkeypatch):
    marker = lambda: False
    manager = wb.WhatsAppContactManager("emulator-5554", cancelled=marker)
    captured = {}

    def fake_wait(serial, predicate, timeout=20.0, interval=1.0, cancelled=None):
        captured["cancelled"] = cancelled
        return None

    monkeypatch.setattr(wb.ui, "wait_for", fake_wait)
    manager._wait_for(lambda dump: None, timeout=1)
    assert captured["cancelled"] is marker


def test_open_app_skips_restart_when_already_home(monkeypatch):
    controller = wb.WhatsAppAppController("emulator-5554")
    shell_calls = []

    monkeypatch.setattr(wb, "detect_state", lambda serial: wb.WhatsAppState.HOME)
    monkeypatch.setattr(
        wb.adb,
        "shell",
        lambda *args, **kwargs: shell_calls.append((args, kwargs)) or "",
    )

    controller.open_app()

    assert shell_calls == []


def test_open_contact_picker_skips_new_chat_when_already_in_picker(monkeypatch):
    controller = wb.WhatsAppAppController("emulator-5554")
    taps = []
    dumps = []

    monkeypatch.setattr(
        wb,
        "detect_state",
        lambda serial: wb.WhatsAppState.CONTACT_PICKER,
    )
    monkeypatch.setattr(
        wb.ui,
        "ui_dump",
        lambda *args, **kwargs: dumps.append(args) or None,
    )
    monkeypatch.setattr(wb.adb, "tap", lambda *args, **kwargs: taps.append(args))

    controller.open_contact_picker()

    assert dumps == []
    assert taps == []


def test_create_contact_refuses_unverified_coordinate_fallback(monkeypatch):
    manager = wb.WhatsAppContactManager("emulator-5554")
    new_contact = Node(text=wb.sel.TEXT_NEW_CONTACT, clickable=True, bounds=(10, 10, 30, 30))
    dump = UiDump(serial="emulator-5554", xml="", nodes=[new_contact])
    taps = []

    monkeypatch.setattr(wb.ui, "ui_dump", lambda *args, **kwargs: dump)
    monkeypatch.setattr(wb.ui, "wait_for", lambda *args, **kwargs: None)
    monkeypatch.setattr(wb.adb, "wait_for_activity", lambda *args, **kwargs: True)
    monkeypatch.setattr(wb.adb, "tap", lambda serial, x, y: taps.append((x, y)))
    monkeypatch.setattr(wb.time, "sleep", lambda *args, **kwargs: None)

    with pytest.raises(WhatsAppError, match="selector an toàn"):
        manager.create_contact("84900000001")

    assert taps == [new_contact.center]
