# BÁO CÁO KỸ THUẬT
## Tools GUI Tin WhatsApp

**Cập nhật:** 20/08/2026  
**Nhánh hardening:** `fix/harden-whatsapp-automation`  
**Nền tảng mục tiêu:** Windows + Android Studio Emulator + ADB + WhatsApp

---

## 1. Mục tiêu hệ thống

Ứng dụng desktop Windows hỗ trợ:

- quản lý Android Virtual Device (AVD);
- khởi động AVD headless;
- nhập/import danh sách số điện thoại;
- tự động hoá thao tác WhatsApp qua ADB + UI hierarchy;
- gửi text hoặc ảnh;
- chạy worker nền không block GUI;
- retry có kiểm soát, cancellation, progress và log theo thiết bị.

Dự án vẫn là UI automation phụ thuộc vào phiên bản WhatsApp/Android; không được xem selector hiện tại là API ổn định vĩnh viễn.

---

## 2. Kiến trúc hiện tại

```text
GUI (PySide6)
  │
  ├── DevicesTab
  └── BroadcastTab
          │
          ▼
  BroadcastWorker (QThread)
          │
          ▼
      WhatsAppBot
      ├── AppController
      ├── ContactManager
      └── Messenger
          │
          ├── whatsapp_state
          ├── whatsapp_selectors
          ├── uiautomator
          └── adb
                  │
                  ▼
          Android Emulator / WhatsApp
```

Các module hỗ trợ:

- `data_manager.py`: chuẩn hoá/import dữ liệu.
- `settings.py`: config runtime + migration.
- `paths.py`: install/user-data paths.
- `logging_setup.py`: rotating logs + masking.
- `exceptions.py`: error taxonomy.

---

## 3. Thay đổi hardening chính

### 3.1 Repository hygiene

Đã loại khỏi Git tracking:

- `build/`;
- `dist/`;
- `logs/`;
- `__pycache__/`;
- `config/settings.json`.

`.gitignore` giữ các artifact/runtime file ngoài repository.

### 3.2 Packaging an toàn hơn

PyInstaller chỉ bundle:

```text
config/default_settings.json
```

Không bundle `settings.json` người dùng.

UPX tắt mặc định để giảm khác biệt build giữa các máy.

### 3.3 ADB command execution

`adb.py` có `CommandResult` để phân biệt:

- thành công;
- executable không tồn tại;
- timeout;
- non-zero exit code;
- stdout/stderr.

Các thao tác quan trọng có thể dùng `check=True` để raise `ADBError` thay vì biến mọi lỗi thành output rỗng.

### 3.4 Text input

Dữ liệu người dùng được truyền bằng argument riêng qua `shell_args()` thay vì tự ghép shell string.

Không còn logic tự:

- đổi space thành `%s` ở tầng WhatsApp;
- escape riêng `&` / `|`;
- xóa dấu `'`.

ADBKeyboard vẫn là đường ưu tiên cho Unicode nếu được cài trên AVD.

### 3.5 Multi-image correctness

Workflow cũ push nhiều ảnh nhưng chỉ chọn thumbnail đầu tiên rồi log như đã gửi đủ N ảnh.

Workflow hiện tại gửi **tuần tự từng ảnh**:

```text
push → media scan → Attach → Gallery → thumbnail → Send
```

Caption chỉ gắn vào ảnh đầu tiên.

Nếu đã gửi một phần ảnh rồi gặp lỗi, `PartialSendError` ngăn worker retry toàn recipient để tránh gửi trùng nội dung đã thành công.

### 3.6 Selector hardening

Selector ưu tiên:

```text
resource-id → content-desc/hint → text → heuristic
```

Fallback tọa độ Phone cố định đã bị loại bỏ. Nếu không tìm thấy field bằng selector an toàn, workflow fail rõ ràng.

### 3.7 State-aware navigation

`whatsapp_state.py` nhận diện trạng thái từ top activity:

- HOME;
- CONTACT_PICKER;
- CONTACT_FORM;
- CONVERSATION;
- OTHER_WHATSAPP;
- UNKNOWN.

Tích hợp hiện tại mang tính bảo thủ:

- đang ở HOME → bỏ qua restart WhatsApp;
- đang ở ContactPicker → bỏ qua bấm New Chat;
- trạng thái khác → giữ đường xử lý cũ.

### 3.8 Retry / circuit breaker / pacing

Worker có:

- retry count;
- retry backoff tăng theo attempt;
- circuit breaker sau nhiều recipient lỗi liên tiếp;
- success reset failure streak;
- minimum interval 1 giây giữa recipient;
- blank phone bị loại khỏi total thực tế.

### 3.9 Cancellation

Nút Dừng không chỉ set flag ở vòng ngoài.

Callback cancellation được truyền qua:

```text
BroadcastWorker
→ WhatsAppBot/controllers
→ ui.wait_for / ui_dump
→ adb.wait_for_activity
```

Do đó worker có thể dừng tại checkpoint gần nhất thay vì buộc chờ hết mọi timeout UI.

### 3.10 Diagnostic privacy

Số điện thoại trong worker/ContactManager log được mask, ví dụ:

```text
849******21
```

Message body không được ghi nguyên văn vào diagnostic log của worker.

---

## 4. Runtime data path

Runtime data không còn ghi cạnh source/EXE.

Windows mặc định:

