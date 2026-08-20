"""Phân tích UI hierarchy từ uiautomator - Node/UiDump và các hàm chờ tìm selector."""
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import adb

SLOW_DUMP_SECONDS = 2.5
_PERF_LOGGER = logging.getLogger("wa.perf")
if not _PERF_LOGGER.handlers:
    _PERF_LOGGER.setLevel(logging.WARNING)
    try:
        _PERF_LOGGER.addHandler(logging.StreamHandler())
    except ValueError:  # stderr có thể không có trong GUI mode
        pass


@dataclass
class Node:
    text: str = ""
    content_desc: str = ""
    resource_id: str = ""
    package: str = ""
    cls: str = ""
    hint: str = ""
    clickable: bool = False
    enabled: bool = True
    bounds: tuple = (0, 0, 0, 0)

    @property
    def center(self) -> tuple[int, int]:
        x = (self.bounds[0] + self.bounds[2]) // 2
        y = (self.bounds[1] + self.bounds[3]) // 2
        return x, y


@dataclass
class UiDump:
    serial: str
    xml: str
    nodes: list[Node] = field(default_factory=list)

    def _parsed(self) -> bool:
        return bool(self.nodes)

    def find(self, *, text: str = None, desc: str = None, rid: str = None,
             cls: str = None, hint: str = None) -> Optional[Node]:
        for n in self.nodes:
            if text is not None and n.text != text:
                continue
            if desc is not None and n.content_desc != desc:
                continue
            if rid is not None and n.resource_id != rid:
                continue
            if cls is not None and n.cls != cls:
                continue
            if hint is not None and n.hint != hint:
                continue
            return n
        return None

    def find_all(self, *, text: str = None, desc: str = None, rid: str = None,
                 cls: str = None, hint: str = None) -> list[Node]:
        out = []
        for n in self.nodes:
            if text is not None and n.text != text:
                continue
            if desc is not None and n.content_desc != desc:
                continue
            if rid is not None and n.resource_id != rid:
                continue
            if cls is not None and n.cls != cls:
                continue
            if hint is not None and n.hint != hint:
                continue
            out.append(n)
        return out

    def find_regex(self, pattern: str, attr: str = "text") -> Optional[Node]:
        rx = re.compile(pattern)
        for n in self.nodes:
            if rx.search(getattr(n, attr)):
                return n
        return None


def _parse_bounds(s: str) -> tuple:
    m = re.search(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", s or "")
    if not m:
        return (0, 0, 0, 0)
    return tuple(int(v) for v in m.groups())


def _walk(parent: ET.Element, nodes: list[Node]) -> None:
    for child in parent:
        n = Node(
            text=child.get("text") or "",
            content_desc=child.get("content-desc") or "",
            resource_id=child.get("resource-id") or "",
            package=child.get("package") or "",
            cls=child.get("class") or "",
            hint=child.get("hint") or "",
            clickable=child.get("clickable") == "true",
            enabled=child.get("enabled") != "false",
            bounds=_parse_bounds(child.get("bounds")),
        )
        nodes.append(n)
        _walk(child, nodes)


def ui_dump(serial: str, retries: int = 3, delay: float = 1.0,
            cancelled: Optional[Callable[[], bool]] = None) -> Optional[UiDump]:
    """Lấy UI hierarchy. Retry vì uiautomator dump thỉnh thoảng lỗi.

    `cancelled` cho phép worker ngừng giữa các lần dump/retry thay vì đợi hết chu kỳ.
    """
    t0 = time.monotonic()
    for attempt in range(retries):
        if cancelled is not None and cancelled():
            return None
        xml = adb.exec_out(serial, "uiautomator dump /dev/tty", timeout=25)
        if xml and "<hierarchy" in xml:
            end = xml.find("</hierarchy>")
            if end != -1:
                xml = xml[: end + len("</hierarchy>")]
            try:
                root = ET.fromstring(xml)
                nodes: list[Node] = []
                _walk(root, nodes)
                _log_dump_duration(serial, time.monotonic() - t0, len(nodes))
                return UiDump(serial=serial, xml=xml, nodes=nodes)
            except ET.ParseError:
                pass
        if attempt < retries - 1:
            if cancelled is not None and cancelled():
                return None
            time.sleep(delay)
    _log_dump_duration(serial, time.monotonic() - t0, 0)
    return None


def _log_dump_duration(serial: str, elapsed: float, n_nodes: int) -> None:
    if elapsed >= SLOW_DUMP_SECONDS:
        _PERF_LOGGER.warning(
            f"ui_dump chậm {serial}: {elapsed:.1f}s ({n_nodes} nodes)")


# ---------------------------------------------------------------------------
# Chờ đợi có điều kiện
# ---------------------------------------------------------------------------

def wait_for(serial: str, predicate: Callable[[UiDump], Optional[Node]],
             timeout: float = 20.0, interval: float = 1.0,
             cancelled: Optional[Callable[[], bool]] = None) -> Optional[Node]:
    """Lặp ui_dump tới khi predicate match, timeout hoặc có yêu cầu hủy."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cancelled is not None and cancelled():
            return None
        dump = ui_dump(serial, cancelled=cancelled)
        if dump:
            node = predicate(dump)
            if node is not None:
                return node
        if cancelled is not None and cancelled():
            return None
        time.sleep(interval)
    return None


def wait_for_text(serial: str, text: str, timeout: float = 20.0,
                  cancelled: Optional[Callable[[], bool]] = None) -> Optional[Node]:
    return wait_for(
        serial,
        lambda d: d.find(text=text),
        timeout=timeout,
        cancelled=cancelled,
    )


def wait_for_rid(serial: str, rid: str, timeout: float = 20.0,
                 cancelled: Optional[Callable[[], bool]] = None) -> Optional[Node]:
    return wait_for(
        serial,
        lambda d: d.find(rid=rid),
        timeout=timeout,
        cancelled=cancelled,
    )
