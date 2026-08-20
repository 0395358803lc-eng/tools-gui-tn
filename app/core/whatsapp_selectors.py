"""Selector & hằng số WhatsApp - tập trung toàn bộ để dễ bảo trì khi app cập nhật."""
from typing import Optional

from .data_manager import normalize_phone
from .uiautomator import Node, UiDump

# Package / Activity
PKG = "com.whatsapp"
ACT_MAIN = f"{PKG}/com.whatsapp.Main"
ACT_PICKER = f"{PKG}/.contact.ui.picker.ContactPicker"
ACT_CONVERSATION = f"{PKG}/.Conversation"
ACT_CONTACT_FORM = "ContactFormActivity"

# Resource-ID (đã xác minh)
RID_EULA_ACCEPT = "com.whatsapp:id/eula_accept"
RID_SAVE_BUTTON = "com.whatsapp:id/keyboard_aware_save_button"
RID_NEW_CHAT_FAB = "com.whatsapp:id/fab"

# ADBKeyboard (gõ tiếng Việt/unicode)
ADB_IME = "com.android.adbkeyboard/.AdbIME"
ADB_IME_INPUT_ACTION = "ADB_INPUT_TEXT"

# Text / content-desc / hint
HINT_PHONE = "Phone"
HINT_MESSAGE = "Message"
DESC_NEW_CHAT = "New chat"
DESC_SEND_MESSAGE = "Send message"
TEXT_NEW_CONTACT = "New contact"
TEXT_SAVE = "SAVE"
DESC_SEND = "Send"
DESC_ATTACH = "Attach"
TEXT_GALLERY = "Gallery"
DESC_CAPTION = "Add a caption"
HINT_CAPTION = "Add a caption"

# Tọa độ fallback cho ô nhập phone (đã xác minh trên AVD)
FALLBACK_PHONE_COORD = (919, 1231)


class FallbackCoord:
    """Node giả chỉ có center, dùng cho tọa độ fallback khi không tìm được node thật."""

    def __init__(self, center: tuple[int, int]):
        self.center = center


def _edit_text_by_semantics(dump: UiDump, label: str) -> Optional[Node]:
    """Ưu tiên hint -> content-desc -> text trên các EditText."""
    nodes = dump.find_all(cls="android.widget.EditText")
    for attr in ("hint", "content_desc", "text"):
        for node in nodes:
            if getattr(node, attr) == label:
                return node
    return None


def _clickable_by_desc_or_text(dump: UiDump, label: str) -> Optional[Node]:
    """Ưu tiên content-desc; fallback text, ưu tiên node clickable."""
    desc_nodes = [n for n in dump.nodes if n.content_desc == label]
    text_nodes = [n for n in dump.nodes if n.text == label]
    for group in (desc_nodes, text_nodes):
        for node in group:
            if node.clickable:
                return node
        if group:
            return group[0]
    return None


# ---------------------------------------------------------------------------
# Hàm tìm selector (nhận UiDump, trả Node)
# ---------------------------------------------------------------------------

def find_new_chat_button(dump: UiDump) -> Optional[Node]:
    # Resource-ID đã xác minh ổn định hơn text/content-desc.
    return (
        dump.find(rid=RID_NEW_CHAT_FAB)
        or _clickable_by_desc_or_text(dump, DESC_NEW_CHAT)
        or _clickable_by_desc_or_text(dump, DESC_SEND_MESSAGE)
    )


def find_phone_field(dump: UiDump) -> Optional[Node]:
    return _edit_text_by_semantics(dump, HINT_PHONE)


def find_message_field(dump: UiDump) -> Optional[Node]:
    return _edit_text_by_semantics(dump, HINT_MESSAGE)


def find_caption_field(dump: UiDump) -> Optional[Node]:
    return (
        dump.find(desc=DESC_CAPTION)
        or dump.find(hint=HINT_CAPTION)
        or dump.find(text=HINT_CAPTION)
    )


def find_save_button(dump: UiDump) -> Optional[Node]:
    return dump.find(rid=RID_SAVE_BUTTON) or _clickable_by_desc_or_text(dump, TEXT_SAVE)


def find_send_button(dump: UiDump) -> Optional[Node]:
    return _clickable_by_desc_or_text(dump, DESC_SEND)


def find_attach_button(dump: UiDump) -> Optional[Node]:
    return _clickable_by_desc_or_text(dump, DESC_ATTACH)


def find_gallery_entry(dump: UiDump) -> Optional[Node]:
    return _clickable_by_desc_or_text(dump, TEXT_GALLERY)


def find_first_media_thumbnail(dump: UiDump) -> Optional[Node]:
    """Tìm ảnh đầu tiên trong lưới gallery (ImageView clickable, nằm trong vùng gallery)."""
    for n in dump.nodes:
        if n.cls != "android.widget.ImageView" or not n.clickable:
            continue
        if n.bounds[1] < 1000:
            continue
        w = n.bounds[2] - n.bounds[0]
        h = n.bounds[3] - n.bounds[1]
        if w >= 150 and h >= 150:
            return n
    return None


def find_send_media_button(dump: UiDump) -> Optional[Node]:
    """Nút gửi ảnh: content-desc 'Send', 'Send N media', hoặc text 'Send'."""
    for n in dump.nodes:
        if n.content_desc.startswith(DESC_SEND) and n.clickable:
            return n
    for n in dump.nodes:
        if n.text.startswith(DESC_SEND) and n.clickable:
            return n
    return None


def matches_phone(text: str, digits: str) -> bool:
    t = normalize_phone(text)
    if not t:
        return False
    return t == digits or t.endswith(digits) or digits.endswith(t)


def find_contact_row(dump: UiDump, digits: str) -> Optional[Node]:
    """Tìm dòng liên hệ khớp số điện thoại (ưu tiên node clickable/Button)."""
    by_text = [n for n in dump.nodes if matches_phone(n.text, digits)]
    by_desc = [n for n in dump.nodes if matches_phone(n.content_desc, digits)]
    for n in by_text:
        if n.clickable or n.cls.endswith("Button"):
            return n
    if by_text:
        return by_text[0]
    for n in by_desc:
        if n.clickable:
            return n
    return by_desc[0] if by_desc else None
