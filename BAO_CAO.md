# BÁO CÁO KẾ HOẠCH
## Ứng dụng tự động gửi tin nhắn WhatsApp hàng loạt qua máy ảo Android Studio

**Ngày lập:** 06/08/2026
**Môi trường:** Windows, Python 3.14.5, Android SDK (emulator, adb)

---

## 1. Mục tiêu

Xây dựng ứng dụng desktop Windows tự động hoá quy trình gửi tin nhắn WhatsApp hàng loạt trên các máy ảo Android Studio (AVD) bằng cách tái sử dụng quy trình thao tác đã xây dựng và kiểm chứng (mở WhatsApp → tạo danh bạ → mở chat → nhập nội dung → gửi).

## 2. Công nghệ lựa chọn

| Thành phần | Lựa chọn | Lý do |
|---|---|---|
| Ngôn ngữ | Python 3.14.5 | Đã cài sẵn, dễ tích hợp adb |
| GUI | PySide6 6.11 | Đã cài sẵn, giao diện chuyên nghiệp |
| Tự động hoá | adb + uiautomator | Tái sử dụng quy trình đã kiểm chứng |
| Import Excel/CSV | openpyxl 3.1.2 / pandas 3.0.3 | Đã cài sẵn |
| Lưu cấu hình | JSON | Đơn giản, phổ biến |

## 3. Môi trường đã khảo sát

- Android SDK: `C:\Users\Admin\AppData\Local\Android\Sdk`
- Android Studio: `C:\Program Files\Android\Android Studio` (đang chạy)
- Emulator hỗ trợ chạy ẩn: `-no-window -no-audio -no-boot-anim`
- 5 AVD có sẵn: `test_whatsap_-1`, `whatsapp_device_01` → `04` (đều Android 16, google_apis x86_64)
- WhatsApp đã cài trên máy ảo, quy trình gửi tin đã kiểm chứng thành công trên `whatsapp_device_01` (emulator-5558)

### 3.1. Resource-ID đã xác minh trên WhatsApp

| Màn hình | Thành phần | Selector |
|---|---|---|
| EULA/Onboarding | Nút "AGREE AND CONTINUE" | `com.whatsapp:id/eula_accept` |
| Home | Nút New chat (FAB) | `com.whatsapp:id/fab` (content-desc "New chat") |
| ContactPicker | Mục "New contact" | text="New contact" |
| ContactForm | Ô nhập Phone | EditText hint="Phone" |
| ContactForm | Nút SAVE | `com.whatsapp:id/keyboard_aware_save_button` |
| Conversation | Ô nhập tin nhắn | EditText text/hint="Message" |
| Conversation | Nút gửi | content-desc="Send" |
| Conversation | Nút đính kèm | content-desc="Attach" |
| Bottom sheet | Mục Gallery | text="Gallery" |

## 4. Yêu cầu tính năng

### 4.1. Danh mục Danh sách thiết bị
- Hiển thị toàn bộ máy ảo Android Studio (tên AVD, model, trạng thái, serial adb)
- **Khởi động ẩn**: khởi động từng máy ở chế độ không màn hình (`-no-window`)
- Khởi động có màn hình (hỗ trợ setup thủ công), Tắt máy, Làm mới
- Tự cập nhật trạng thái định kỳ

### 4.2. Danh mục Gửi tin nhắn hàng loạt
- **QUAN TRỌNG**: Toàn bộ quy trình gửi tin nhắn hàng loạt phải thực thi khi máy ảo chạy ở chế độ **ẩn (headless, `-no-window`)** — không hiển thị màn hình. Ứng dụng tự động bắt đầu gửi **chỉ khi** thiết bị ở chế độ ẩn; nếu thiết bị đang hiển thị màn hình sẽ có cảnh báo trong log (nhưng vẫn cho phép gửi nếu người dùng xác nhận).
- Cột trái: danh sách máy ảo; ấn vào máy nào → cột phải hiển thị cấu hình riêng cho máy đó
- Ô nhập danh sách số điện thoại (mỗi dòng 1 số) + **Import Excel/CSV**
- Ô nhập nội dung tin nhắn (đa dòng)
- Thêm 1 hoặc nhiều hình ảnh gửi kèm (không bắt buộc)
- Cấu hình khoảng cách giữa mỗi tin (giây)
- Nút **Bắt đầu quy trình** / **Dừng**
- **Log** hiển thị dữ liệu làm việc theo thời gian thực trên thiết bị đang chọn

## 5. Kiến trúc dự án

