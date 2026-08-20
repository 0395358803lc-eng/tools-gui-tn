"""Các lỗi chung của ứng dụng - tránh catch generic Exception tràn lan."""


class AppError(Exception):
    """Lỗi gốc của toàn bộ ứng dụng."""


class ADBError(AppError):
    """Lỗi khi tương tác với adb / thiết bị."""


class AVDError(AppError):
    """Lỗi khi quản lý máy ảo (khởi động, tắt, trạng thái)."""


class WhatsAppError(AppError):
    """Lỗi trong quy trình tự động hoá WhatsApp."""


class DataError(AppError):
    """Lỗi khi xử lý dữ liệu nhập vào (số điện thoại, file Excel/CSV)."""


class ConfigError(AppError):
    """Lỗi khi lưu/nạp cấu hình."""
