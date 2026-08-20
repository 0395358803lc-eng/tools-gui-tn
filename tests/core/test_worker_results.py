"""Tests cho BroadcastWorker structured result/report."""
import logging

from app.core import worker as wk
from app.core.broadcast_result import RecipientStatus
from app.core.exceptions import PartialSendError, WhatsAppError
from app.core.preflight import PreflightCheck, PreflightResult


def prepare(monkeypatch):
    logger = logging.getLogger("test.worker-results")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    monkeypatch.setattr(wk, "device_logger", lambda name: logger)
    monkeypatch.setattr(wk, "attach_qt_handler", lambda logger, emit: None)
    monkeypatch.setattr(wk.avd_manager.manager, "is_running_headless", lambda name: True)
    monkeypatch.setattr(wk, "validate_broadcast_inputs", lambda *a, **k: PreflightResult())
    monkeypatch.setattr(wk, "run_device_preflight", lambda *a, **k: PreflightResult())
    monkeypatch.setattr(wk, "return_home_best_effort", lambda *a, **k: True)


def config():
    return wk.SendConfig(
        avd_name="avd_1",
        phones=["84987654321"],
        message="hello",
        interval=0,
    )


def test_success_after_retry_records_attempt_count(monkeypatch):
    prepare(monkeypatch)
    calls = []

    class Bot:
        def __init__(self, *args, **kwargs):
            pass

        def send_bulk(self, phone, message, images):
            calls.append(phone)
            if len(calls) == 1:
                raise WhatsAppError("temporary")

    monkeypatch.setattr(wk, "WhatsAppBot", Bot)
    worker = wk.BroadcastWorker(
        config(),
        "emulator-5554",
        retries=2,
        retry_backoff=0,
        minimum_interval=0,
        auto_export_reports=False,
    )

    worker.run()

    result = worker.report.recipients[0]
    assert result.status is RecipientStatus.SUCCESS
    assert result.attempts == 2
    assert result.error_code == ""
    assert worker.report.success_count == 1
    assert worker.report.completed_at


def test_partial_send_records_partial_without_retry(monkeypatch):
    prepare(monkeypatch)
    calls = []

    class Bot:
        def __init__(self, *args, **kwargs):
            pass

        def send_bulk(self, phone, message, images):
            calls.append(phone)
            raise PartialSendError("sent 1/2")

    monkeypatch.setattr(wk, "WhatsAppBot", Bot)
    worker = wk.BroadcastWorker(
        config(),
        "emulator-5554",
        retries=3,
        retry_backoff=0,
        auto_export_reports=False,
    )

    worker.run()

    result = worker.report.recipients[0]
    assert result.status is RecipientStatus.PARTIAL
    assert result.attempts == 1
    assert result.error_code == "PartialSendError"
    assert calls == ["84987654321"]


def test_exhausted_retry_records_failed(monkeypatch):
    prepare(monkeypatch)

    class Bot:
        def __init__(self, *args, **kwargs):
            pass

        def send_bulk(self, phone, message, images):
            raise WhatsAppError("still failing")

    monkeypatch.setattr(wk, "WhatsAppBot", Bot)
    worker = wk.BroadcastWorker(
        config(),
        "emulator-5554",
        retries=2,
        retry_backoff=0,
        auto_export_reports=False,
    )

    worker.run()

    result = worker.report.recipients[0]
    assert result.status is RecipientStatus.FAILED
    assert result.attempts == 3
    assert result.error_code == "WhatsAppError"


def test_stop_during_recipient_records_cancelled(monkeypatch):
    prepare(monkeypatch)
    holder = {}

    class Bot:
        def __init__(self, *args, **kwargs):
            pass

        def send_bulk(self, phone, message, images):
            holder["worker"].stop()
            raise WhatsAppError("Đã dừng theo yêu cầu")

    monkeypatch.setattr(wk, "WhatsAppBot", Bot)
    worker = wk.BroadcastWorker(
        config(),
        "emulator-5554",
        retries=3,
        retry_backoff=0,
        auto_export_reports=False,
    )
    holder["worker"] = worker

    worker.run()

    result = worker.report.recipients[0]
    assert result.status is RecipientStatus.CANCELLED
    assert result.error_code == "Cancelled"


def test_preflight_failure_is_recorded_in_report(monkeypatch):
    prepare(monkeypatch)
    failed = PreflightResult([
        PreflightCheck("whatsapp_installed", False, "missing", required=True),
    ])
    monkeypatch.setattr(wk, "run_device_preflight", lambda *a, **k: failed)

    class Bot:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Bot must not be created after failed preflight")

    monkeypatch.setattr(wk, "WhatsAppBot", Bot)
    worker = wk.BroadcastWorker(
        config(),
        "emulator-5554",
        auto_export_reports=False,
    )

    worker.run()

    assert worker.report.preflight_ok is False
    assert worker.report.recipients == []
    assert "whatsapp_installed: missing" in worker.report.preflight_errors
    assert worker.report.completed_at
