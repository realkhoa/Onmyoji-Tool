import time
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCursor

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("log_widget")
        self.setReadOnly(True)
        self.setMaximumHeight(140)

    def append_log(self, msg: str, color: str = "#b3b3b3"):
        ts = time.strftime("%H:%M:%S")
        self.append(f'<span style="color:#6a6a6a">[{ts}]</span> <span style="color:{color}">{msg}</span>')
        self.moveCursor(QTextCursor.MoveOperation.End)

    def append_ok(self, msg): self.append_log(msg, "#1db954")
    def append_err(self, msg): self.append_log(msg, "#e22134")
    def append_info(self, msg): self.append_log(msg, "#4da6ff")
