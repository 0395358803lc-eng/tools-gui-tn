"""Xử lý dữ liệu số điện thoại: chuẩn hoá, dọn dữ liệu, import Excel/CSV."""
from pathlib import Path
from typing import Optional

import pandas as pd

from .exceptions import DataError

PHONE_MIN_DIGITS = 7
PHONE_MAX_DIGITS = 15
PHONE_LIKE_RATIO = 0.5


def normalize_phone(value) -> str:
    """Chỉ giữ ký tự số, bỏ khoảng trắng / dấu `+` / `-` / dấu ngoặc."""
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def is_phone_like(value) -> bool:
    digits = normalize_phone(value)
    return PHONE_MIN_DIGITS <= len(digits) <= PHONE_MAX_DIGITS


def clean_phone_text(text: str) -> list[str]:
    """Tách từng dòng, dọn chỉ giữ số, bỏ dòng rỗng."""
    result = []
    for line in (text or "").splitlines():
        digits = normalize_phone(line)
        if digits:
            result.append(digits)
    return result


def import_phones_from_file(path: str | Path) -> list[str]:
    """Đọc sheet đầu tiên của file Excel/CSV, tự nhận diện cột chứa số điện thoại."""
    path = Path(path)
    if not path.exists():
        raise DataError(f"File không tồn tại: {path}")
    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path, dtype=str, header=None)
        else:
            df = pd.read_excel(path, dtype=str, header=None)
    except Exception as e:  # noqa: BLE001
        raise DataError(f"Không đọc được file {path.name}: {e}") from e

    best_col = best_numeric_column(df)
    if best_col is None:
        raise DataError("Không tìm thấy cột chứa số điện thoại trong file.")

    numbers = [str(v).strip() for v in df[best_col].dropna() if is_phone_like(v)]
    if not numbers:
        raise DataError("Không có số điện thoại hợp lệ trong file.")
    return [normalize_phone(n) for n in numbers]


def best_numeric_column(df: pd.DataFrame) -> Optional[int]:
    """Chọn cột có tỷ lệ ô dạng số điện thoại cao nhất (>= PHONE_LIKE_RATIO)."""
    best_idx: Optional[int] = None
    best_ratio = 0.0
    for col in df.columns:
        values = [str(v) for v in df[col].dropna()]
        if not values:
            continue
        ratio = sum(1 for v in values if is_phone_like(v)) / len(values)
        if ratio > best_ratio:
            best_ratio, best_idx = ratio, col
    if best_idx is not None and best_ratio >= PHONE_LIKE_RATIO:
        return best_idx
    return None
