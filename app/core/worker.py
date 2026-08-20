"""Hàng đợi gửi tin hàng loạt - mỗi thiết bị 1 worker QThread chạy nền."""
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QThread, Signal

from . import avd_manager
from .broadcast_result import BroadcastReport, RecipientResult, RecipientStatus
from .exceptions import ADBError, PartialSendError, WhatsAppError
from .logging_setup import attach_qt_handler, device_logger, log_success, mask_phone
from .preflight import run_device_preflight, validate_broadcast_inputs
from .report_export import export_csv, export_xlsx
from .whatsapp_bot import WhatsAppBot
from .whatsapp_state import return_home_best_effort


@dataclass
class SendConfig:
    avd_name: str
    phones: list[str] = field(default_factory=list)
    message: str = ""
    images: list[str] = field(default_factory=list)
    interval: int = 5


class BroadcastWorker(QThread):
    """Worker gửi tin cho 1 thiết bị, kèm preflight và structured report."""

    log_signal = Signal(str, str)
    progress_signal = Signal(int, int, int)
    finished_signal = Signal(str, bool)
    result_signal = Signal(object)
    report_signal = Signal(object)

    def __init__(self, config: SendConfig, serial: str, retries: int = 2,
                 retry_backoff: float = 1.0, max_consecutive_failures: int = 5,
                 minimum_interval: float = 1.0, auto_export_reports: bool = True,
                 parent=None):
        super().__init__(parent)
        self.config = config
        self.serial = serial
        self.retries = max(0, retries)
        self.retry_backoff = max(0.0, float(retry_backoff))
        self.max_consecutive_failures = max(1, int(max_consecutive_failures))
        self.minimum_interval = max(0.0, float(minimum_interval))
        self.auto_export_reports = bool(auto_export_reports)
        self._stop = False
        self._logger = device_logger(config.avd_name)
        attach_qt_handler(self._logger, self._emit_log)
        self.report = BroadcastReport(avd_name=config.avd_name, serial=serial)

    def stop(self) -> None:
        self._stop = True

    def _emit_log(self, message: str, level: str) -> None:
        self.log_signal.emit(message, level)

    def _log_preflight(self, title: str, result) -> None:
        self._logger.info(f"--- Preflight {title} ---")
        for check in result.checks:
            if check.ok:
                self._logger.info(f"[OK] {check.code}: {check.detail}")
            elif check.required:
                self._logger.error(f"[FAIL] {check.code}: {check.detail}")
            else:
                self._logger.warning(f"[WARN] {check.code}: {check.detail}")

    def _record_preflight_failure(self, result) -> None:
        self.report.preflight_ok = False
        self.report.preflight_errors.extend(
            f"{check.code}: {check.detail}" for check in result.errors
        )

    def _preflight_ok(self) -> bool:
        local = validate_broadcast_inputs(
            self.config.phones,
            self.config.message,
            self.config.images,
            self.config.interval,
        )
        self._log_preflight("dữ liệu", local)
        if not local.ok:
            self._record_preflight_failure(local)
            return False

        require_unicode = any(ord(ch) > 127 for ch in (self.config.message or ""))
        device = run_device_preflight(self.serial, require_unicode=require_unicode)
        self._log_preflight("thiết bị", device)
        if not device.ok:
            self._record_preflight_failure(device)
            return False
        return True

    def _add_result(self, result: RecipientResult) -> None:
        self.report.add(result)
        self.result_signal.emit(result)

    def _finalize_report(self) -> None:
        if not self.report.completed_at:
            self.report.finish()
        if self.auto_export_reports:
            try:
                csv_path = export_csv(self.report)
                xlsx_path = export_xlsx(self.report)
                self._logger.info(f"Đã xuất report CSV: {csv_path}")
                self._logger.info(f"Đã xuất report XLSX: {xlsx_path}")
            except Exception as exc:  # noqa: BLE001 - export không được đổi kết quả batch
                self._logger.warning(f"Không xuất được report: {exc}")
        self.report_signal.emit(self.report)

    def _finish(self, success_all: bool) -> None:
        self._finalize_report()
        self.finished_signal.emit(self.config.avd_name, success_all)

    def run(self) -> None:
        phones = [p.strip() for p in self.config.phones if p and p.strip()]
        total = len(phones)
        ok = 0
        consecutive_failures = 0
        t_start = time.monotonic()
        self._logger.info(
            f"===== BẮT ĐẦU gửi {total} tin trên {self.config.avd_name} =====")
        try:
            if self._stop:
                self.report.preflight_ok = False
                self.report.preflight_errors.append("cancelled_before_preflight")
                self._logger.warning("Đã dừng trước khi chạy preflight.")
                self._finish(False)
                return

            if not self._preflight_ok():
                self._logger.error("PREFLIGHT THẤT BẠI: batch không được bắt đầu.")
                self._finish(False)
                return

            if self._stop:
                self._logger.warning("Đã dừng sau preflight.")
                self._finish(False)
                return

            headless = avd_manager.manager.is_running_headless(self.config.avd_name)
            if headless:
                log_success(self._logger, "Thiết bị đang chạy ở chế độ ẨN (-no-window). OK.")
            else:
                self._logger.warning(
                    "CẢNH BÁO: thiết bị đang chạy CÓ màn hình. Khuyến nghị khởi động ẩn "
                    "(-no-window) trước khi gửi hàng loạt.")

            bot = WhatsAppBot(
                self.serial,
                logger=self._logger,
                cancelled=lambda: self._stop,
            )
            for idx, phone in enumerate(phones, start=1):
                if self._stop:
                    self._logger.warning("Đã dừng theo yêu cầu.")
                    break

                phone_label = mask_phone(phone)
                self._logger.info(f"[{idx}/{total}] Đang gửi tới {phone_label}...")
                last_err = None
                success = False
                partial = False
                attempts_made = 0
                t_phone = time.monotonic()

                for attempt in range(1, self.retries + 2):
                    if self._stop:
                        break
                    attempts_made = attempt
                    try:
                        bot.send_bulk(phone, self.config.message, self.config.images)
                        if not self._stop:
                            reused = return_home_best_effort(
                                self.serial,
                                cancelled=lambda: self._stop,
                            )
                            if not reused:
                                self._logger.warning(
                                    "Không đưa được WhatsApp về HOME sau khi gửi; "
                                    "recipient kế tiếp sẽ fallback về workflow restart."
                                )
                        ok += 1
                        success = True
                        elapsed = time.monotonic() - t_phone
                        log_success(self._logger,
                                    f"[{idx}/{total}] GỬI THÀNH CÔNG tới {phone_label} "
                                    f"({elapsed:.1f}s).")
                        break
                    except PartialSendError as e:
                        last_err = e
                        partial = True
                        self._logger.error(
                            f"[{idx}/{total}] Đã gửi một phần, KHÔNG retry để tránh gửi trùng: {e}")
                        break
                    except (WhatsAppError, ADBError) as e:
                        last_err = e
                        if self._stop:
                            break
                        self._logger.warning(
                            f"[{idx}/{total}] Lần thử {attempt}/{self.retries + 1} thất bại: {e}")
                        if attempt <= self.retries:
                            delay = self.retry_backoff * attempt
                            if delay > 0:
                                self._logger.info(f"Chờ {delay:.1f}s trước lần retry tiếp theo...")
                                self._sleep_interval(delay)
                    except Exception as e:  # noqa: BLE001
                        last_err = e
                        self._logger.error(f"[{idx}/{total}] LỖI tới {phone_label}: {e}")
                        break

                elapsed = time.monotonic() - t_phone
                if success:
                    status = RecipientStatus.SUCCESS
                    error_code = ""
                    error_message = ""
                elif self._stop:
                    status = RecipientStatus.CANCELLED
                    error_code = "Cancelled"
                    error_message = "Đã dừng theo yêu cầu"
                elif partial:
                    status = RecipientStatus.PARTIAL
                    error_code = type(last_err).__name__ if last_err else "PartialSendError"
                    error_message = str(last_err or "")
                else:
                    status = RecipientStatus.FAILED
                    error_code = type(last_err).__name__ if last_err else "UnknownError"
                    error_message = str(last_err or "Không xác định")

                recipient_result = RecipientResult(
                    avd_name=self.config.avd_name,
                    serial=self.serial,
                    phone=phone,
                    status=status,
                    attempts=attempts_made,
                    elapsed_seconds=elapsed,
                    error_code=error_code,
                    error_message=error_message,
                )
                self._add_result(recipient_result)

                if self._stop:
                    self._logger.warning("Đã dừng theo yêu cầu.")
                    break

                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if last_err is not None:
                        self._logger.error(
                            f"[{idx}/{total}] LỖI tới {phone_label}: {last_err} ({elapsed:.1f}s)")

                self.progress_signal.emit(idx, total, ok)

                if (not success
                        and consecutive_failures >= self.max_consecutive_failures
                        and idx < total):
                    self._logger.error(
                        "CIRCUIT BREAKER: dừng batch sau "
                        f"{consecutive_failures} recipient lỗi liên tiếp.")
                    break

                if idx < total and not self._stop:
                    delay = max(float(self.config.interval), self.minimum_interval)
                    if delay > 0:
                        if self.config.interval < self.minimum_interval:
                            self._logger.info(
                                f"Interval yêu cầu {self.config.interval}s thấp hơn mức tối thiểu; "
                                f"dùng {delay:.1f}s.")
                        else:
                            self._logger.info(f"Nghỉ {delay:.1f} giây trước tin kế tiếp...")
                        self._sleep_interval(delay)
        except Exception as e:  # noqa: BLE001
            self._logger.error(f"LỖI worker: {e}")
        self._logger.info(
            f"===== KẾT THÚC: {ok}/{total} thành công trên {self.config.avd_name} "
            f"(tổng {time.monotonic() - t_start:.1f}s) =====")
        self._finish(ok == total)

    def _sleep_interval(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not self._stop:
            time.sleep(0.2)
