"""Widget hiển thị log - chỉ hiển thị; ghi file do logging module đảm nhiệm."""
import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

LEVEL_COLORS = {
    "info": "#0f766e",
    "success": "#15803d",
    "warning": "#b45309",
    "error": "#b91c1c",
    "debug": "#6b7280",
}


class LogPanel(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

    def append_log(self, message: str, level: str = "info") -> None:
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        color = LEVEL_COLORS.get(level, "#0f766e")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        line = f"[{stamp}] {message}"
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.textCursor().insertText(line + "\n", fmt)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def clear_log(self) -> None:
        self.clear()
