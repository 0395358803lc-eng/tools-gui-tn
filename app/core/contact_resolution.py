"""Chiến lược resolve contact và cache in-memory theo phiên worker/device."""
from dataclasses import dataclass, field

from .data_manager import normalize_phone


@dataclass
class ContactCache:
    """Cache contact đã xác minh trong phiên hiện tại; không persist xuống disk."""

    device_key: str
    _known: set[str] = field(default_factory=set)

    def is_known(self, phone: str) -> bool:
        digits = normalize_phone(phone)
        return bool(digits and digits in self._known)

    def mark_known(self, phone: str) -> None:
        digits = normalize_phone(phone)
        if digits:
            self._known.add(digits)

    def clear(self) -> None:
        self._known.clear()


class ContactResolver:
    """Quyết định có cần tạo contact dựa trên cache + kết quả quan sát UI."""

    def __init__(self, cache: ContactCache):
        self.cache = cache

    def should_create(self, phone: str, *, detected_existing: bool) -> bool:
        if self.cache.is_known(phone):
            return False
        if detected_existing:
            self.cache.mark_known(phone)
            return False
        return True

    def mark_resolved(self, phone: str) -> None:
        self.cache.mark_known(phone)
