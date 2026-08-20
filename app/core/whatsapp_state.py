"""Nhận diện/trợ giúp điều hướng state WhatsApp."""
import time
from enum import Enum
from typing import Callable, Optional

from . import adb
from . import whatsapp_selectors as sel
from .exceptions import ADBError


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


def return_home_best_effort(
    serial: str,
    *,
    cancelled: Optional[Callable[[], bool]] = None,
    max_back: int = 3,
    pause: float = 0.5,
) -> bool:
    """Cố đưa WhatsApp về HOME để tái sử dụng session cho recipient kế tiếp.

    Chỉ dùng Back với các state đã hiểu rõ (Conversation/ContactPicker). Mọi lỗi hoặc
    state lạ trả False để caller fallback về workflow restart cũ; không raise sau khi
    nội dung đã gửi thành công.
    """
    cancelled = cancelled or (lambda: False)
    for _ in range(max(0, max_back) + 1):
        if cancelled():
            return False
        state = detect_state(serial)
        if state is WhatsAppState.HOME:
            return True
        if state not in {WhatsAppState.CONVERSATION, WhatsAppState.CONTACT_PICKER}:
            return False
        try:
            adb.back(serial)
        except ADBError:
            return False
        if pause > 0:
            time.sleep(pause)
    return detect_state(serial) is WhatsAppState.HOME
