"""Core-test fixtures tránh ghi runtime report ra user AppData."""
import pytest

from app.core import worker as wk


@pytest.fixture(autouse=True)
def disable_worker_report_export_side_effects(monkeypatch):
    monkeypatch.setattr(wk, "export_csv", lambda report: "test-report.csv")
    monkeypatch.setattr(wk, "export_xlsx", lambda report: "test-report.xlsx")
