# Emulator / WhatsApp Compatibility Baseline

Tài liệu này tách **baseline đã được ghi nhận trong khảo sát ban đầu** khỏi **những thứ cần tái xác minh sau mỗi thay đổi môi trường**.

## Baseline lịch sử

Theo khảo sát dự án ngày 06/08/2026:

| Thành phần | Baseline được ghi nhận |
|---|---|
| Hệ điều hành host | Windows |
| Android SDK | `%LOCALAPPDATA%\Android\Sdk` |
| Emulator mode | Hỗ trợ `-no-window -no-audio -no-boot-anim` |
| Android image | Android 16, Google APIs, x86_64 |
| AVD | `test_whatsap_-1`, `whatsapp_device_01` → `whatsapp_device_04` |
| AVD đã dùng để xác minh quy trình | `whatsapp_device_01` |
| Serial được ghi nhận trong khảo sát | `emulator-5558` |
| Automation | ADB + `uiautomator dump` |

Các giá trị trên là **dữ liệu khảo sát lịch sử**, không phải cam kết rằng mọi AVD/WhatsApp hiện tại vẫn tương thích mà không cần retest.

## Selector baseline

Các selector từng được xác minh trong môi trường dự án:

| Màn hình | Thành phần | Baseline selector |
|---|---|---|
| EULA | Agree/Continue | `com.whatsapp:id/eula_accept` |
| Home | New chat FAB | `com.whatsapp:id/fab` / `content-desc="New chat"` |
| Contact Picker | New contact | text `New contact` |
| Contact Form | Phone | EditText hint/content-desc/text `Phone` |
| Contact Form | Save | `com.whatsapp:id/keyboard_aware_save_button` / text `SAVE` |
| Conversation | Message field | EditText hint/content-desc/text `Message` |
| Conversation | Send | content-desc/text `Send` |
| Conversation | Attach | content-desc/text `Attach` |
| Media sheet | Gallery | content-desc/text `Gallery` |
| Media preview | Send media | content-desc bắt đầu bằng `Send` |

Implementation hiện ưu tiên:

```text
resource-id → content-desc / hint → text → heuristic
```

Không còn fallback tọa độ cố định cho ô Phone.

## Checklist khi thay WhatsApp/Android image

Trước khi chạy batch thực tế trên phiên bản mới:

1. `adb devices` trả thiết bị ở trạng thái `device`.
2. `adb shell getprop sys.boot_completed` trả `1`.
3. WhatsApp package mở được.
4. `uiautomator dump /dev/tty` trả hierarchy hợp lệ.
5. Home/New Chat selector match.
6. Contact Picker/New Contact selector match.
7. Contact Form/Phone + Save selector match.
8. Conversation/Message + Send selector match.
9. Attach/Gallery/media preview selector match nếu dùng ảnh.
10. Test nhập Unicode/ADBKeyboard nếu message có tiếng Việt.
11. Chạy một recipient test trước batch lớn.
12. Kiểm tra log không có circuit breaker/slow-dump warning bất thường.

## Headless mode

Batch automation nên chạy AVD với các flag nền:

```text
-no-window
-no-audio
-no-boot-anim
-no-snapshot
-gpu swiftshader_indirect
-no-metrics
```

Code vẫn có thể phát hiện AVD chạy có màn hình và cảnh báo, nhưng môi trường chuẩn của dự án là headless.

## Media compatibility

Không giả định media picker hỗ trợ cùng một multi-select workflow trên mọi Android/WhatsApp version. Implementation hiện gửi nhiều ảnh tuần tự để tránh báo thành công sai khi selector chỉ xác minh được một thumbnail.

Nếu muốn chuyển sang album/multi-select thật sự, phải thu UI hierarchy fixture trên phiên bản mục tiêu và thêm regression tests trước khi thay đổi workflow.

## Khi nào cập nhật tài liệu này

Cập nhật matrix khi có thay đổi một trong các yếu tố:

- Android API/image.
- Resolution/DPI của AVD.
- WhatsApp version/layout.
- Android Contacts app.
- Media picker implementation.
- ADBKeyboard version/input method.
- Headless emulator flags/GPU backend.

Mỗi baseline mới nên ghi ngày, AVD profile và kết quả test thay vì ghi chung là “đã chạy”.
