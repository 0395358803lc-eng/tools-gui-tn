"""Tests cho nhận diện state và best-effort navigation."""
from app.core import whatsapp_state as ws


def test_state_from_activity_known_whatsapp_states():
    assert ws.state_from_activity("com.whatsapp/com.whatsapp.Main") is ws.WhatsAppState.HOME
    assert ws.state_from_activity("com.whatsapp/.Main") is ws.WhatsAppState.HOME
    assert ws.state_from_activity(
        "com.whatsapp/.contact.ui.picker.ContactPicker"
    ) is ws.WhatsAppState.CONTACT_PICKER
    assert ws.state_from_activity("com.whatsapp/.Conversation") is ws.WhatsAppState.CONVERSATION
    assert ws.state_from_activity(
        "com.android.contacts/.activities.ContactFormActivity"
    ) is ws.WhatsAppState.CONTACT_FORM


def test_state_from_activity_unknown_and_other_whatsapp():
    assert ws.state_from_activity("") is ws.WhatsAppState.UNKNOWN
    assert ws.state_from_activity("com.android.settings/.Settings") is ws.WhatsAppState.UNKNOWN
    assert ws.state_from_activity("com.whatsapp/.SomeFutureActivity") is ws.WhatsAppState.OTHER_WHATSAPP


def test_detect_state_uses_top_activity(monkeypatch):
    monkeypatch.setattr(
        ws.adb,
        "top_activity",
        lambda serial: "com.whatsapp/.Conversation",
    )
    assert ws.detect_state("emulator-5554") is ws.WhatsAppState.CONVERSATION


def test_return_home_best_effort_backs_out_conversation_and_picker(monkeypatch):
    states = iter([
        ws.WhatsAppState.CONVERSATION,
        ws.WhatsAppState.CONTACT_PICKER,
        ws.WhatsAppState.HOME,
    ])
    backs = []
    monkeypatch.setattr(ws, "detect_state", lambda serial: next(states))
    monkeypatch.setattr(ws.adb, "back", lambda serial: backs.append(serial))
    monkeypatch.setattr(ws.time, "sleep", lambda seconds: None)

    assert ws.return_home_best_effort("emulator-5554") is True
    assert backs == ["emulator-5554", "emulator-5554"]


def test_return_home_best_effort_refuses_unknown_state(monkeypatch):
    backs = []
    monkeypatch.setattr(ws, "detect_state", lambda serial: ws.WhatsAppState.OTHER_WHATSAPP)
    monkeypatch.setattr(ws.adb, "back", lambda serial: backs.append(serial))

    assert ws.return_home_best_effort("emulator-5554") is False
    assert backs == []


def test_return_home_best_effort_honors_cancel(monkeypatch):
    calls = []
    monkeypatch.setattr(ws, "detect_state", lambda serial: calls.append(serial) or ws.WhatsAppState.HOME)

    assert ws.return_home_best_effort(
        "emulator-5554",
        cancelled=lambda: True,
    ) is False
    assert calls == []
