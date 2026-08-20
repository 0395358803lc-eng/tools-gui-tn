"""Cấu hình logging chuẩn Python.

- File log riêng mỗi thiết bị trong user-data `logs/<avd_name>.log`
- QtLogHandler để nối log vào UI (phải emit signal từ thread làm việc)
- Có mức level tuỳ chỉnh SUCCESS để UI hiển thị màu xanh lá
"""
import logging
from logging.handlers import RotatingFileHandler
from typing import Callable

from . import paths

LOGS_DIR = paths.logs_dir()

SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


def mask_phone(value: str, prefix: int = 3, suffix: int = 2) -> str:
    """Che phần lớn số điện thoại trước khi ghi log/UI diagnostics."""
    text = str(value or "")
    if not text:
        return ""
    prefix = max(0, int(prefix))
    suffix = max(0, int(suffix))
    visible = prefix + suffix
    if len(text) <= visible:
        return "*" * len(text)
    head = text[:prefix] if prefix else ""
    tail = text[-suffix:] if suffix else ""
    return head + "*" * (len(text) - visible) + tail


class QtLogHandler(logging.Handler):
    """Handler forwarding bản ghi log sang UI (message, level_lowercase)."""

    def __init__(self, emit_callable: Callable[[str, str], None]):
        super().__init__()
        self._emit_callable = emit_callable

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emit_callable(self.format(record), record.levelname.lower())
        except Exception:  # noqa: BLE001 - lỗi UI không được làm chết worker
            pass


def device_logger(avd_name: str) -> logging.Logger:
    """Logger riêng cho 1 thiết bị, ghi ra user-data `logs/<avd_name>.log`."""
    name = f"wa.{avd_name}"
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        LOGS_DIR / f"{avd_name}.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)
    return logger


def attach_qt_handler(logger: logging.Logger, emit_callable: Callable[[str, str], None]) -> None:
    """Gắn handler UI cho logger (thay thế handler UI cũ để tránh trùng lặp)."""
    for h in list(logger.handlers):
        if isinstance(h, QtLogHandler):
            logger.removeHandler(h)
    qt = QtLogHandler(emit_callable)
    qt.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(qt)


def log_success(logger: logging.Logger, message: str) -> None:
    logger.log(SUCCESS_LEVEL, message)
