"""Structured result model cho từng recipient và toàn batch."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RecipientStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


@dataclass
class RecipientResult:
    avd_name: str
    serial: str
    phone: str
    status: RecipientStatus
    attempts: int
    elapsed_seconds: float
    error_code: str = ""
    error_message: str = ""
    timestamp: str = field(default_factory=utc_now_iso)

    def to_row(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "avd_name": self.avd_name,
            "serial": self.serial,
            "phone": self.phone,
            "status": self.status.value,
            "attempts": self.attempts,
            "elapsed_seconds": round(float(self.elapsed_seconds), 3),
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass
class BroadcastReport:
    avd_name: str
    serial: str
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str = ""
    preflight_ok: bool = True
    preflight_errors: list[str] = field(default_factory=list)
    recipients: list[RecipientResult] = field(default_factory=list)

    def add(self, result: RecipientResult) -> None:
        self.recipients.append(result)

    def finish(self) -> None:
        self.completed_at = utc_now_iso()

    @property
    def success_count(self) -> int:
        return sum(r.status is RecipientStatus.SUCCESS for r in self.recipients)

    @property
    def failed_count(self) -> int:
        return sum(r.status is RecipientStatus.FAILED for r in self.recipients)

    @property
    def partial_count(self) -> int:
        return sum(r.status is RecipientStatus.PARTIAL for r in self.recipients)

    @property
    def cancelled_count(self) -> int:
        return sum(r.status is RecipientStatus.CANCELLED for r in self.recipients)

    @property
    def attempted_count(self) -> int:
        return len(self.recipients)

    def summary_row(self) -> dict:
        return {
            "avd_name": self.avd_name,
            "serial": self.serial,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "preflight_ok": self.preflight_ok,
            "attempted": self.attempted_count,
            "success": self.success_count,
            "failed": self.failed_count,
            "partial": self.partial_count,
            "cancelled": self.cancelled_count,
        }
