"""Preflight checks trước khi bắt đầu batch automation."""
from dataclasses import dataclass, field
from pathlib import Path

from . import adb, uiautomator as ui
from . import whatsapp_selectors as sel
from .data_manager import is_phone_like, normalize_phone
from .exceptions import ADBError

_ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class PreflightCheck:
    code: str
    ok: bool
    detail: str
    required: bool = True


@dataclass
class PreflightResult:
    checks: list[PreflightCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks if check.required)

    @property
    def errors(self) -> list[PreflightCheck]:
        return [check for check in self.checks if check.required and not check.ok]

    @property
    def warnings(self) -> list[PreflightCheck]:
        return [check for check in self.checks if not check.required and not check.ok]

    def add(self, code: str, ok: bool, detail: str, *, required: bool = True) -> None:
        self.checks.append(PreflightCheck(code, ok, detail, required))


def validate_broadcast_inputs(
    phones: list[str],
    message: str,
    images: list[str],
    interval: int | float,
) -> PreflightResult:
    """Validate dữ liệu local, không gọi ADB."""
    result = PreflightResult()
    cleaned = [normalize_phone(phone) for phone in phones if str(phone or "").strip()]
    valid = [phone for phone in cleaned if is_phone_like(phone)]
    invalid_count = len(cleaned) - len(valid)

    result.add("phones_present", bool(valid), f"{len(valid)} số hợp lệ")
    result.add(
        "phones_valid",
        invalid_count == 0,
        f"{invalid_count} số không hợp lệ" if invalid_count else "Không có số sai định dạng",
    )

    duplicate_count = len(valid) - len(set(valid))
    result.add(
        "phones_unique",
        duplicate_count == 0,
        f"Có {duplicate_count} số trùng; nên dọn trước khi gửi",
        required=False,
    )

    result.add(
        "content_present",
        bool((message or "").strip() or images),
        "Có nội dung text/ảnh" if ((message or "").strip() or images) else "Thiếu text và ảnh",
    )

    missing_images = [path for path in images if not Path(path).is_file()]
    bad_types = [
        path for path in images
        if Path(path).suffix.lower() not in _ALLOWED_IMAGE_SUFFIXES
    ]
    result.add(
        "images_exist",
        not missing_images,
        f"Thiếu {len(missing_images)} file ảnh" if missing_images else "Các file ảnh đều tồn tại",
    )
    result.add(
        "image_types",
        not bad_types,
        f"Có {len(bad_types)} file ảnh không hỗ trợ" if bad_types else "Định dạng ảnh hợp lệ",
    )
    result.add(
        "interval_nonnegative",
        float(interval) >= 0,
        f"Interval={interval}",
    )
    return result


def run_device_preflight(serial: str, *, require_unicode: bool = False) -> PreflightResult:
    """Kiểm tra ADB/device/WhatsApp/UI hierarchy trước batch."""
    result = PreflightResult()

    adb_version = adb.run_command([adb.adb_path(), "version"], timeout=10)
    result.add(
        "adb_available",
        adb_version.ok,
        "ADB hoạt động" if adb_version.ok else "Không chạy được ADB",
    )
    if not adb_version.ok:
        return result

    online = serial in adb.devices()
    result.add(
        "device_online",
        online,
        f"Thiết bị {serial} online" if online else f"Không thấy thiết bị {serial}",
    )
    if not online:
        return result

    booted = adb.is_boot_completed(serial)
    result.add(
        "boot_completed",
        booted,
        "Android boot hoàn tất" if booted else "Android chưa boot hoàn tất",
    )
    if not booted:
        return result

    try:
        package_out = adb.shell_args(
            serial,
            ["pm", "path", sel.PKG],
            timeout=10,
            check=True,
        )
        whatsapp_installed = "package:" in package_out
    except ADBError:
        whatsapp_installed = False
    result.add(
        "whatsapp_installed",
        whatsapp_installed,
        "WhatsApp package tồn tại" if whatsapp_installed else "Không tìm thấy WhatsApp package",
    )
    if not whatsapp_installed:
        return result

    dump = ui.ui_dump(serial, retries=1, delay=0)
    result.add(
        "ui_dump",
        dump is not None,
        f"UI hierarchy đọc được ({len(dump.nodes)} nodes)" if dump else "Không đọc được UI hierarchy",
    )

    if require_unicode:
        try:
            ime_out = adb.shell_args(serial, ["ime", "list", "-s"], timeout=10, check=True)
            adb_keyboard = sel.ADB_IME in ime_out
        except ADBError:
            adb_keyboard = False
        result.add(
            "adb_keyboard",
            adb_keyboard,
            "ADBKeyboard sẵn sàng" if adb_keyboard else "Không thấy ADBKeyboard; Unicode fallback có thể hạn chế",
            required=False,
        )

    return result
