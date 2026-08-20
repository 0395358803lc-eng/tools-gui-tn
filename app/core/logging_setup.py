"""Cấu hình logging chuẩn Python.

- File log riêng mỗi thiết bị: `logs/<avd_name>.log`
- QtLogHandler để nối log vào UI (phải emit signal từ thread làm việc)
- Có mức level tuỳ chỉnh SUCCESS để UI hiển thị màu xanh lá
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).resolve().parent
else:
    _BASE_DIR = Path(__file__).resolve().parents[2]
LOGS_DIR = _BASE_DIR / "logs"

SUCCESS_LEVEL = 25
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")


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
    """Logger riêng cho 1 thiết bị, ghi ra `logs/<avd_name>.log`."""
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
