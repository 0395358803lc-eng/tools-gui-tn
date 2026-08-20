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
    broadcast = wk.BroadcastWorker(config, "emulator-5554", retries=3, retry_backoff=0)

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
    broadcast = wk.BroadcastWorker(config, "emulator-5554", retries=3, retry_backoff=0)

    broadcast.run()

    assert calls == ["84900000001", "84900000001", "84900000001"]


def test_retry_backoff_increases_by_attempt(monkeypatch):
    _prepare_worker(monkeypatch)
    calls = []
    sleeps = []

    class FakeBot:
        def __init__(self, serial, logger=None):
            pass

        def send_bulk(self, phone, message, images):
            calls.append(phone)
            raise WhatsAppError("temporary")

    monkeypatch.setattr(wk, "WhatsAppBot", FakeBot)
    config = wk.SendConfig(avd_name="avd_1", phones=["84900000001"], interval=0)
    broadcast = wk.BroadcastWorker(config, "emulator-5554", retries=2, retry_backoff=1.5)
    monkeypatch.setattr(broadcast, "_sleep_interval", lambda seconds: sleeps.append(seconds))

    broadcast.run()

    assert len(calls) == 3
    assert sleeps == [1.5, 3.0]


def test_circuit_breaker_stops_after_consecutive_failures(monkeypatch):
    _prepare_worker(monkeypatch)
    calls = []

    class FakeBot:
        def __init__(self, serial, logger=None):
            pass

        def send_bulk(self, phone, message, images):
            calls.append(phone)
            raise WhatsAppError("permanent")

    monkeypatch.setattr(wk, "WhatsAppBot", FakeBot)
    config = wk.SendConfig(
        avd_name="avd_1",
        phones=["1111111", "2222222", "3333333"],
        interval=0,
    )
    broadcast = wk.BroadcastWorker(
        config,
        "emulator-5554",
        retries=0,
        retry_backoff=0,
        max_consecutive_failures=2,
    )

    broadcast.run()

    assert calls == ["1111111", "2222222"]


def test_success_resets_circuit_breaker_streak(monkeypatch):
    _prepare_worker(monkeypatch)
    calls = []

    outcomes = {
        "1111111": False,
        "2222222": True,
        "3333333": False,
        "4444444": False,
        "5555555": True,
    }

    class FakeBot:
        def __init__(self, serial, logger=None):
            pass

        def send_bulk(self, phone, message, images):
            calls.append(phone)
            if not outcomes[phone]:
                raise WhatsAppError("failed")

    monkeypatch.setattr(wk, "WhatsAppBot", FakeBot)
    config = wk.SendConfig(
        avd_name="avd_1",
        phones=list(outcomes),
        interval=0,
    )
    broadcast = wk.BroadcastWorker(
        config,
        "emulator-5554",
        retries=0,
        retry_backoff=0,
        max_consecutive_failures=2,
    )

    broadcast.run()

    # Lỗi ở 111 được reset bởi thành công 222; breaker chỉ mở sau 333 + 444.
    assert calls == ["1111111", "2222222", "3333333", "4444444"]


def test_blank_phone_entries_are_ignored(monkeypatch):
    _prepare_worker(monkeypatch)
    calls = []

    class FakeBot:
        def __init__(self, serial, logger=None):
            pass

        def send_bulk(self, phone, message, images):
            calls.append(phone)

    monkeypatch.setattr(wk, "WhatsAppBot", FakeBot)
    config = wk.SendConfig(avd_name="avd_1", phones=["", "   ", "84900000001"], interval=0)
    broadcast = wk.BroadcastWorker(config, "emulator-5554", retry_backoff=0)

    broadcast.run()

    assert calls == ["84900000001"]
