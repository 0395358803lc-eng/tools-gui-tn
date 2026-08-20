# Broadcast Reports

Mỗi batch tạo `BroadcastReport` có cấu trúc và mặc định xuất hai định dạng:

```text
%LOCALAPPDATA%\ToolsGuiTinWhatsApp\reports\
├── broadcast_<avd>_<timestamp>.csv
└── broadcast_<avd>_<timestamp>.xlsx
```

Có thể đổi root runtime bằng `TOOLS_GUI_TN_DATA_DIR`.

## Nội dung report

Mỗi recipient có các trường chính:

- timestamp;
- AVD / serial;
- số điện thoại;
- status: `success`, `failed`, `partial`, `cancelled`;
- số lần attempt;
- thời gian thực thi;
- error code / error message.

Report cũng giữ trạng thái preflight và summary của batch.

## Quyền riêng tư

Có chủ đích phân biệt giữa **diagnostic log** và **operational report**:

- log/UI diagnostics che phần lớn số điện thoại, ví dụ `849******21`;
- CSV/XLSX report giữ **số điện thoại đầy đủ** để có thể đối soát recipient thành công/thất bại.

Vì vậy report phải được xem là dữ liệu nhạy cảm của người vận hành:

- không commit report vào Git;
- không đưa vào build artifact;
- không gửi report ra ngoài nếu chưa có nhu cầu/quyền phù hợp;
- xóa hoặc archive theo chính sách dữ liệu của môi trường triển khai.

## Spreadsheet safety

Exporter neutralize cell có khả năng bị Excel/CSV viewer hiểu thành formula, kể cả khi `=`, `+`, `-`, `@` đứng sau whitespace/tab ở đầu cell.

Ví dụ:

```text
=SUM(1,1)
\t=SUM(1,1)
  @cmd
```

đều được prefix apostrophe trước khi ghi file.

## Preflight failure

Nếu batch dừng ngay ở preflight và chưa attempt recipient nào, report vẫn được tạo với:

- `preflight_ok=false`;
- danh sách lỗi preflight;
- một record export mô tả `PREFLIGHT_FAILED` để file không bị rỗng hoàn toàn.

## Export failure

Lỗi ghi CSV/XLSX không được phép biến một batch đã gửi thành thất bại. Worker chỉ ghi warning khi export lỗi và giữ nguyên kết quả recipient đã ghi nhận.
