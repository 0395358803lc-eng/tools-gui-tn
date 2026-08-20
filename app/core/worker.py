"""Hàng đợi gửi tin hàng loạt - mỗi thiết bị 1 worker QThread chạy nền.

Dùng logging chuẩn: file `logs/<avd>.log` + handler nối UI (QtLogHandler).
"""
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QThread, Signal

from . import avd_manager
from .exceptions import ADBError, PartialSendError, WhatsAppError
from .logging_setup import attach_qt_handler, device_logger, log_success
from .whatsapp_bot import WhatsAppBot


@dataclass
class SendConfig:
    avd_name: str
    phones: list[str] = field(default_factory=list)
    message: str = ""
    images: list[str] = field(default_factory=list)
    interval: int = 5          # giây giữa mỗi tin


class BroadcastWorker(QThread):
    """Worker gửi tin cho 1 thiết bị."""

    log_signal = Signal(str, str)          # (message, level)
    progress_signal = Signal(int, int, int)  # (done, total, ok)
    finished_signal = Signal(str, bool)    # (avd_name, success_all)

    def __init__(self, config: SendConfig, serial: str, retries: int = 2, parent=None):
        super().__init__(parent)
        self.config = config
        self.serial = serial
        self.retries = max(0, retries)
        self._stop = False
        self._logger = device_logger(config.avd_name)
        attach_qt_handler(self._logger, self._emit_log)

    def stop(self) -> None:
        self._stop = True

    def _emit_log(self, message: str, level: str) -> None:
        self.log_signal.emit(message, level)

    def run(self) -> None:
        total = len(self.config.phones)
        ok = 0
        t_start = time.monotonic()
        self._logger.info(
            f"===== BẮT ĐẦU gửi {total} tin trên {self.config.avd_name} =====")
        try:
            headless = avd_manager.manager.is_running_headless(self.config.avd_name)
            if headless:
                log_success(self._logger, "Thiết bị đang chạy ở chế độ ẨN (-no-window). OK.")
            else:
                self._logger.warning(
                    "CẢNH BÁO: thiết bị đang chạy CÓ màn hình. Khuyến nghị khởi động ẩn "
                    "(-no-window) trước khi gửi hàng loạt.")

            bot = WhatsAppBot(self.serial, logger=self._logger)
            for idx, phone in enumerate(self.config.phones, start=1):
                if self._stop:
                    self._logger.warning("Đã dừng theo yêu cầu.")
                    break
                if not phone.strip():
                    continue
                phone = phone.strip()
                self._logger.info(f"[{idx}/{total}] Đang gửi tới {phone}...")
                last_err = None
                success = False
                t_phone = time.monotonic()
                for attempt in range(1, self.retries + 2):
                    if self._stop:
                        break
                    try:
                        bot.send_bulk(phone, self.config.message, self.config.images)
                        ok += 1
                        success = True
                        elapsed = time.monotonic() - t_phone
                        log_success(self._logger,
                                    f"[{idx}/{total}] GỬI THÀNH CÔNG tới {phone} "
                                    f"({elapsed:.1f}s).")
                        break
                    except PartialSendError as e:
                        # Một phần nội dung đã gửi thành công; retry toàn workflow sẽ tạo duplicate.
                        last_err = e
                        self._logger.error(
                            f"[{idx}/{total}] Đã gửi một phần, KHÔNG retry để tránh gửi trùng: {e}")
                        break
                    except (WhatsAppError, ADBError) as e:
                        last_err = e
                        self._logger.warning(
                            f"[{idx}/{total}] Lần thử {attempt}/{self.retries + 1} thất bại: {e}")
                    except Exception as e:  # noqa: BLE001 - lỗi không lường trước, không retry
                        last_err = e
                        self._logger.error(f"[{idx}/{total}] LỖI tới {phone}: {e}")
                        break
                elapsed = time.monotonic() - t_phone
                if not success and last_err is not None:
                    self._logger.error(
                        f"[{idx}/{total}] LỖI tới {phone}: {last_err} ({elapsed:.1f}s)")
                self.progress_signal.emit(idx, total, ok)
                if idx < total and not self._stop and self.config.interval > 0:
                    self._logger.info(f"Nghỉ {self.config.interval} giây trước tin kế tiếp...")
                    self._sleep_interval(self.config.interval)
        except Exception as e:  # noqa: BLE001
            self._logger.error(f"LỖI worker: {e}")
        self._logger.info(
            f"===== KẾT THÚC: {ok}/{total} thành công trên {self.config.avd_name} "
            f"(tổng {time.monotonic() - t_start:.1f}s) =====")
        self.finished_signal.emit(self.config.avd_name, ok == total)

    def _sleep_interval(self, seconds: int) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not self._stop:
            time.sleep(0.2)
