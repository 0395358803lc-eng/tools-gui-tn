"""Tự động hoá WhatsApp - chia thành các controller theo từng phần.

- WhatsAppAppController: mở app, kiểm tra onboarding (EULA), mở ContactPicker
- WhatsAppContactManager: tạo/lưu liên hệ, mở cuộc trò chuyện
- WhatsAppMessenger: gửi tin text / gửi ảnh kèm caption
- WhatsAppBot: facade điều phối toàn bộ quy trình cho 1 số điện thoại
"""
import logging
import time
from pathlib import Path
from typing import Optional

from . import adb
from . import uiautomator as ui
from . import whatsapp_selectors as sel
from .data_manager import normalize_phone
from .exceptions import ADBError, PartialSendError, WhatsAppError
from .logging_setup import log_success

ANR_PATTERN = "isn.t responding"


class _Base:
    """Chung: serial, logger và gõ văn bản (hỗ trợ ADBKeyboard)."""

    def __init__(self, serial: str, logger: Optional[logging.Logger] = None):
        self.serial = serial
        self._logger = logger or logging.getLogger("wa.bot")

    def _info(self, msg: str) -> None:
        self._logger.info(msg)

    def _ok(self, msg: str) -> None:
        log_success(self._logger, msg)

    def _warn(self, msg: str) -> None:
        self._logger.warning(msg)

    def _err(self, msg: str) -> None:
        self._logger.error(msg)

    def type_text(self, text: str) -> None:
        if not text:
            return
        if self._is_adbkeyboard():
            self._broadcast_adbkeyboard(text)
            return
        adb.input_text(self.serial, text)

    def _is_adbkeyboard(self) -> bool:
        out = adb.shell_args(self.serial, ["ime", "list", "-s"], timeout=10)
        return sel.ADB_IME in out

    def _broadcast_adbkeyboard(self, text: str) -> None:
        adb.shell_args(
            self.serial,
            ["am", "broadcast", "-a", sel.ADB_IME_INPUT_ACTION, "--es", "msg", text],
            timeout=10,
            check=True,
        )

    def _ensure_screen_ready(self, attempts: int = 4) -> None:
        """Bỏ qua hộp thoại '... isn't responding' (thường gặp khi chạy ẩn chậm)."""
        for _ in range(attempts):
            dump = ui.ui_dump(self.serial)
            if not dump:
                time.sleep(1)
                continue
            wait = dump.find(text="Wait")
            anr = dump.find_regex(ANR_PATTERN, attr="text")
            if anr is not None and wait is not None:
                self._warn("Phát hiện hộp thoại 'not responding', bấm Wait...")
                adb.tap(self.serial, *wait.center)
                time.sleep(2)
            else:
                return
        time.sleep(1)


class WhatsAppAppController(_Base):
    """Mở app WhatsApp và xử lý các màn hình chung (onboarding, picker)."""

    def open_app(self) -> None:
        self._info("Mở ứng dụng WhatsApp...")
        adb.shell(self.serial, f"am force-stop {sel.PKG}", timeout=15)
        time.sleep(1)
        adb.shell(self.serial, f"am start -n {sel.ACT_MAIN}", timeout=15)
        if not adb.wait_for_activity(self.serial, f"{sel.PKG}/", timeout=25):
            raise WhatsAppError("Không mở được WhatsApp (timeout chờ activity)")
        time.sleep(3)

    def ensure_onboarded(self) -> None:
        node = ui.wait_for_rid(self.serial, sel.RID_EULA_ACCEPT, timeout=8)
        if node is not None:
            self._info("Phát hiện màn chào mừng (EULA), bấm AGREE AND CONTINUE...")
            adb.tap(self.serial, *node.center)
            time.sleep(3)
            again = ui.wait_for_rid(self.serial, sel.RID_EULA_ACCEPT, timeout=6)
            if again is not None:
                adb.tap(self.serial, *again.center)
                time.sleep(3)
        else:
            self._info("Không có màn EULA (đã được thiết lập).")

    def open_contact_picker(self) -> None:
        self._info("Mở danh sách chọn liên hệ...")
        self._ensure_screen_ready()
        dump = ui.ui_dump(self.serial)
        node = sel.find_new_chat_button(dump) if dump else None
        if node is None:
            node = ui.wait_for(self.serial, lambda d: sel.find_new_chat_button(d), timeout=20)
        if node is None:
            raise WhatsAppError("Không tìm thấy nút New chat")
        adb.tap(self.serial, *node.center)
        if not adb.wait_for_activity(self.serial, sel.ACT_PICKER, timeout=20):
            self._warn("Không thấy ContactPicker ngay lập tức, vẫn tiếp tục...")
        time.sleep(2)


