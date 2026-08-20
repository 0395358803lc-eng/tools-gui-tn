"""Tab Gửi tin nhắn hàng loạt - trái: danh sách máy ảo, phải: cấu hình cho máy đang chọn.

UI thuần tuý hiển thị/tương tác; xử lý dữ liệu giao cho core (data_manager, worker).
"""
import os

from PySide6.QtCore import QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (QFileDialog, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QSplitter, QSpinBox, QVBoxLayout, QWidget)

from ..core import avd_manager, settings
from ..core import data_manager
from ..core.logging_setup import device_logger
from ..core.worker import BroadcastWorker, SendConfig
from .log_panel import LogPanel


class DeviceRefreshThread(QThread):
    """Làm mới danh sách AVD trong thread nền (list_avds gọi adb + wmic/PowerShell)."""

    result_ready = Signal(list)      # list[AVDInfo]

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self._manager = manager

    def run(self) -> None:
        cmd_lines = self._manager.emulator_command_lines()
        avds = self._manager.list_avds(cmd_lines=cmd_lines)
        self.result_ready.emit(avds)


class BroadcastTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._avds: dict[str, avd_manager.AVDInfo] = {}
        self._workers: dict[str, BroadcastWorker] = {}
        self._image_paths: dict[str, str] = {}   # basename -> full path
        self._refresh_thread: DeviceRefreshThread | None = None
        self._selected_device = ""   # thiết bị đang hiển thị trên panel phải
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ---- Cột trái: danh sách máy ảo ----
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Danh sách máy ảo:"))
        self.device_list = QListWidget()
        self.device_list.itemClicked.connect(self._on_device_selected)
        left_layout.addWidget(self.device_list)
        self.btn_refresh = QPushButton("Làm mới trạng thái")
        self.btn_refresh.setToolTip("Cập nhật trạng thái đang dừng / đang chạy của các máy ảo")
        self.btn_refresh.clicked.connect(self.refresh_devices)
        left_layout.addWidget(self.btn_refresh)
        splitter.addWidget(left)

        # ---- Cột phải: cấu hình ----
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)

        self.lbl_device = QLabel("Chưa chọn thiết bị")
        self.lbl_device.setStyleSheet("font-size:15px; font-weight:bold;")
        right_layout.addWidget(self.lbl_device)

        # Số điện thoại
        group_numbers = QGroupBox("Danh sách số điện thoại (mỗi dòng 1 số)")
        vn = QVBoxLayout(group_numbers)
        self.txt_numbers = QPlainTextEdit()
        self.txt_numbers.setPlaceholderText("Ví dụ:\n12052452095\n84987654321")
        vn.addWidget(self.txt_numbers)
        btn_row = QHBoxLayout()
        self.btn_import = QPushButton("Import Excel/CSV")
        self.btn_clean = QPushButton("Dọn dữ liệu (chỉ giữ số)")
        btn_row.addWidget(self.btn_import)
        btn_row.addWidget(self.btn_clean)
        btn_row.addStretch(1)
        vn.addLayout(btn_row)
        right_layout.addWidget(group_numbers)

        # Nội dung tin nhắn
        group_msg = QGroupBox("Nội dung tin nhắn")
        vm = QVBoxLayout(group_msg)
        self.txt_message = QPlainTextEdit()
        self.txt_message.setPlaceholderText("Nhập nội dung tin nhắn...")
        vm.addWidget(self.txt_message)
        right_layout.addWidget(group_msg)

        # Hình ảnh kèm
        group_img = QGroupBox("Hình ảnh kèm (không bắt buộc)")
        vi = QVBoxLayout(group_img)
        self.list_images = QListWidget()
        self.list_images.setMaximumHeight(120)
        vi.addWidget(self.list_images)
        img_row = QHBoxLayout()
        self.btn_add_images = QPushButton("Thêm ảnh...")
        self.btn_remove_image = QPushButton("Xoá ảnh chọn")
        img_row.addWidget(self.btn_add_images)
        img_row.addWidget(self.btn_remove_image)
        img_row.addStretch(1)
        vi.addLayout(img_row)
        right_layout.addWidget(group_img)

        # Khoảng cách
        row_interval = QHBoxLayout()
        row_interval.addWidget(QLabel("Khoảng cách giữa mỗi tin (giây):"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(0, 600)
        self.spin_interval.setValue(5)
        row_interval.addWidget(self.spin_interval)
        row_interval.addStretch(1)
        right_layout.addLayout(row_interval)

        # Nút điều khiển
        row_ctrl = QHBoxLayout()
        self.btn_start = QPushButton("Bắt đầu quy trình")
        self.btn_stop = QPushButton("Dừng")
        self.btn_stop.setEnabled(False)
        row_ctrl.addWidget(self.btn_start)
        row_ctrl.addWidget(self.btn_stop)
        row_ctrl.addStretch(1)
        right_layout.addLayout(row_ctrl)

        # Tiến trình
        row_progress = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.lbl_progress = QLabel("0/0")
        row_progress.addWidget(self.progress_bar, 1)
        row_progress.addWidget(self.lbl_progress)
        right_layout.addLayout(row_progress)

        # Log
        right_layout.addWidget(QLabel("Log hoạt động:"))
        self.log_panel = LogPanel()
        right_layout.addWidget(self.log_panel, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([250, 900])
        layout.addWidget(splitter)

        # Kết nối
        self.btn_import.clicked.connect(self.import_numbers)
        self.btn_clean.clicked.connect(self.clean_numbers)
        self.btn_add_images.clicked.connect(self.add_images)
        self.btn_remove_image.clicked.connect(self.remove_image)
        self.btn_start.clicked.connect(self.start_process)
        self.btn_stop.clicked.connect(self.stop_process)

    # ------------------------------------------------------------------
    # Đồng bộ danh sách thiết bị
    # ------------------------------------------------------------------
    def refresh_devices(self) -> None:
        """Làm mới thủ công trạng thái máy ảo (chạy thread nền, không chặn UI)."""
        if self._refresh_thread is not None and self._refresh_thread.isRunning():
            return
        self.btn_refresh.setEnabled(False)
        self.log_panel.append_log("Đang làm mới danh sách thiết bị...", "info")
        thread = DeviceRefreshThread(avd_manager.manager, self)
        thread.result_ready.connect(self._on_devices_refreshed)
        thread.finished.connect(thread.deleteLater)
        self._refresh_thread = thread
        thread.start()

    @Slot(list)
    def _on_devices_refreshed(self, avds: list) -> None:
        self._refresh_thread = None
        self.btn_refresh.setEnabled(True)
        self.on_devices_changed(avds)
        self.log_panel.append_log("Đã làm mới danh sách thiết bị.", "success")

    @Slot(list)
    def on_devices_changed(self, avds: list) -> None:
        current = self.current_device()
        self._avds = {a.name: a for a in avds}
        self.device_list.blockSignals(True)
        self.device_list.clear()
        for a in avds:
            item = QListWidgetItem(f"{a.name}   [{a.status}]")
            self.device_list.addItem(item)
        self.device_list.blockSignals(False)
        if current and current in self._avds:
            self._select_device(current)

    def _select_device(self, name: str) -> None:
        for i in range(self.device_list.count()):
            if self.device_list.item(i).text().startswith(name):
                self.device_list.setCurrentRow(i)
                break
        self._on_device_selected(self.device_list.currentItem())

    def select_avd(self, name: str) -> None:
        if name in self._avds:
            self._select_device(name)

    def current_device(self) -> str:
        item = self.device_list.currentItem()
        if not item:
            return ""
        return item.text().split()[0]

    def _on_device_selected(self, item: QListWidgetItem) -> None:
        if not item:
            return
        name = item.text().split()[0]
        avd = self._avds.get(name)
        status = avd.status if avd else "?"
        self.lbl_device.setText(f"{name}   —   {status}")

        # Nếu vẫn là thiết bị đang hiển thị (vd: refresh định kỳ) thì không load lại
        # dữ liệu từ config để tránh mất nội dung người dùng đang nhập dở.
        if name == self._selected_device:
            return
        self._selected_device = name

        cfg = settings.get_device_config(name)
        self.txt_numbers.setPlainText(cfg.get("numbers", ""))
        self.txt_message.setPlainText(cfg.get("message", ""))
        self.spin_interval.setValue(int(cfg.get("interval", 5)))
        self.list_images.clear()
        self._image_paths.clear()
        for p in cfg.get("images", []):
            self.list_images.addItem(os.path.basename(p))
            self._image_paths[os.path.basename(p)] = p
        self.log_panel.clear_log()
        self.log_panel.append_log(f"Chọn thiết bị {name}.", "info")
        device_logger(name).info(f"Chọn thiết bị {name}.")

    # ------------------------------------------------------------------
    # Nhập liệu
    # ------------------------------------------------------------------
    def import_numbers(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file Excel/CSV", "",
            "Excel/CSV (*.xlsx *.xls *.csv);;Tất cả (*)")
        if not path:
            return
        try:
            numbers = data_manager.import_phones_from_file(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi import", str(e))
            return
        current = self.txt_numbers.toPlainText().strip()
        merged = "\n".join(filter(None, [current] + numbers))
        self.txt_numbers.setPlainText(merged)
        self.log_panel.append_log(f"Đã import {len(numbers)} số từ {os.path.basename(path)}.", "success")

    def clean_numbers(self) -> None:
        cleaned = data_manager.clean_phone_text(self.txt_numbers.toPlainText())
        self.txt_numbers.setPlainText("\n".join(cleaned))
        self.log_panel.append_log("Đã dọn dữ liệu số điện thoại.", "info")

    def add_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh gửi kèm", "", "Hình ảnh (*.png *.jpg *.jpeg *.webp);;Tất cả (*)")
        for p in paths:
            base = os.path.basename(p)
            self.list_images.addItem(base)
            self._image_paths[base] = p

    def remove_image(self) -> None:
        for item in self.list_images.selectedItems():
            self._image_paths.pop(item.text(), None)
            self.list_images.takeItem(self.list_images.row(item))

    # ------------------------------------------------------------------
    # Bắt đầu / dừng
    # ------------------------------------------------------------------
    def start_process(self) -> None:
        name = self.current_device()
        if not name:
            QMessageBox.information(self, "Thông báo", "Hãy chọn một máy ảo bên trái.")
            return
        avd = self._avds.get(name)
        if not avd or not avd.serial:
            QMessageBox.warning(self, "Thiết bị chưa chạy",
                                f"{name} chưa khởi động.\nHãy vào tab 'Danh sách thiết bị' và "
                                "bấm 'Khởi động ẩn (không màn hình)' trước.")
            return
        if not avd_manager.manager.is_running_headless(name):
            resp = QMessageBox.question(
                self, "Cảnh báo chế độ hiển thị",
                f"{name} đang chạy CÓ màn hình. Toàn bộ quy trình phải chạy ở chế độ ẨN "
                "(-no-window).\n\nBạn có muốn tắt và khởi động lại ẨN không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resp == QMessageBox.StandardButton.Yes:
                avd_manager.manager.kill(name, avd.serial)
                self.log_panel.append_log("Tắt máy để khởi động lại chế độ ẩn...", "warning")
                return
            self.log_panel.append_log("CẢNH BÁO: tiếp tục với thiết bị CÓ màn hình.", "warning")

        numbers = data_manager.clean_phone_text(self.txt_numbers.toPlainText())
        message = self.txt_message.toPlainText()
        image_paths = list(self._image_paths.values())
        interval = self.spin_interval.value()

        if not numbers:
            QMessageBox.information(self, "Thông báo", "Chưa có số điện thoại nào.")
            return
        if not message and not image_paths:
            QMessageBox.information(self, "Thông báo", "Chưa có nội dung tin nhắn hoặc ảnh.")
            return

        settings.set_device_config(name, {
            "numbers": self.txt_numbers.toPlainText(),
            "message": message,
            "images": image_paths,
            "interval": interval,
        })

        config = SendConfig(avd_name=name, phones=numbers, message=message,
                            images=image_paths, interval=interval)
        worker = BroadcastWorker(config, avd.serial)
        worker.log_signal.connect(lambda m, l: self.log_panel.append_log(m, l))
        worker.progress_signal.connect(self._on_progress)
        worker.finished_signal.connect(self._on_finished)
        self._workers[name] = worker
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setMaximum(len(numbers))
        self.progress_bar.setValue(0)
        self.lbl_progress.setText("0/" + str(len(numbers)))
        worker.start()
        self.log_panel.append_log(f"Đã chọn thiết bị {name} (serial {avd.serial}).", "info")

    def stop_process(self) -> None:
        name = self.current_device()
        worker = self._workers.get(name)
        if worker:
            self.log_panel.append_log("Yêu cầu dừng...", "warning")
            worker.stop()

    @Slot(int, int, int)
    def _on_progress(self, done: int, total: int, ok: int) -> None:
        self.progress_bar.setValue(done)
        self.lbl_progress.setText(f"{done}/{total} (thành công {ok})")

    @Slot(str, bool)
    def _on_finished(self, avd_name: str, success_all: bool) -> None:
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if avd_name in self._workers:
            self._workers.pop(avd_name, None)
