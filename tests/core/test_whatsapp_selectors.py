"""Test selector WhatsApp - tìm đúng node theo UiDump."""
from app.core import whatsapp_selectors as sel
from app.core.uiautomator import Node, UiDump


def make_dump(nodes):
    return UiDump(serial="emulator-5554", xml="", nodes=nodes)


def test_matches_phone():
    assert sel.matches_phone("+1 (202) 555-0134", "12025550134")
    assert sel.matches_phone("84987654321", "84987654321")
    assert not sel.matches_phone("abc", "12025550134")


def test_find_new_chat_prefers_verified_resource_id():
    dump = make_dump([
        Node(content_desc="New chat", clickable=True, bounds=(1, 1, 2, 2)),
        Node(resource_id=sel.RID_NEW_CHAT_FAB, clickable=True, bounds=(3, 3, 4, 4)),
    ])
    assert sel.find_new_chat_button(dump).resource_id == sel.RID_NEW_CHAT_FAB


def test_find_new_chat_falls_back_to_content_description():
    dump = make_dump([Node(content_desc="New chat", clickable=True)])
    assert sel.find_new_chat_button(dump).content_desc == "New chat"


def test_find_phone_and_message_fields_prefers_hint():
    dump = make_dump([
        Node(cls="android.widget.EditText", text="Phone", bounds=(1, 1, 2, 2)),
        Node(cls="android.widget.EditText", hint="Phone", bounds=(3, 3, 4, 4)),
        Node(cls="android.widget.EditText", content_desc="Message", bounds=(5, 5, 6, 6)),
        Node(cls="android.widget.EditText", hint="Message", bounds=(7, 7, 8, 8)),
    ])
    assert sel.find_phone_field(dump).hint == "Phone"
    assert sel.find_message_field(dump).hint == "Message"


def test_find_edit_fields_fall_back_to_content_desc_then_text():
    dump = make_dump([
        Node(cls="android.widget.EditText", content_desc="Phone"),
        Node(cls="android.widget.EditText", text="Message"),
    ])
    assert sel.find_phone_field(dump).content_desc == "Phone"
    assert sel.find_message_field(dump).text == "Message"


def test_find_caption_supports_desc_hint_and_text():
    assert sel.find_caption_field(make_dump([Node(content_desc="Add a caption")])) is not None
    assert sel.find_caption_field(make_dump([Node(hint="Add a caption")])) is not None
    assert sel.find_caption_field(make_dump([Node(text="Add a caption")])) is not None


def test_find_send_attach_and_gallery_prefer_clickable():
    dump = make_dump([
        Node(text="Send", clickable=False, bounds=(1, 1, 2, 2)),
        Node(content_desc="Send", clickable=True, bounds=(3, 3, 4, 4)),
        Node(text="Attach", clickable=True),
        Node(content_desc="Gallery", clickable=True),
    ])
    assert sel.find_send_button(dump).content_desc == "Send"
    assert sel.find_attach_button(dump).text == "Attach"
    assert sel.find_gallery_entry(dump).content_desc == "Gallery"


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