class WhatsAppContactManager(_Base):
    """Tạo/lưu liên hệ và mở cuộc trò chuyện."""

    def create_contact(self, phone: str) -> None:
        phone_digits = normalize_phone(phone)
        dump = ui.ui_dump(self.serial)
        if dump and any(sel.matches_phone(n.text, phone_digits) for n in dump.nodes):
            self._ok(f"Số {phone_digits} đã có trong danh bạ, bỏ qua tạo mới.")
            return

        new_contact = dump.find(text=sel.TEXT_NEW_CONTACT) if dump else None
        if new_contact is None:
            new_contact = ui.wait_for_text(self.serial, sel.TEXT_NEW_CONTACT, timeout=10)
        if new_contact is None:
            raise WhatsAppError("Không tìm thấy mục New contact")
        self._info("Tạo danh bạ mới...")
        adb.tap(self.serial, *new_contact.center)
        if not adb.wait_for_activity(self.serial, sel.ACT_CONTACT_FORM, timeout=15):
            raise WhatsAppError("Không mở được form tạo danh bạ")

        phone_field = ui.wait_for(self.serial, lambda d: sel.find_phone_field(d), timeout=10)
        if phone_field is None:
            phone_field = sel.FallbackCoord(sel.FALLBACK_PHONE_COORD)
        adb.tap(self.serial, *phone_field.center)
        time.sleep(0.5)
        self.type_text(phone_digits)
        time.sleep(0.5)

        save = ui.wait_for(self.serial, lambda d: sel.find_save_button(d), timeout=10)
        if save is None:
            raise WhatsAppError("Không tìm thấy nút SAVE")
        adb.tap(self.serial, *save.center)
        if not adb.wait_for_activity(self.serial, sel.ACT_PICKER, timeout=15):
            raise WhatsAppError("Lưu danh bạ xong nhưng không quay lại được màn chọn liên hệ")
        time.sleep(1)
        self._ok(f"Đã lưu danh bạ {phone_digits}.")

    def open_chat(self, phone: str) -> None:
        phone_digits = normalize_phone(phone)
        self._info(f"Mở cuộc trò chuyện với {phone_digits}...")
        self._ensure_screen_ready()

        row = None
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            dump = ui.ui_dump(self.serial)
            if dump:
                row = sel.find_contact_row(dump, phone_digits)
                if row:
                    break
            adb.swipe(self.serial, 672, 2000, 672, 1000, 300)
            time.sleep(0.5)
        if row is None:
            raise WhatsAppError(f"Không tìm thấy liên hệ {phone_digits} trong danh bạ")
        adb.tap(self.serial, *row.center)
        if not adb.wait_for_activity(self.serial, sel.ACT_CONVERSATION, timeout=15):
            adb.tap(self.serial, *row.center)
            if not adb.wait_for_activity(self.serial, sel.ACT_CONVERSATION, timeout=15):
                raise WhatsAppError("Không mở được cuộc trò chuyện")
        time.sleep(1)


