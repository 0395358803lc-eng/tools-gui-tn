"""Tests cho contact resolver/cache in-memory."""
from app.core.contact_resolution import ContactCache, ContactResolver


def test_contact_cache_normalizes_and_marks_known_phone():
    cache = ContactCache("emulator-5554")
    cache.mark_known("+84 987-654-321")

    assert cache.is_known("84987654321") is True
    assert cache.is_known("84900000000") is False


def test_resolver_skips_when_ui_detected_existing():
    cache = ContactCache("emulator-5554")
    resolver = ContactResolver(cache)

    assert resolver.should_create("84987654321", detected_existing=True) is False
    assert cache.is_known("84987654321") is True


def test_resolver_skips_subsequent_creation_after_resolved():
    cache = ContactCache("emulator-5554")
    resolver = ContactResolver(cache)

    assert resolver.should_create("84987654321", detected_existing=False) is True
    resolver.mark_resolved("84987654321")
    assert resolver.should_create("84987654321", detected_existing=False) is False


def test_cache_clear_forces_resolution_again():
    cache = ContactCache("emulator-5554")
    resolver = ContactResolver(cache)
    resolver.mark_resolved("84987654321")

    cache.clear()

    assert resolver.should_create("84987654321", detected_existing=False) is True
