"""Nhận diện trạng thái WhatsApp từ activity hiện tại để giảm navigation thừa."""
from enum import Enum

from . import adb
from . import whatsapp_selectors as sel


class WhatsAppState(str, Enum):
    HOME = "home"
    CONTACT_PICKER = "contact_picker"
    CONTACT_FORM = "contact_form"
    CONVERSATION = "conversation"
    OTHER_WHATSAPP = "other_whatsapp"
    UNKNOWN = "unknown"


def _activity_matches(activity: str, target: str) -> bool:
    if not activity or not target:
        return False
    if activity == target:
        return True
    tail = target.split("/", 1)[-1]
    return bool(tail and (activity.endswith(tail) or tail in activity))


def state_from_activity(activity: str) -> WhatsAppState:
    activity = (activity or "").strip()
    if not activity:
        return WhatsAppState.UNKNOWN
    if _activity_matches(activity, sel.ACT_PICKER):
        return WhatsAppState.CONTACT_PICKER
    if _activity_matches(activity, sel.ACT_CONTACT_FORM):
        return WhatsAppState.CONTACT_FORM
    if _activity_matches(activity, sel.ACT_CONVERSATION):
        return WhatsAppState.CONVERSATION
    if _activity_matches(activity, sel.ACT_MAIN) or activity.endswith(".Main"):
        return WhatsAppState.HOME
    if sel.PKG in activity:
        return WhatsAppState.OTHER_WHATSAPP
    return WhatsAppState.UNKNOWN


def detect_state(serial: str) -> WhatsAppState:
    """Đọc top activity qua ADB rồi ánh xạ sang trạng thái workflow."""
    return state_from_activity(adb.top_activity(serial))
