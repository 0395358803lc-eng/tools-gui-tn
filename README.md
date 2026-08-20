# Tools GUI Tin WhatsApp

Ứng dụng desktop Windows viết bằng Python/PySide6 để điều khiển Android Emulator (AVD) qua ADB và tự động hoá thao tác WhatsApp bằng UI hierarchy (`uiautomator`).

> Dự án phụ thuộc vào giao diện ứng dụng WhatsApp trên Android. Sau mỗi lần cập nhật WhatsApp, cần chạy lại test/kiểm tra selector trên AVD trước khi dùng cho batch lớn.

## 1. Yêu cầu hệ thống

- Windows 10/11.
- Python 3.10 trở lên.
- Android Studio và Android SDK.
- `platform-tools/adb.exe` và Android Emulator.
- Ít nhất một Android Virtual Device (AVD) đã được tạo.
- WhatsApp đã được cài và thiết lập trên AVD.
- Khuyến nghị cài ADBKeyboard nếu cần nhập Unicode/tiếng Việt ổn định.

Ứng dụng tìm Android SDK theo thứ tự:

1. `ANDROID_HOME`.
2. `ANDROID_SDK_ROOT`.
3. Fallback Windows: `%USERPROFILE%\AppData\Local\Android\Sdk`.
4. Nếu không tìm thấy SDK theo các đường dẫn trên, ứng dụng thử dùng `adb` / `emulator` từ `PATH`.

## 2. Cài đặt môi trường Python

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,build]"
```

`pyproject.toml` là nguồn dependency chính:

- Runtime: PySide6, openpyxl, pandas.
- `dev`: pytest, Ruff.
- `build`: PyInstaller.

`requirements.txt` chỉ được giữ như compatibility entry point cho các script cũ và trỏ về package hiện tại.

## 3. Kiểm tra Android SDK / ADB

Trong PowerShell:

```powershell
adb version
adb devices
emulator -list-avds
```

Nếu `adb` không nằm trong `PATH`, có thể cấu hình:

```powershell
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
```

Đảm bảo AVD có thể boot hoàn chỉnh và `adb devices` hiển thị trạng thái `device` thay vì `offline`.

## 4. Chạy ứng dụng

Có thể chạy bằng một trong các cách:

```powershell
python -m app
```

hoặc:

```powershell
python main.py
```

Nếu package đã được cài editable:

```powershell
wa-tool
```

Self-test chỉ kiểm tra import các module chính và không khởi tạo GUI/config runtime:

```powershell
python -m app --self-test
```

## 5. Quy trình sử dụng

### Danh sách thiết bị

1. Mở tab quản lý thiết bị.
2. Làm mới danh sách AVD.
3. Khởi động AVD ở chế độ ẩn (`-no-window`) cho batch automation.
4. Chờ trạng thái boot hoàn tất.

### Gửi tin

1. Chọn AVD đang chạy.
2. Nhập danh sách số điện thoại hoặc import Excel/CSV.
3. Nhập nội dung tin nhắn.
4. Có thể thêm ảnh.
5. Cấu hình khoảng cách giữa recipient.
6. Bấm bắt đầu và theo dõi progress/log.
7. Nút Dừng truyền cancellation xuống các vòng chờ UI/activity để dừng ở checkpoint gần nhất.

Core luôn áp dụng khoảng nghỉ tối thiểu 1 giây giữa các recipient, kể cả khi config cũ lưu `interval=0`.

## 6. Gửi ảnh

Media picker hiện chỉ có selector đã được xác minh cho một thumbnail tại một thời điểm. Vì vậy nhiều ảnh được gửi **tuần tự từng ảnh**, thay vì giả định multi-select:

1. Push một ảnh lên `/sdcard/Pictures/`.
2. Trigger Media Scanner.
3. Mở Attach → Gallery.
4. Chọn ảnh mới nhất.
5. Gửi.
6. Lặp lại ảnh tiếp theo.

Caption chỉ được gắn vào ảnh đầu tiên để tránh lặp nội dung.

Nếu một số ảnh đã gửi thành công rồi ảnh tiếp theo lỗi, worker không retry toàn bộ recipient, nhằm tránh gửi trùng các ảnh đã thành công.

## 7. Dữ liệu runtime

Ứng dụng không còn ghi settings/log cạnh file EXE.

Trên Windows, dữ liệu runtime mặc định nằm tại:

```text
%LOCALAPPDATA%\ToolsGuiTinWhatsApp\
├── config\
│   ├── default_settings.json
│   └── settings.json
└── logs\
    └── <avd_name>.log
