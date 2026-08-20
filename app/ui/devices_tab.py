"""Tab Danh sách thiết bị - hiển thị toàn bộ AVD, khởi động ẩn không màn hình.

Refresh chạy trên QThread nền để không làm đơ UI (list_avds gọi adb + wmic/PowerShell).
"""
from PySide6.QtCore import QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import avd_manager

STATUS_COLORS = {
    "Đang chạy": "#15803d",
    "Đang khởi động": "#b45309",
    "Đang dừng": "#6b7280",
}


class AVDRefreshThread(QThread):
    """Lấy danh sách AVD + trạng thái trong thread nền (cmd_lines lấy 1 lần)."""

    result_ready = Signal(list)      # list[AVDInfo]

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self._manager = manager

    def run(self) -> None:
        cmd_lines = self._manager.emulator_command_lines()
        avds = self._manager.list_avds(cmd_lines=cmd_lines)
        self.result_ready.emit(avds)


class DevicesTab(QWidget):
    devices_changed = Signal(list)      # list[AVDInfo]
    device_activated = Signal(str)      # avd name -> chuyển tab gửi tin

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = avd_manager.manager
        self._refresh_thread: AVDRefreshThread | None = None
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(5000)
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Làm mới")
        self.btn_headless = QPushButton("Khởi động ẩn (không màn hình)")
        self.btn_visible = QPushButton("Khởi động có màn hình")
        self.btn_kill = QPushButton("Tắt máy")
        self.btn_headless.setToolTip("Khởi động máy ảo ở chế độ ẩn: emulator -avd <tên> -no-window ...")
        for b in (self.btn_refresh, self.btn_headless, self.btn_visible, self.btn_kill):
            bar.addWidget(b)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Tên AVD", "Model", "Trạng thái", "Serial adb", "Chế độ"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (2, 3, 4):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_headless.clicked.connect(self.launch_headless)
        self.btn_visible.clicked.connect(self.launch_visible)
        self.btn_kill.clicked.connect(self.kill_selected)
        self.table.itemDoubleClicked.connect(lambda item: self._on_double_click(item.row()))

    # ------------------------------------------------------------------
    def selected_avd(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        return self.table.item(row, 0).text()

    def refresh(self) -> None:
        """Bỏ qua nếu đang có refresh trước đó; chạy lại không chặn UI."""
        if self._refresh_thread is not None and self._refresh_thread.isRunning():
            return
        thread = AVDRefreshThread(self._manager, self)
        thread.result_ready.connect(self._on_refresh_done)
        thread.finished.connect(thread.deleteLater)
        self._refresh_thread = thread
        thread.start()

    @Slot(list)
    def _on_refresh_done(self, avds: list) -> None:
        self._refresh_thread = None
        self.table.setRowCount(len(avds))
        for r, avd in enumerate(avds):
            self.table.setItem(r, 0, QTableWidgetItem(avd.name))
            self.table.setItem(r, 1, QTableWidgetItem(avd.device or avd.target))
            status = QTableWidgetItem(avd.status)
            status.setForeground(QColor(STATUS_COLORS.get(avd.status, "#000000")))
            self.table.setItem(r, 2, status)
            self.table.setItem(r, 3, QTableWidgetItem(avd.serial))
            mode = ""
            if avd.serial:
                mode = "Ẩn (-no-window)" if avd.headless else "Có màn hình"
            self.table.setItem(r, 4, QTableWidgetItem(mode))
        self.devices_changed.emit(avds)

    # ------------------------------------------------------------------
    def launch_headless(self) -> None:
        self._launch(headless=True)

    def launch_visible(self) -> None:
        self._launch(headless=False)

    def _launch(self, headless: bool) -> None:
        name = self.selected_avd()
        if not name:
            QMessageBox.information(self, "Thông báo", "Hãy chọn một máy ảo trong danh sách.")
            return
        if self._manager.is_running_headless(name):
            QMessageBox.information(self, "Thông báo", f"{name} đang chạy ẩn rồi.")
            return
        try:
            self._manager.launch(name, headless=headless)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi", f"Khởi động thất bại: {e}")
            return
        mode = "ẨN (không màn hình)" if headless else "CÓ màn hình"
        QMessageBox.information(self, "Đang khởi động",
                                f"Đang khởi động {name} ở chế độ {mode}.\n"
                                "Vui lòng chờ vài chục giây để boot hoàn tất.")
        self.refresh()

    def kill_selected(self) -> None:
        name = self.selected_avd()
        if not name:
            return
        serial = ""
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == name:
                serial = self.table.item(r, 3).text()
                break
        self._manager.kill(name, serial)
        self.refresh()

    # ------------------------------------------------------------------
    def _on_double_click(self, row: int) -> None:
        name = self.table.item(row, 0).text()
        if name:
            self.device_activated.emit(name)
