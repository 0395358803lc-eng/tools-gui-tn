"""Test xử lý dữ liệu số điện thoại."""
import pandas as pd
import pytest

from app.core import data_manager as dm
from app.core.exceptions import DataError


def test_normalize_phone():
    assert dm.normalize_phone("+1 202-555-0134") == "12025550134"
    assert dm.normalize_phone("(84) 987.654.321") == "84987654321"
    assert dm.normalize_phone(None) == ""
    assert dm.normalize_phone(12052452095) == "12052452095"


def test_is_phone_like():
    assert dm.is_phone_like("12052452095")
    assert dm.is_phone_like("+84987654321")
    assert not dm.is_phone_like("123")
    assert not dm.is_phone_like("abc")
    assert not dm.is_phone_like("1234567890123456")  # > 15 chữ số


def test_clean_phone_text():
    text = "+1 202 555 0134\n 84987654321 \n\nabc\n12052452095"
    assert dm.clean_phone_text(text) == ["12025550134", "84987654321", "12052452095"]


def test_best_numeric_column():
    df = pd.DataFrame({"name": ["a", "b", "c"], "phone": ["12052452095", "84987654321", "12052452096"]})
    assert dm.best_numeric_column(df) == "phone"


def test_best_numeric_column_no_phone():
    df = pd.DataFrame({"a": ["1", "2", "3"], "b": ["x", "y", "z"]})
    assert dm.best_numeric_column(df) is None


def test_import_csv(tmp_path):
    csv_file = tmp_path / "phones.csv"
    csv_file.write_text("name,phone\nA,12052452095\nB,84987654321\n", encoding="utf-8")
    numbers = dm.import_phones_from_file(csv_file)
    assert numbers == ["12052452095", "84987654321"]


def test_import_missing_file(tmp_path):
    with pytest.raises(DataError):
        dm.import_phones_from_file(tmp_path / "khong_co.xlsx")


def test_import_file_without_phone(tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("a,b\nx,y\n", encoding="utf-8")
    with pytest.raises(DataError):
        dm.import_phones_from_file(csv_file)
