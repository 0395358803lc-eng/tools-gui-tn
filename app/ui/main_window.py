"""Cửa sổ chính với 2 tab: Danh sách thiết bị và Gửi tin nhắn hàng loạt."""
from PySide6.QtCore import QByteArray, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QTabWidget

from ..core import settings
from .broadcast_tab import BroadcastTab
from .devices_tab import DevicesTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tools Tự Động Gửi Tin Nhắn WhatsApp")
        self.resize(1280, 800)

        self.tabs = QTabWidget()
        self.devices_tab = DevicesTab()
        self.broadcast_tab = BroadcastTab()

        self.tabs.addTab(self.devices_tab, "Danh sách thiết bị")
        self.tabs.addTab(self.broadcast_tab, "Gửi tin nhắn hàng loạt")

        self.setCentralWidget(self.tabs)

        self._restore_window_state()

        self.devices_tab.devices_changed.connect(self.broadcast_tab.on_devices_changed)
        self.devices_tab.device_activated.connect(self._jump_to_broadcast)

        # Đảm bảo broadcast tab nhận danh sách AVD sau khi signal đã kết nối
        # (refresh chạy trong thread nền, không chặn UI)
        QTimer.singleShot(100, self.devices_tab.refresh)

    def _restore_window_state(self) -> None:
        state = settings.get_window_state()
        geom = state.get("geometry")
        if geom:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geom.encode("ascii")))
            except Exception:  # noqa: BLE001
                pass
        try:
            self.tabs.setCurrentIndex(int(state.get("tab", 0)))
        except (TypeError, ValueError):
            pass

    def _initial_broadcast_sync(self) -> None:
        from ..core import avd_manager
        self.broadcast_tab.on_devices_changed(avd_manager.manager.list_avds())

    def _jump_to_broadcast(self, avd_name: str) -> None:
        self.tabs.setCurrentWidget(self.broadcast_tab)
        self.broadcast_tab.select_avd(avd_name)

    def closeEvent(self, event: QCloseEvent) -> None:
        settings.set_window_state(
            bytes(self.saveGeometry().toBase64()).decode("ascii"),
            self.tabs.currentIndex(),
        )
        event.accept()
