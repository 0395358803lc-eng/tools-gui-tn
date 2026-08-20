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


# ---------------------------------------------------------------------------
# Hàm tìm selector (nhận UiDump, trả Node)
# ---------------------------------------------------------------------------

def find_new_chat_button(dump: UiDump) -> Optional[Node]:
    node = dump.find(desc=DESC_NEW_CHAT)
    if node is None:
        node = dump.find(desc=DESC_SEND_MESSAGE)
    return node


def find_phone_field(dump: UiDump) -> Optional[Node]:
    return next((n for n in dump.find_all(cls="android.widget.EditText")
                 if n.hint == HINT_PHONE or n.text == HINT_PHONE), None)


def find_message_field(dump: UiDump) -> Optional[Node]:
    return next((n for n in dump.find_all(cls="android.widget.EditText")
                 if n.hint == HINT_MESSAGE or n.text == HINT_MESSAGE), None)


def find_caption_field(dump: UiDump) -> Optional[Node]:
    return dump.find(desc=DESC_CAPTION) or dump.find(hint=HINT_CAPTION)


def find_save_button(dump: UiDump) -> Optional[Node]:
    return dump.find(rid=RID_SAVE_BUTTON) or dump.find(text=TEXT_SAVE)


def find_send_button(dump: UiDump) -> Optional[Node]:
    return dump.find(desc=DESC_SEND)


def find_attach_button(dump: UiDump) -> Optional[Node]:
    return dump.find(desc=DESC_ATTACH)


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
        if n.text.startswith("Send") and n.clickable:
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
