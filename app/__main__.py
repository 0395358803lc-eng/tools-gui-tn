"""Entry point: chạy bằng `python -m app`, `python main.py` hoặc exe đóng gói.

Hỗ trợ `--self-test`: kiểm tra import các module chính rồi thoát (dùng để verify exe).
"""
import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def _self_test() -> int:
    import app.core.settings      # noqa: F401
    import app.core.data_manager  # noqa: F401
    import app.ui.main_window     # noqa: F401
    import app.core.worker        # noqa: F401
    print("SELF-TEST OK: all main modules imported")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return _self_test()
    app = QApplication(sys.argv)
    app.setApplicationName("Tools Tự Động Gửi Tin Nhắn WhatsApp")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
