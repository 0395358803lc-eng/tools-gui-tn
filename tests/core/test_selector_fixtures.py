"""Regression tests selector dựa trên XML fixture lưu trong repository."""
import xml.etree.ElementTree as ET
from pathlib import Path

from app.core import uiautomator as ui
from app.core import whatsapp_selectors as sel

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "whatsapp"


def load_dump(name: str) -> ui.UiDump:
    xml = (_FIXTURES / name).read_text(encoding="utf-8")
    root = ET.fromstring(xml)
    nodes = []
    ui._walk(root, nodes)
    return ui.UiDump(serial="fixture", xml=xml, nodes=nodes)


def test_home_fixture_resolves_new_chat():
    dump = load_dump("home.xml")
    node = sel.find_new_chat_button(dump)
    assert node is not None
    assert node.resource_id == sel.RID_NEW_CHAT_FAB


def test_contact_form_fixture_resolves_phone_and_save():
    dump = load_dump("contact_form.xml")
    phone = sel.find_phone_field(dump)
    save = sel.find_save_button(dump)

    assert phone is not None
    assert phone.hint == sel.HINT_PHONE
    assert save is not None
    assert save.resource_id == sel.RID_SAVE_BUTTON


def test_conversation_fixture_resolves_message_attach_send():
    dump = load_dump("conversation.xml")

    assert sel.find_message_field(dump) is not None
    assert sel.find_attach_button(dump) is not None
    assert sel.find_send_button(dump) is not None
