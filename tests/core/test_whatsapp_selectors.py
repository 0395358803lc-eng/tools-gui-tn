"""Test selector WhatsApp - tìm đúng node theo UiDump."""
from app.core import whatsapp_selectors as sel
from app.core.uiautomator import Node, UiDump


def make_dump(nodes):
    return UiDump(serial="emulator-5554", xml="", nodes=nodes)


def test_matches_phone():
    assert sel.matches_phone("+1 (202) 555-0134", "12025550134")
    assert sel.matches_phone("84987654321", "84987654321")
    assert not sel.matches_phone("abc", "12025550134")


def test_find_phone_and_message_fields():
    dump = make_dump([
        Node(cls="android.widget.EditText", hint="Phone"),
        Node(cls="android.widget.EditText", hint="Message"),
    ])
    assert sel.find_phone_field(dump) is not None
    assert sel.find_message_field(dump) is not None


def test_find_contact_row_prefers_clickable():
    dump = make_dump([
        Node(text="12025550134", cls="android.widget.TextView", clickable=False),
        Node(text="12025550134", cls="android.widget.Button", clickable=True),
    ])
    assert sel.find_contact_row(dump, "12025550134").cls == "android.widget.Button"


def test_find_first_media_thumbnail():
    dump = make_dump([
        Node(cls="android.widget.ImageView", clickable=True, bounds=(100, 500, 300, 700)),
        Node(cls="android.widget.ImageView", clickable=True, bounds=(100, 1200, 400, 1500)),
    ])
    found = sel.find_first_media_thumbnail(dump)
    assert found is not None
    assert found.bounds[1] >= 1000


def test_find_send_media_button():
    dump = make_dump([
        Node(content_desc="Attach", clickable=True),
        Node(content_desc="Send 1 media", clickable=True),
    ])
    assert sel.find_send_media_button(dump).content_desc == "Send 1 media"
