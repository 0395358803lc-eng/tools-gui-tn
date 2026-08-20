"""Export BroadcastReport thành CSV/XLSX trong thư mục user-data reports."""
import csv
import re
from pathlib import Path

from openpyxl import Workbook

from . import paths
from .broadcast_result import BroadcastReport

_FORMULA_PREFIXES = ("=", "+", "-", "@")
_RECIPIENT_COLUMNS = [
    "report_started_at",
    "report_completed_at",
    "preflight_ok",
    "timestamp",
    "avd_name",
    "serial",
    "phone",
    "status",
    "attempts",
    "elapsed_seconds",
    "error_code",
    "error_message",
]


def _safe_cell(value):
    """Neutralize chuỗi có thể bị Excel/CSV viewer hiểu thành formula.

    Kiểm tra sau khi bỏ whitespace/control phổ biến ở đầu vì payload kiểu
    ``\t=SUM(...)`` hoặc ``  @cmd`` vẫn có thể bị spreadsheet xử lý đặc biệt.
    Apostrophe luôn được chèn ở ký tự đầu tiên của cell, giữ nguyên nội dung gốc.
    """
    if isinstance(value, str):
        probe = value.lstrip(" \t\r\n")
        if probe.startswith(_FORMULA_PREFIXES):
            return "'" + value
    return value


def _safe_avd_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "avd")).strip("._")
    return cleaned or "avd"


def default_report_path(report: BroadcastReport, extension: str) -> Path:
    extension = extension.lower().lstrip(".")
    if extension not in {"csv", "xlsx"}:
        raise ValueError(f"Định dạng report không hỗ trợ: {extension}")
    root = paths.reports_dir()
    root.mkdir(parents=True, exist_ok=True)
    stamp = report.started_at.replace(":", "-").replace("+", "_")
    return root / f"broadcast_{_safe_avd_name(report.avd_name)}_{stamp}.{extension}"


def _recipient_rows(report: BroadcastReport) -> list[dict]:
    rows = []
    for recipient in report.recipients:
        row = recipient.to_row()
        rows.append({
            "report_started_at": report.started_at,
            "report_completed_at": report.completed_at,
            "preflight_ok": report.preflight_ok,
            **row,
        })
    if not rows:
        rows.append({
            "report_started_at": report.started_at,
            "report_completed_at": report.completed_at,
            "preflight_ok": report.preflight_ok,
            "timestamp": "",
            "avd_name": report.avd_name,
            "serial": report.serial,
            "phone": "",
            "status": "",
            "attempts": 0,
            "elapsed_seconds": 0,
            "error_code": "PREFLIGHT_FAILED" if not report.preflight_ok else "",
            "error_message": "; ".join(report.preflight_errors),
        })
    return rows


def export_csv(report: BroadcastReport, path: str | Path | None = None) -> Path:
    target = Path(path) if path is not None else default_report_path(report, "csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_RECIPIENT_COLUMNS)
        writer.writeheader()
        for row in _recipient_rows(report):
            writer.writerow({key: _safe_cell(row.get(key, "")) for key in _RECIPIENT_COLUMNS})
    return target


def export_xlsx(report: BroadcastReport, path: str | Path | None = None) -> Path:
    target = Path(path) if path is not None else default_report_path(report, "xlsx")
    target.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    summary.append(["field", "value"])
    for key, value in report.summary_row().items():
        summary.append([key, _safe_cell(value)])
    summary.append(["preflight_errors", _safe_cell("; ".join(report.preflight_errors))])

    recipients = wb.create_sheet("Recipients")
    recipients.append(_RECIPIENT_COLUMNS)
    for row in _recipient_rows(report):
        recipients.append([_safe_cell(row.get(key, "")) for key in _RECIPIENT_COLUMNS])

    wb.save(target)
    return target
