"""Regression tests cho luồng gửi một/nhiều ảnh WhatsApp."""
import pytest

from app.core import whatsapp_bot as wb
from app.core.exceptions import PartialSendError, WhatsAppError


class DummyNode:
    center = (100, 200)


def test_send_with_image_sends_all_and_caption_only_once(monkeypatch):
    messenger = wb.WhatsAppMessenger("emulator-5554")
    calls = []

    def fake_send(path, message, *, index):
        calls.append((path, message, index))

    monkeypatch.setattr(messenger, "_send_single_image", fake_send)
    messenger.send_with_image(["a.jpg", "b.png", "c.webp"], "Xin chào")
    assert calls == [
        ("a.jpg", "Xin chào", 0),
        ("b.png", "", 1),
        ("c.webp", "", 2),
    ]


def test_send_with_image_rejects_empty_list():
    messenger = wb.WhatsAppMessenger("emulator-5554")
    with pytest.raises(WhatsAppError, match="Danh sách ảnh rỗng"):
        messenger.send_with_image([], "hello")


def test_send_with_image_stops_at_failed_item_without_duplicate_retry(monkeypatch):
    messenger = wb.WhatsAppMessenger("emulator-5554")
    calls = []

    def fake_send(path, message, *, index):
        calls.append(index)
        if index == 1:
            raise WhatsAppError("ảnh thứ hai lỗi")

    monkeypatch.setattr(messenger, "_send_single_image", fake_send)
    with pytest.raises(PartialSendError, match=r"Đã gửi 1/3 ảnh.*ảnh thứ hai lỗi"):
        messenger.send_with_image(["a.jpg", "b.jpg", "c.jpg"], "hello")
    assert calls == [0, 1]


def test_first_image_failure_remains_retryable(monkeypatch):
    messenger = wb.WhatsAppMessenger("emulator-5554")

    def fail_first(path, message, *, index):
        raise WhatsAppError("ảnh đầu lỗi")

    monkeypatch.setattr(messenger, "_send_single_image", fail_first)
    with pytest.raises(WhatsAppError, match="ảnh đầu lỗi") as exc_info:
        messenger.send_with_image(["a.jpg", "b.jpg"], "hello")
    assert not isinstance(exc_info.value, PartialSendError)


def test_cancelled_media_send_stops_before_first_image(monkeypatch):
    messenger = wb.WhatsAppMessenger("emulator-5554", cancelled=lambda: True)
    calls = []
    monkeypatch.setattr(
        messenger,
        "_send_single_image",
        lambda *args, **kwargs: calls.append(args),
    )

    with pytest.raises(WhatsAppError, match="Đã dừng"):
        messenger.send_with_image(["a.jpg"], "hello")
    assert calls == []


def test_push_image_uses_checked_push_touch_and_scan(monkeypatch):
    messenger = wb.WhatsAppMessenger("emulator-5554")
    pushed = []
    shell_calls = []
    scanned = []

    def fake_run(args, timeout=30, *, check=False):
        pushed.append((args, timeout, check))
        return "1 file pushed"

    def fake_shell_args(serial, args, timeout=30, *, check=False):
        shell_calls.append((serial, args, timeout, check))
        return ""

    monkeypatch.setattr(wb.adb, "_run", fake_run)
    monkeypatch.setattr(wb.adb, "shell_args", fake_shell_args)
    monkeypatch.setattr(wb.time, "time_ns", lambda: 123456789)
    monkeypatch.setattr(messenger, "_scan_media", lambda path: scanned.append(path))

    remote = messenger._push_image("C:/tmp/photo.png", index=2)
    assert remote == "/sdcard/Pictures/wa_send_2_123456789.png"
    assert pushed[0][0][-2:] == ["C:/tmp/photo.png", remote]
    assert pushed[0][1:] == (60, True)
    assert shell_calls == [
        ("emulator-5554", ["touch", remote], 10, True),
    ]
    assert scanned == [remote]


def test_single_image_fails_when_attach_missing(monkeypatch):
    messenger = wb.WhatsAppMessenger("emulator-5554")
    monkeypatch.setattr(messenger, "_push_image", lambda path, *, index: "/sdcard/Pictures/a.jpg")
    monkeypatch.setattr(wb.ui, "wait_for", lambda *args, **kwargs: None)

    with pytest.raises(WhatsAppError, match="Attach"):
        messenger._send_single_image("a.jpg", "", index=0)


def test_single_image_retries_scan_then_fails_without_thumbnail(monkeypatch):
    messenger = wb.WhatsAppMessenger("emulator-5554")
    waits = iter([
        DummyNode(),  # attach
        DummyNode(),  # gallery
        None,         # thumbnail lần 1
        None,         # thumbnail retry
    ])
    rescans = []

    monkeypatch.setattr(messenger, "_push_image", lambda path, *, index: "/sdcard/Pictures/a.jpg")
    monkeypatch.setattr(messenger, "_scan_media", lambda path: rescans.append(path))
    monkeypatch.setattr(wb.ui, "wait_for", lambda *args, **kwargs: next(waits))
    monkeypatch.setattr(wb.adb, "tap", lambda *args, **kwargs: None)
    monkeypatch.setattr(wb.time, "sleep", lambda *args, **kwargs: None)

    with pytest.raises(WhatsAppError, match="Không tìm thấy ảnh 1"):
        messenger._send_single_image("a.jpg", "", index=0)
    assert rescans == ["/sdcard/Pictures/a.jpg"]


def test_single_image_fails_when_send_button_missing(monkeypatch):
    messenger = wb.WhatsAppMessenger("emulator-5554")
    waits = iter([
        DummyNode(),  # attach
        DummyNode(),  # gallery
        DummyNode(),  # thumbnail
        None,         # send
    ])

    monkeypatch.setattr(messenger, "_push_image", lambda path, *, index: "/sdcard/Pictures/a.jpg")
    monkeypatch.setattr(wb.ui, "wait_for", lambda *args, **kwargs: next(waits))
    monkeypatch.setattr(wb.adb, "tap", lambda *args, **kwargs: None)
    monkeypatch.setattr(wb.time, "sleep", lambda *args, **kwargs: None)

    with pytest.raises(WhatsAppError, match="nút gửi ảnh 1"):
        messenger._send_single_image("a.jpg", "", index=0)