```
tools-tu-dong-gui-tn/
├── main.py                    # Entry point (python main.py)
├── pyproject.toml             # Đóng gói + config pytest
├── requirements.txt
├── BAO_CAO.md                 # Báo cáo này
├── app/
│   ├── __main__.py            # python -m app
│   ├── core/
│   │   ├── __init__.py
│   │   ├── adb.py             # Wrapper lệnh adb cơ bản (shell, tap, swipe, text, emu kill)
│   │   ├── uiautomator.py     # Node/UiDump, ui_dump, wait_for tìm selector
│   │   ├── avd_manager.py     # AVDController: danh sách, khởi động ẩn/có màn hình, trạng thái, tắt
│   │   ├── whatsapp_bot.py    # AppController / ContactManager / Messenger + WhatsAppBot facade
│   │   ├── whatsapp_selectors.py  # Toàn bộ selector, activity, intent + hàm tìm node
│   │   ├── data_manager.py    # Chuẩn hoá số, dọn dữ liệu, import Excel/CSV
│   │   ├── worker.py          # BroadcastWorker (QThread): hàng đợi gửi, retry, dừng an toàn
│   │   ├── logging_setup.py   # Logging chuẩn: file logs/<avd>.log + handler nối UI
│   │   ├── settings.py        # Config JSON + default_settings.json (pathlib)
│   │   └── exceptions.py      # Các lỗi chung của ứng dụng
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py     # Cửa sổ chính, 2 tab, lưu/khôi phục window state
│       ├── devices_tab.py     # Danh mục danh sách thiết bị
│       ├── broadcast_tab.py   # Danh mục gửi tin hàng loạt (chỉ hiển thị/tương tác)
│       └── log_panel.py       # Widget hiển thị log màu theo mức, auto-scroll
├── config/
│   ├── default_settings.json  # Giá trị mặc định
│   └── settings.json          # Cấu hình lưu lại (tự khởi tạo)
├── logs/                      # Log riêng mỗi thiết bị (RotatingFileHandler)
└── tests/
    ├── core/
    │   ├── test_data_manager.py
    │   ├── test_settings.py
    │   ├── test_uiautomator.py
    │   ├── test_whatsapp_selectors.py
    │   └── test_adb_avd.py
```

## 6. Chi tiết module

### 6.1. `core/adb.py`
- Tự tìm adb theo `ANDROID_HOME` / `ANDROID_SDK_ROOT`
- `devices()`, `shell(serial, cmd)`, `exec_out(serial, cmd)`, `emu_kill(serial)`
- `tap`, `swipe`, `input_text`, `keyevent`, `wait_for_activity`, `is_boot_completed`
- Không chứa logic phân tích UI (tách sang `uiautomator.py`)

### 6.2. `core/uiautomator.py`
- `Node` / `UiDump`: parse XML hierarchy → tìm node theo text/content-desc/resource-id
- `ui_dump()`: retry khi `uiautomator dump` lỗi (đã gặp trong khảo sát)
- `wait_for`, `wait_for_text`, `wait_for_rid`

### 6.3. `core/avd_manager.py`
- `AVDController` quản lý toàn bộ lifecycle AVD (danh sách, khởi động, tắt, chờ boot)
- `launch(avd, headless=True)`: `emulator -avd <tên> -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect` (subprocess.Popen, chạy nền, **không hiển thị màn hình**)
- `launch(avd, headless=False)`: chế độ có màn hình (chỉ dùng để setup thủ công ban đầu)
- `is_running_headless()`: khớp chính xác `-avd <tên>` để tránh nhầm AVD tên tương tự
- `kill()`: ưu tiên `adb -s <serial> emu kill` rồi terminate tiến trình đã theo dõi
- `wait_boot(serial, timeout)`: poll `sys.boot_completed`

### 6.4. `core/whatsapp_bot.py`
Quy trình gửi tin cho từng số (tái hiện quy trình đã kiểm chứng):
1. `WhatsAppAppController.open_app()`: khởi động `com.whatsapp/.Main`
2. `ensure_onboarded()`: phát hiện màn EULA → bấm "AGREE AND CONTINUE" (`eula_accept`)
3. `open_contact_picker()`: bấm FAB New chat → chờ ContactPicker
4. `WhatsAppContactManager.create_contact(phone)`: bấm "New contact" → nhập số vào ô Phone → bấm SAVE; bỏ qua nếu số đã tồn tại
5. `open_chat(phone)`: bấm dòng liên hệ tương ứng
6. `WhatsAppMessenger.send_text(message)`: bấm ô Message → nhập nội dung → bấm Send
7. `send_with_image(images, message)`: `adb push` ảnh → Attach → Gallery → chọn ảnh → (caption) → Send
8. Nghỉ theo khoảng cách cấu hình → chuyển số kế tiếp

