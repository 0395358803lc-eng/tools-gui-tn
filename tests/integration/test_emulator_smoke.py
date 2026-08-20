"""Smoke tests chỉ chạy khi WA_INTEGRATION_SERIAL trỏ tới emulator thật."""
import os

import pytest

from app.core import adb, uiautomator as ui
from app.core import whatsapp_selectors as sel

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def serial():
    value = os.environ.get("WA_INTEGRATION_SERIAL", "").strip()
    if not value:
        pytest.skip("Set WA_INTEGRATION_SERIAL to run emulator integration tests")
    return value


def test_selected_device_is_online(serial):
    assert serial in adb.devices()


def test_selected_device_is_booted(serial):
    assert adb.is_boot_completed(serial) is True


def test_whatsapp_package_is_installed(serial):
    out = adb.shell_args(serial, ["pm", "path", sel.PKG], timeout=10, check=True)
    assert "package:" in out


def test_uiautomator_dump_is_readable(serial):
    dump = ui.ui_dump(serial, retries=1, delay=0)
    assert dump is not None
    assert isinstance(dump.nodes, list)
