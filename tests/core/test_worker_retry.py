"""Regression tests cho retry policy của BroadcastWorker."""
import logging

from app.core import worker as wk
from app.core.exceptions import PartialSendError, WhatsAppError


def _prepare_worker(monkeypatch):
    logger = logging.getLogger("test.broadcast-worker")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    monkeypatch.setattr(wk, "device_logger", lambda avd_name: logger)
    monkeypatch.setattr(wk, "attach_qt_handler", lambda logger, emit: None)
    monkeypatch.setattr(wk.avd_manager.manager, "is_running_headless", lambda name: True)


def test_partial_send_error_is_not_retried(monkeypatch):
    _prepare_worker(monkeypatch)
    calls = []

    class FakeBot:
        def __init__(self, serial, logger=None):
            pass

        def send_bulk(self, phone, message, images):
            calls.append(phone)
            raise PartialSendError("Đã gửi 1/3 ảnh")

    monkeypatch.setattr(wk, "WhatsAppBot", FakeBot)
    config = wk.SendConfig(
        avd_name="avd_1",
        phones=["84900000001"],
        message="hello",
        images=["a.jpg", "b.jpg", "c.jpg"],
        interval=0,
    )
    broadcast = wk.BroadcastWorker(config, "emulator-5554", retries=3)

    broadcast.run()

    assert calls == ["84900000001"]


def test_retryable_whatsapp_error_still_retries(monkeypatch):
    _prepare_worker(monkeypatch)
    calls = []

    class FakeBot:
        def __init__(self, serial, logger=None):
            pass

        def send_bulk(self, phone, message, images):
            calls.append(phone)
            if len(calls) < 3:
                raise WhatsAppError("selector tạm thời chưa thấy")

    monkeypatch.setattr(wk, "WhatsAppBot", FakeBot)
    config = wk.SendConfig(
        avd_name="avd_1",
        phones=["84900000001"],
        message="hello",
        interval=0,
    )
    broadcast = wk.BroadcastWorker(config, "emulator-5554", retries=3)

    broadcast.run()

    assert calls == ["84900000001", "84900000001", "84900000001"]
