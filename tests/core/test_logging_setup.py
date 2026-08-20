"""Tests cho masking dữ liệu nhạy cảm trong diagnostics."""
import logging

from app.core import logging_setup
from app.core import whatsapp_bot as wb
from app.core.uiautomator import Node, UiDump


def test_mask_phone_long_number():
    assert logging_setup.mask_phone("84987654321") == "849******21"


def test_mask_phone_short_value_is_fully_hidden():
    assert logging_setup.mask_phone("12345") == "*****"
    assert logging_setup.mask_phone("") == ""


def test_mask_phone_handles_zero_visible_suffix_without_leaking_tail():
    assert logging_setup.mask_phone("123456789", prefix=3, suffix=0) == "123******"
    assert logging_setup.mask_phone("123456789", prefix=0, suffix=2) == "*******89"


def test_contact_manager_logs_masked_phone_for_existing_contact(monkeypatch, caplog):
    phone = "84987654321"
    dump = UiDump(
        serial="emulator-5554",
        xml="",
        nodes=[Node(text=phone)],
    )
    logger = logging.getLogger("test.masked-contact")
    logger.propagate = True
    logger.handlers.clear()
    manager = wb.WhatsAppContactManager("emulator-5554", logger=logger)

    monkeypatch.setattr(wb.ui, "ui_dump", lambda *args, **kwargs: dump)
    caplog.set_level(logging.INFO)

    manager.create_contact(phone)

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert phone not in messages
    assert "849******21" in messages
