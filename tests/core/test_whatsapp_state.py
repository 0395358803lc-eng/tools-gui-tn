"""Tests cho nhận diện state từ Android activity."""
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