Toàn bộ selector, activity, intent tập trung tại `whatsapp_selectors.py`. Tất cả bước có `ui_dump` + timeout + retry, lỗi ném kèm ngữ cảnh để ghi log.

### 6.5. `core/data_manager.py`
- `normalize_phone()`: lọc chỉ giữ ký tự số
- `clean_phone_text()`: dọn từng dòng dữ liệu nhập tay
- `import_phones_from_file()`: đọc Excel/CSV, tự nhận diện cột số điện thoại

### 6.6. `core/worker.py`
- `BroadcastWorker` (QThread): mỗi máy ảo 1 worker riêng, chạy song song không treo UI
- Retry theo lỗi WhatsAppError, dừng an toàn giữa các tin, đếm thành công/thất bại
- Cảnh báo nếu thiết bị chạy CÓ màn hình (yêu cầu chạy ẩn `-no-window`)
- Dùng `logging` chuẩn: file `logs/<avd>.log` (RotatingFileHandler) + handler nối UI

### 6.7. `core/settings.py`
- Lưu/nạp JSON bằng `pathlib.Path`, tự khởi tạo `config/settings.json` từ `default_settings.json`
- Cấu hình riêng từng thiết bị + lưu/khôi phục window state, tab đang chọn

## 7. Thiết kế giao diện

### 7.1. Tab "Danh sách thiết bị"
- Thanh công cụ: Làm mới | Khởi động ẩn | Khởi động có màn hình | Tắt máy
- Bảng: Tên AVD | Model | Trạng thái | Serial adb
- Tự làm mới trạng thái mỗi 5 giây

### 7.2. Tab "Gửi tin nhắn hàng loạt"
- QSplitter: trái = danh sách máy ảo, phải = panel cấu hình của máy đang chọn
- Panel cấu hình:
  - Header: tên + trạng thái thiết bị
  - Danh sách số điện thoại (mỗi dòng 1 số) + nút Import Excel/CSV + nút Dọn dữ liệu
  - Nội dung tin nhắn (đa dòng)
  - Hình ảnh kèm (không bắt buộc): danh sách ảnh + Thêm ảnh + Xoá
  - Khoảng cách giữa mỗi tin (SpinBox 0–600 giây)
  - Nút Bắt đầu quy trình / Dừng
  - Log panel: màu theo mức (thông tin/thành công/lỗi), auto-scroll, ghi ra `logs/<thiết bị>.log`
  - Tiến trình: progress bar + "đã gửi x/y"

## 8. Xử lý dữ liệu số điện thoại

- Import Excel/CSV: đọc sheet đầu tiên, tự nhận diện cột chứa số (ô dạng số > 50%), đổ mỗi số vào 1 dòng
- Nút "Dọn dữ liệu": lọc chỉ giữ ký tự số, bỏ khoảng trắng/dấu `+`/`-`
- Chuẩn hoá: 11 chữ số bắt đầu bằng 1 → định dạng US; còn lại giữ nguyên dãy số

## 9. Kế hoạch kiểm thử

1. List AVD + khởi động ẩn `whatsapp_device_01` (`-no-window`) → xác nhận boot xong, **không có cửa sổ hiển thị**
2. Gửi thử 1 số, nội dung "hello" (không ảnh) — toàn bộ trong chế độ ẩn
3. Gửi thử 1 số kèm 1 ảnh — chế độ ẩn
4. Gửi batch 2 số, khoảng cách 3 giây → kiểm log, thứ tự, nút Dừng
5. Import file Excel có sẵn trong thư mục dự án

## 10. Lưu ý / rủi ro

| Rủi ro | Giải pháp |
|---|---|
| Máy ảo mới chưa đăng ký WhatsApp | Setup thủ công 1 lần (nhập số, nhận mã SMS) rồi snapshot; tool tự xử lý màn EULA |
| `adb input text` không gõ được tiếng Việt/unicode | Cài ADBKeyboard trên máy ảo để gõ đầy đủ; fallback `%s` cho khoảng trắng |
| `uiautomator dump` lỗi ngẫu nhiên | Cơ chế retry + timeout |
| WhatsApp cập nhật giao diện | Tập trung toàn bộ selector vào `whatsapp_selectors.py` để dễ bảo trì |
| Gửi nhiều máy đồng thời | Worker thread riêng từng máy, adb theo serial |

## 11. Kiểm thử tự động

Chạy bộ test với pytest:

```bash
python -m pytest
```

Bao phủ: chuẩn hoá/import số điện thoại, settings (default + roundtrip), parse UI hierarchy & retry, selector WhatsApp, phát hiện đường dẫn adb và khớp `is_running_headless` chính xác.