```text
%LOCALAPPDATA%\ToolsGuiTinWhatsApp\
├── config\
│   ├── default_settings.json
│   └── settings.json
└── logs\
    └── <avd>.log
```

Có thể override:

```text
TOOLS_GUI_TN_DATA_DIR
```

### Migration

Nếu runtime settings mới chưa tồn tại nhưng có legacy `config/settings.json` cạnh source/EXE:

- JSON hợp lệ được copy sang user-data;
- bản legacy không bị xóa;
- settings mới hiện hữu không bị ghi đè;
- legacy JSON lỗi → fallback defaults.

---

## 5. Dependency management

Nguồn chuẩn là `pyproject.toml`.

### Runtime

- PySide6
- openpyxl
- pandas

### Dev

- pytest
- Ruff

### Build

- PyInstaller

`requirements.txt` chỉ còn compatibility entry point trỏ về package hiện tại.

---

## 6. Test suite

Test hiện bao phủ các nhóm quan trọng:

- ADB path + command result/error;
- AVD parsing/headless detection;
- data cleaning/import;
- settings + migration;
- user-data path resolution;
- UI hierarchy parsing;
- cancellation-aware UI waits;
- selector priority/fallback;
- WhatsApp state detection;
- orchestration text/media;
- Unicode/special-character text input;
- sequential multi-image;
- partial-send duplicate prevention;
- worker retry/backoff;
- circuit breaker;
- worker cancellation;
- minimum pacing;
- phone masking.

---

## 7. CI / Build verification

Workflow `.github/workflows/tests.yml` được cấu hình trên Windows để chạy:

```text
Ruff
→ pytest
→ python -m app --self-test
→ PyInstaller build
→ packaged EXE --self-test
```

Lưu ý: việc workflow được cấu hình không đồng nghĩa mọi run tương lai luôn pass. Kết quả Actions của commit/PR phải được kiểm tra trước khi merge/release.

---

## 8. Baseline tương thích

Khảo sát lịch sử ngày 06/08/2026 ghi nhận:

- Windows host;
- Android SDK tại user LocalAppData;
- Android 16 Google APIs x86_64;
- các AVD `test_whatsap_-1`, `whatsapp_device_01` → `04`;
- workflow từng được xác minh trên `whatsapp_device_01`.

Đây là baseline lịch sử, không phải chứng nhận compatibility hiện tại sau mỗi WhatsApp update.

Chi tiết xem:

```text
docs/COMPATIBILITY.md
```

---

## 9. Rủi ro còn lại

### 9.1 WhatsApp UI thay đổi

Resource-id/content-desc/text có thể thay đổi sau update.

Giải pháp:

- giữ selector tập trung;
- fixture/regression test;
- retest một recipient trước batch lớn;
- không quay lại coordinate fallback nếu chưa có device profile được xác minh.

### 9.2 Media picker khác nhau giữa Android image

Workflow hiện dùng sequential image send vì đó là hành vi có thể kiểm soát tốt hơn với selector đã xác minh.

Album/multi-select thật sự chỉ nên triển khai sau khi có UI fixture trên môi trường mục tiêu.

### 9.3 ADB shell Unicode

ADBKeyboard là đường ưu tiên. Fallback `input text` có thể khác nhau giữa Android image/IME.

### 9.4 Automation throughput

Quy trình vẫn tạo/tìm contact và navigation UI tương đối nhiều. Tối ưu session/contact cache thuộc giai đoạn P3 sau khi reliability layer ổn định.

---

## 10. Trạng thái roadmap

### P0 — Correctness / safety

Đã triển khai chính:

- repository cleanup;
- safe config bundling;
- explicit ADB errors;
- safe text input;
- multi-image correctness;
- explicit settings initialization;
- partial-send duplicate prevention.

### P1 — Reliability

Đã triển khai chính:

- selector priority;
- loại fixed coordinate;
- state detection/navigation guard;
- retry backoff;
- circuit breaker;
- cancellation propagation;
- minimum pacing;
- worker/bot/media tests;
- CI + Ruff;
- diagnostic masking.

### P2 — Maintainability / packaging

Đã triển khai phần lớn:

- user-data paths;
- migration legacy settings;
- dependency consolidation;
- PyInstaller hardening;
- README;
- compatibility documentation;
- cập nhật báo cáo này.

### P3 — Optimization

Chưa hoàn tất, gồm các hướng chính:

- contact resolution strategy;
- contact cache per device;
- reuse WhatsApp session giữa recipient;
- device/broadcast preflight;
- structured result model;
- CSV/XLSX result export;
- integration tests với emulator thật.

---

## 11. Kết luận kỹ thuật

Kiến trúc nền ban đầu được giữ lại vì separation giữa GUI / worker / WhatsApp controllers / selector / ADB là hợp lý.

Hardening tập trung vào correctness, observability và fail-safe behavior thay vì viết lại toàn bộ ứng dụng.

Sau P0–P2, dự án có nền tảng tốt hơn rõ rệt để bước sang P3. Tuy nhiên trước khi release cho batch thực tế vẫn cần:

1. CI run xanh trên commit/PR mục tiêu.
2. Build EXE thành công trên Windows.
3. Smoke test trên AVD thật.
4. Retest selector với WhatsApp version đang sử dụng.
5. Test một recipient text và một recipient media trước batch lớn.