```

Có thể override thư mục dữ liệu bằng biến môi trường:

```powershell
$env:TOOLS_GUI_TN_DATA_DIR = "D:\ToolsGuiTinWhatsAppData"
```

### Migration settings cũ

Nếu chưa có `settings.json` ở user-data nhưng tồn tại `config/settings.json` cạnh source/EXE cũ, ứng dụng sẽ:

- đọc file cũ nếu JSON hợp lệ;
- copy dữ liệu sang user-data;
- **không xóa** file cũ;
- không ghi đè settings mới nếu settings mới đã tồn tại.

## 8. Log và dữ liệu nhạy cảm

Log theo từng AVD được rotate tự động. Số điện thoại trong diagnostics được che phần giữa, ví dụ:

```text
849******21
```

Nội dung tin nhắn không được ghi nguyên văn vào worker diagnostic log.

Không commit `settings.json`, log, build output hoặc cache Python lên Git.

## 9. Chạy test và static checks

```powershell
python -m ruff check app tests main.py
python -m pytest -q
python -m app --self-test
```

Các nhóm test hiện bao phủ:

- ADB command execution và lỗi timeout/not-found/non-zero exit.
- AVD parsing/headless detection.
- Data import và chuẩn hoá số.
- Settings + migration.
- UI hierarchy + cancellation-aware waits.
- WhatsApp selectors và state detection.
- Text input có ký tự đặc biệt/Unicode.
- Multi-image sequential sending.
- Partial-send duplicate protection.
- Worker retry/backoff/circuit breaker/cancellation/pacing.

## 10. Build EXE

```powershell
python -m pip install -e ".[build]"
python -m PyInstaller --clean --noconfirm ToolsGuiTinWhatsApp.spec
```

Output:

```text
dist\ToolsGuiTinWhatsApp.exe
```

Kiểm tra package:

```powershell
.\dist\ToolsGuiTinWhatsApp.exe --self-test
```

PyInstaller chỉ bundle `config/default_settings.json`; settings người dùng không được đóng gói vào EXE.

UPX bị tắt mặc định để build dễ tái lập hơn giữa các máy.

## 11. CI

Workflow `.github/workflows/tests.yml` chạy trên Windows và thực hiện:

1. Cài package với extras `dev,build`.
2. Ruff static checks.
3. Pytest.
4. Source self-test.
5. PyInstaller build.
6. Packaged EXE self-test.

## 12. Giới hạn automation

Automation vẫn phụ thuộc vào:

- WhatsApp resource-id / content-desc / hint / text.
- Android Contacts UI.
- Media picker của Android/WhatsApp.
- Tốc độ boot/render của emulator.
- Phiên bản Android và WhatsApp.

Selector được ưu tiên theo hướng ổn định hơn:

```text
resource-id → content-desc / hint → text → heuristic
```

Workflow không còn sử dụng tọa độ Phone cố định khi selector thất bại. Nếu không tìm được ô Phone bằng selector an toàn, thao tác dừng với lỗi rõ ràng thay vì tap vào một vị trí có thể sai.

## 13. Troubleshooting

### Không thấy AVD

Kiểm tra:

```powershell
emulator -list-avds
```

và `ANDROID_HOME` / `ANDROID_SDK_ROOT`.

### AVD hiển thị `offline`

Thử:

```powershell
adb kill-server
adb start-server
adb devices
```

Sau đó chờ emulator boot hoàn tất.

### Không tìm thấy selector WhatsApp

- Xác nhận WhatsApp chưa vừa cập nhật layout.
- Chạy lại test selector.
- Thu UI hierarchy bằng `uiautomator dump` trên AVD kiểm thử.
- Cập nhật `app/core/whatsapp_selectors.py` thay vì thêm tọa độ cố định.

### Không nhập được tiếng Việt/Unicode

Kiểm tra ADBKeyboard đã được cài/enable trên AVD. Fallback `adb shell input text` không đảm bảo hỗ trợ mọi Unicode giống nhau trên mọi Android image.

### Config không ghi được

Kiểm tra quyền ghi tại `%LOCALAPPDATA%\ToolsGuiTinWhatsApp` hoặc thư mục được chỉ định qua `TOOLS_GUI_TN_DATA_DIR`.

## 14. Cấu trúc chính

```text
app/
├── __main__.py
├── core/
│   ├── adb.py
│   ├── avd_manager.py
│   ├── data_manager.py
│   ├── exceptions.py
│   ├── logging_setup.py
│   ├── paths.py
│   ├── settings.py
│   ├── uiautomator.py
│   ├── whatsapp_bot.py
│   ├── whatsapp_selectors.py
│   ├── whatsapp_state.py
│   └── worker.py
└── ui/
    ├── broadcast_tab.py
    ├── devices_tab.py
    ├── log_panel.py
    └── main_window.py

tests/core/
```

Tài liệu kế hoạch/khảo sát kỹ thuật chi tiết hơn nằm trong `BAO_CAO.md`.
