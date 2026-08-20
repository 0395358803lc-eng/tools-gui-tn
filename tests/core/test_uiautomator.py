"""Test phân tích UI hierarchy (uiautomator)."""
from app.core import uiautomator as ui

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="Chats" resource-id="" class="android.widget.TextView"
        package="com.whatsapp" content-desc="New chat" bounds="[0,100][200,300]"
        clickable="true" enabled="true" hint="" />
  <node index="1" text="" resource-id="com.whatsapp:id/fab" class="android.widget.ImageButton"
        package="com.whatsapp" content-desc="Send message" bounds="[900,2000][1100,2200]"
        clickable="false" enabled="true" hint="" />
</hierarchy>"""


def test_parse_bounds():
    assert ui._parse_bounds("[10,20][30,40]") == (10, 20, 30, 40)
    assert ui._parse_bounds(None) == (0, 0, 0, 0)


def test_node_center():
    n = ui.Node(bounds=(100, 200, 300, 400))
    assert n.center == (200, 300)


def test_ui_dump_parses(monkeypatch):
    monkeypatch.setattr(ui.adb, "exec_out", lambda serial, cmd, timeout=25: SAMPLE_XML)
    dump = ui.ui_dump("emulator-5554")
    assert dump is not None
    assert len(dump.nodes) == 2


def test_ui_dump_retry_on_empty(monkeypatch):
    calls = {"n": 0}

    def flaky(serial, cmd, timeout=25):
        calls["n"] += 1
        return "" if calls["n"] < 2 else SAMPLE_XML

    monkeypatch.setattr(ui.adb, "exec_out", flaky)
    dump = ui.ui_dump("emulator-5554")
    assert dump is not None and dump.nodes


def test_ui_dump_returns_none_after_failures(monkeypatch):
    monkeypatch.setattr(ui.adb, "exec_out", lambda serial, cmd, timeout=25: "")
    assert ui.ui_dump("emulator-5554", retries=2, delay=0) is None


def test_ui_dump_honors_cancel_before_adb(monkeypatch):
    calls = []
    monkeypatch.setattr(ui.adb, "exec_out", lambda *args, **kwargs: calls.append(args) or SAMPLE_XML)

    assert ui.ui_dump("emulator-5554", cancelled=lambda: True) is None
    assert calls == []


def test_find_and_find_all(monkeypatch):
    monkeypatch.setattr(ui.adb, "exec_out", lambda serial, cmd, timeout=25: SAMPLE_XML)
    dump = ui.ui_dump("emulator-5554")
    assert dump.find(desc="New chat").text == "Chats"
    assert dump.find(rid="com.whatsapp:id/fab") is not None
    assert len(dump.find_all(cls="android.widget.ImageButton")) == 1
    assert dump.find(text="khong co") is None


def test_find_regex(monkeypatch):
    monkeypatch.setattr(ui.adb, "exec_out", lambda serial, cmd, timeout=25: SAMPLE_XML)
    dump = ui.ui_dump("emulator-5554")
    assert dump.find_regex("Cha", attr="text") is not None
    assert dump.find_regex("abcxyz") is None


def test_wait_for_text(monkeypatch):
    monkeypatch.setattr(ui.adb, "exec_out", lambda serial, cmd, timeout=25: SAMPLE_XML)
    node = ui.wait_for_text("emulator-5554", "Chats", timeout=5)
    assert node is not None


def test_wait_for_honors_cancel_without_dump(monkeypatch):
    calls = []
    monkeypatch.setattr(ui, "ui_dump", lambda *args, **kwargs: calls.append(args) or None)

    node = ui.wait_for(
        "emulator-5554",
        lambda dump: None,
        timeout=5,
        cancelled=lambda: True,
    )

    assert node is None
    assert calls == []


def test_wait_for_text_passes_cancel_callback(monkeypatch):
    captured = {}

    def fake_wait(serial, predicate, timeout=20.0, interval=1.0, cancelled=None):
        captured["cancelled"] = cancelled
        return None

    marker = lambda: False
    monkeypatch.setattr(ui, "wait_for", fake_wait)
    ui.wait_for_text("emulator-5554", "Chats", cancelled=marker)
    assert captured["cancelled"] is marker