class WhatsAppMessenger(_Base):
    """Gửi tin nhắn text hoặc một/nhiều ảnh kèm caption."""

    def send_text(self, message: str) -> None:
        self._info("Nhập tin nhắn...")
        msg_field = ui.wait_for(self.serial, lambda d: sel.find_message_field(d), timeout=10)
        if msg_field is None:
            raise WhatsAppError("Không tìm thấy ô nhập tin nhắn")
        adb.tap(self.serial, *msg_field.center)
        time.sleep(0.5)
        self.type_text(message)
        time.sleep(0.5)
        send_btn = ui.wait_for(self.serial, lambda d: sel.find_send_button(d), timeout=8)
        if send_btn is None:
            raise WhatsAppError("Không tìm thấy nút Send")
        adb.tap(self.serial, *send_btn.center)
        time.sleep(1)
        self._ok("Đã gửi tin nhắn.")

    def send_with_image(self, images: list[str], message: str) -> None:
        """Gửi từng ảnh tuần tự; không retry toàn workflow sau partial success."""
        if not images:
            raise WhatsAppError("Danh sách ảnh rỗng")

        sent = 0
        for index, path in enumerate(images):
            caption = message if index == 0 else ""
            try:
                self._send_single_image(path, caption, index=index)
            except (WhatsAppError, ADBError) as exc:
                if sent > 0:
                    raise PartialSendError(
                        f"Đã gửi {sent}/{len(images)} ảnh; lỗi tại ảnh {index + 1}. "
                        f"Dừng retry để tránh gửi trùng. Chi tiết: {exc}"
                    ) from exc
                raise
            sent += 1
            self._ok(f"Đã gửi ảnh {sent}/{len(images)}.")
        self._ok(f"Đã gửi đủ {sent}/{len(images)} ảnh.")

    def _send_single_image(self, path: str, message: str, *, index: int) -> None:
        remote_path = self._push_image(path, index=index)

        attach = ui.wait_for(self.serial, lambda d: sel.find_attach_button(d), timeout=10)
        if attach is None:
            raise WhatsAppError(f"Không tìm thấy nút Attach khi gửi ảnh {index + 1}")
        adb.tap(self.serial, *attach.center)
        time.sleep(2)

        gallery = ui.wait_for_text(self.serial, sel.TEXT_GALLERY, timeout=8)
        if gallery is None:
            raise WhatsAppError(f"Không tìm thấy mục Gallery khi gửi ảnh {index + 1}")
        adb.tap(self.serial, *gallery.center)
        time.sleep(3)

        first = ui.wait_for(self.serial, lambda d: sel.find_first_media_thumbnail(d), timeout=20)
        if first is None:
            self._warn(f"Chưa thấy thumbnail ảnh {index + 1}, quét media lại...")
            self._scan_media(remote_path)
            time.sleep(3)
            first = ui.wait_for(self.serial, lambda d: sel.find_first_media_thumbnail(d), timeout=15)
        if first is None:
            raise WhatsAppError(f"Không tìm thấy ảnh {index + 1} trong gallery")
        adb.tap(self.serial, *first.center)
        time.sleep(2)

        if message:
            caption = ui.wait_for(self.serial, lambda d: sel.find_caption_field(d), timeout=8)
            if caption is not None:
                adb.tap(self.serial, *caption.center)
                time.sleep(0.5)
                self.type_text(message)
                time.sleep(0.5)
            else:
                self._warn("Không thấy ô caption, gửi ảnh đầu tiên không kèm nội dung.")

        send = ui.wait_for(self.serial, lambda d: sel.find_send_media_button(d), timeout=10)
        if send is None:
            raise WhatsAppError(f"Không tìm thấy nút gửi ảnh {index + 1}")
        adb.tap(self.serial, *send.center)
        time.sleep(1)

    def _push_image(self, path: str, *, index: int) -> str:
        local = Path(path)
        suffix = local.suffix.lower() or ".jpg"
        unique = time.time_ns()
        dest = f"/sdcard/Pictures/wa_send_{index}_{unique}{suffix}"
        self._info(f"Đẩy ảnh {index + 1} lên thiết bị...")
        adb._run(
            [adb.adb_path(), "-s", self.serial, "push", path, dest],
            timeout=60,
            check=True,
        )
        adb.shell_args(self.serial, ["touch", dest], timeout=10, check=True)
        self._scan_media(dest)
        return dest

    def _scan_media(self, remote_path: str) -> None:
        adb.shell_args(
            self.serial,
            [
                "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d", f"file://{remote_path}",
            ],
            timeout=15,
            check=True,
        )


class WhatsAppBot:
    """Facade: phối hợp toàn bộ quy trình gửi tin cho 1 số điện thoại."""

    def __init__(self, serial: str, logger: Optional[logging.Logger] = None):
        self.serial = serial
        self.app = WhatsAppAppController(serial, logger)
        self.contacts = WhatsAppContactManager(serial, logger)
        self.messenger = WhatsAppMessenger(serial, logger)

    def send_bulk(self, phone: str, message: str, images: list[str]) -> None:
        self.app.open_app()
        self.app.ensure_onboarded()
        self.app.open_contact_picker()
        self.contacts.create_contact(phone)
        self.contacts.open_chat(phone)
        if images:
            self.messenger.send_with_image(images, message)
        else:
            self.messenger.send_text(message)
