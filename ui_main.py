import sys
import os
import re
import time
import threading
from collections import OrderedDict
from pathlib import Path

import cv2
import numpy as np
import win32gui
import win32process
import psutil

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTabWidget,
    QTextEdit, QGroupBox, QSplitter, QStatusBar, QMessageBox,
    QPlainTextEdit, QCheckBox, QSpinBox, QFileDialog, QListWidget,
    QListWidgetItem, QFrame, QSizePolicy, QCompleter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QMutex, QMutexLocker, QRect, QSize
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QTextCursor, QPainter, QTextFormat

from screenshot import WindowCapture
from dsl_engine import DSLEngine


# ---------------------------------------------------------------------------
#  Line Number Editor
# ---------------------------------------------------------------------------
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint(event)


DSL_KEYWORDS = [
    "click", "rclick", "dclick", "move", "drag", "drag_to", "drag_image", "drag_offset",
    "key", "type", "wait", "wait_random", "scroll", "log", "find_and_click",
    "wait_for", "wait_and_click", "exists", "exists_exact", "find_and_click_largest_shiki",
    "loop", "end", "forever", "if", "elif", "else", "not", "and", "or",
    "set", "resize", "do", "until", "goto", "count"
]

def get_image_files() -> list[str]:
    """Lấy danh sách các file .png trong thư mục images."""
    img_dir = Path("images")
    if not img_dir.exists():
        return []
    return [f"'{p.name}'" for p in img_dir.glob("*.png")]

class LineNumberEditor(QPlainTextEdit):
    """QPlainTextEdit với line numbers bên trái và tính năng auto-complete."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self._update_line_area_width()

        # Nạp cả keywords DSL và tên file ảnh vào completer
        keywords = DSL_KEYWORDS + get_image_files()
        
        from PyQt5.QtCore import QStringListModel
        self.completer = QCompleter(keywords, self)
        self.completer.setModel(QStringListModel(keywords, self.completer))
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

    def refresh_completer_model(self):
        """Cập nhật lại danh sách file ảnh mởi do user có thể vừa thêm."""
        from PyQt5.QtCore import QStringListModel
        keywords = DSL_KEYWORDS + get_image_files()
        self.completer.setModel(QStringListModel(keywords, self.completer))

    def insert_completion(self, completion):
        tc = self.textCursor()
        prefix = self.completer.completionPrefix()
        
        # Nếu đang gõ name string, xóa prefix hiện tại và điền nốt
        extra = (len(completion) - len(prefix))
        
        tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
        tc.insertText(completion)
        self.setTextCursor(tc)

    def text_under_cursor(self) -> str:
        tc = self.textCursor()
        # Tìm lại từ (gồm cả dấu ' nếu đang gõ chuỗi)
        block_text = tc.block().text()
        pos = tc.positionInBlock()
        
        start = pos
        while start > 0 and (block_text[start - 1].isalnum() or block_text[start - 1] in "_'"):
            start -= 1
        
        return block_text[start:pos]

    def focusInEvent(self, e):
        if self.completer:
            self.completer.setWidget(self)
            self.refresh_completer_model()
        super().focusInEvent(e)

    def keyPressEvent(self, e):
        if self.completer and self.completer.popup() and self.completer.popup().isVisible():
            if e.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                e.ignore()
                return

        is_shortcut = (e.modifiers() & Qt.ControlModifier) and e.key() == Qt.Key_Space
        if not self.completer or not is_shortcut:
            super().keyPressEvent(e)

        ctrl_or_shift = e.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
        if not self.completer or (ctrl_or_shift and e.text() == ""):
            return

        has_modifier = e.modifiers() != Qt.NoModifier and not ctrl_or_shift
        completion_prefix = self.text_under_cursor()

        if not is_shortcut and (has_modifier or e.text() == "" or len(completion_prefix) < 1):
            self.completer.popup().hide()
            return

        if completion_prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completion_prefix)
            self.completer.popup().setCurrentIndex(
                self.completer.completionModel().index(0, 0)
            )

        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0)
                    + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_area_width(self, _=0):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(),
                                          self.line_number_area_width(), cr.height()))

    def line_number_area_paint(self, event):
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor(35, 35, 54))
        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        painter.setFont(self.font())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(100, 100, 140))
                painter.drawText(0, top, self._line_area.width() - 4,
                                 self.fontMetrics().height(),
                                 Qt.AlignRight, str(block_num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_num += 1
        painter.end()


# ---------------------------------------------------------------------------
#  Worker thread: liên tục capture window và emit frame
# ---------------------------------------------------------------------------
class CaptureWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._capture: WindowCapture | None = None
        self._mutex = QMutex()
        self._fps = 30

    def set_capture(self, capture: WindowCapture):
        with QMutexLocker(self._mutex):
            self._capture = capture

    def set_fps(self, fps: int):
        self._fps = max(1, min(fps, 60))

    def run(self):
        self._running = True
        while self._running:
            with QMutexLocker(self._mutex):
                cap = self._capture
            if cap is not None:
                try:
                    frame = cap.capture()
                    if frame is not None:
                        self.frame_ready.emit(frame)
                except Exception:
                    pass
            delay = 1.0 / self._fps
            self.msleep(int(delay * 1000))

    def stop(self):
        self._running = False
        self.wait()


# ---------------------------------------------------------------------------
#  Utility: list visible windows
# ---------------------------------------------------------------------------
def list_windows() -> list[dict]:
    """Return list of {'hwnd': int, 'title': str, 'pid': int, 'process': str}"""
    results = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            name = proc.name()
        except Exception:
            name = ""
            pid = 0
        results.append({"hwnd": hwnd, "title": title, "pid": pid, "process": name})

    win32gui.EnumWindows(_cb, None)
    results.sort(key=lambda x: x["title"].lower())
    return results


# ---------------------------------------------------------------------------
#  Preview label (scale-to-fit)
# ---------------------------------------------------------------------------
class PreviewLabel(QLabel):
    coord_changed = pyqtSignal(int, int)  # tọa độ game (x, y)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #1e1e2e; border: 1px solid #444;")
        self.setMouseTracking(True)
        self._pixmap: QPixmap | None = None
        self._frame_w: int = 0  # kích thước frame gốc
        self._frame_h: int = 0
        self._coord_label = QLabel(self)
        self._coord_label.setStyleSheet(
            "background-color: rgba(0,0,0,180); color: #00ff88; "
            "padding: 2px 6px; font: bold 11px 'Consolas'; border-radius: 3px;"
        )
        self._coord_label.hide()

    def update_frame(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        self._frame_w = w
        self._frame_h = h
        bytes_per_line = 3 * w
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._rescale()

    def _rescale(self):
        if self._pixmap:
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(scaled)

    def _map_to_game_coords(self, pos) -> tuple[int, int] | None:
        """Chuyển tọa độ widget -> tọa độ game gốc."""
        if not self._pixmap or self._frame_w == 0 or self._frame_h == 0:
            return None
        pm = self.pixmap()
        if pm is None:
            return None
        # Tính offset (pixmap được căn giữa trong label)
        off_x = (self.width() - pm.width()) / 2
        off_y = (self.height() - pm.height()) / 2
        rel_x = pos.x() - off_x
        rel_y = pos.y() - off_y
        if rel_x < 0 or rel_y < 0 or rel_x >= pm.width() or rel_y >= pm.height():
            return None
        game_x = int(rel_x / pm.width() * self._frame_w)
        game_y = int(rel_y / pm.height() * self._frame_h)
        return (game_x, game_y)

    def mouseMoveEvent(self, event):
        coords = self._map_to_game_coords(event.pos())
        if coords:
            gx, gy = coords
            self._coord_label.setText(f"X: {gx}  Y: {gy}")
            self._coord_label.adjustSize()
            # Hiển thị gần con trỏ, nhưng không vượt ra ngoài widget
            lx = min(event.x() + 12, self.width() - self._coord_label.width() - 4)
            ly = max(event.y() - 24, 4)
            self._coord_label.move(lx, ly)
            self._coord_label.show()
            self.coord_changed.emit(gx, gy)
        else:
            self._coord_label.hide()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._coord_label.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


# ---------------------------------------------------------------------------
#  Base class for feature tabs
# ---------------------------------------------------------------------------
class FeatureTab(QWidget):
    """Mỗi tab kế thừa class này."""
    log_message = pyqtSignal(str)
    status_message = pyqtSignal(str)

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.feature_name = name
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


# ---------------------------------------------------------------------------
#  Tab 1: Auto Farm (ví dụ)
# ---------------------------------------------------------------------------
class AutoFarmTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__("Auto Farm", parent)
        layout = QVBoxLayout(self)

        desc = QLabel("Tự động farm quái / ải. Viết script DSL ở ô bên dưới hoặc dùng preset.")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Script editor
        self.script_edit = LineNumberEditor()
        self.script_edit.setPlaceholderText(
            "# Ví dụ DSL script:\n"
            "click 500 300\n"
            "wait 1.5\n"
            "find_and_click 'start_btn.png'\n"
            "loop 10\n"
            "  click 500 300\n"
            "  wait 2\n"
            "end"
        )
        self.script_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.script_edit, 1)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_load = QPushButton("Load Script")
        self.btn_save = QPushButton("Save Script")
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.btn_load.clicked.connect(self._load_script)
        self.btn_save.clicked.connect(self._save_script)

        self._worker_thread: threading.Thread | None = None
        self._dsl_engine: DSLEngine | None = None

    def set_dsl_engine(self, engine: DSLEngine):
        self._dsl_engine = engine

    def start(self):
        if self._running:
            return
        script = self.script_edit.toPlainText().strip()
        if not script:
            self.log_message.emit("[Auto Farm] Script trống, không thể chạy.")
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._run, args=(script,), daemon=True)
        self._worker_thread.start()
        self.log_message.emit("[Auto Farm] Bắt đầu chạy script.")
        self.status_message.emit("Auto Farm đang chạy...")

    def _run(self, script: str):
        try:
            if self._dsl_engine:
                self._dsl_engine.execute(script, log_fn=lambda msg: self.log_message.emit(f"[Auto Farm] {msg}"))
        except Exception as e:
            self.log_message.emit(f"[Auto Farm] Lỗi: {e}")
        finally:
            self._running = False
            self.status_message.emit("Auto Farm dừng.")

    def stop(self):
        if self._dsl_engine:
            self._dsl_engine.request_stop()
        self._running = False
        self.log_message.emit("[Auto Farm] Đã dừng.")
        self.status_message.emit("Đã dừng Auto Farm.")

    def _load_script(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Script", "", "Script Files (*.txt *.dsl);;All (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.script_edit.setPlainText(f.read())

    def _save_script(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Script", "", "Script Files (*.txt *.dsl);;All (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.script_edit.toPlainText())


# ---------------------------------------------------------------------------
#  Tab 2: Auto Quest
# ---------------------------------------------------------------------------
class AutoQuestTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__("Auto Quest", parent)
        layout = QVBoxLayout(self)
        desc = QLabel("Tự động làm nhiệm vụ. Cấu hình bên dưới.")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.script_edit = LineNumberEditor()
        self.script_edit.setPlaceholderText("# DSL script cho Auto Quest...")
        self.script_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.script_edit, 1)

        self._worker_thread: threading.Thread | None = None
        self._dsl_engine: DSLEngine | None = None

    def set_dsl_engine(self, engine: DSLEngine):
        self._dsl_engine = engine

    def start(self):
        if self._running:
            return
        script = self.script_edit.toPlainText().strip()
        if not script:
            self.log_message.emit("[Auto Quest] Script trống.")
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._run, args=(script,), daemon=True)
        self._worker_thread.start()
        self.log_message.emit("[Auto Quest] Bắt đầu.")
        self.status_message.emit("Auto Quest đang chạy...")

    def _run(self, script: str):
        try:
            if self._dsl_engine:
                self._dsl_engine.execute(script, log_fn=lambda msg: self.log_message.emit(f"[Auto Quest] {msg}"))
        except Exception as e:
            self.log_message.emit(f"[Auto Quest] Lỗi: {e}")
        finally:
            self._running = False
            self.status_message.emit("Auto Quest dừng.")

    def stop(self):
        if self._dsl_engine:
            self._dsl_engine.request_stop()
        self._running = False
        self.log_message.emit("[Auto Quest] Đã dừng.")


# ---------------------------------------------------------------------------
#  Tab 3: Script Console – chạy DSL tự do
# ---------------------------------------------------------------------------
class ScriptConsoleTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__("Script Console", parent)
        layout = QVBoxLayout(self)

        desc = QLabel("Console chạy DSL script tự do. Xem DSL Reference ở tab bên cạnh.")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.script_edit = LineNumberEditor()
        self.script_edit.setPlaceholderText("# Gõ DSL script ở đây...")
        self.script_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.script_edit, 1)

        btn_row = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_save = QPushButton("Save")
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.btn_load.clicked.connect(self._load)
        self.btn_save.clicked.connect(self._save)

        self._worker_thread: threading.Thread | None = None
        self._dsl_engine: DSLEngine | None = None

    def set_dsl_engine(self, engine: DSLEngine):
        self._dsl_engine = engine

    def start(self):
        if self._running:
            return
        script = self.script_edit.toPlainText().strip()
        if not script:
            self.log_message.emit("[Console] Script trống.")
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._run, args=(script,), daemon=True)
        self._worker_thread.start()
        self.log_message.emit("[Console] Chạy script...")

    def _run(self, script: str):
        try:
            if self._dsl_engine:
                self._dsl_engine.execute(script, log_fn=lambda msg: self.log_message.emit(f"[Console] {msg}"))
        except Exception as e:
            self.log_message.emit(f"[Console] Lỗi: {e}")
        finally:
            self._running = False
            self.status_message.emit("Console dừng.")

    def stop(self):
        if self._dsl_engine:
            self._dsl_engine.request_stop()
        self._running = False
        self.log_message.emit("[Console] Đã dừng.")

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Script", "", "Script Files (*.txt *.dsl);;All (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.script_edit.setPlainText(f.read())

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Script", "", "Script Files (*.txt *.dsl);;All (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.script_edit.toPlainText())


# ---------------------------------------------------------------------------
#  Tab 4: DSL Reference
# ---------------------------------------------------------------------------
class DSLReferenceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        ref = QTextEdit()
        ref.setReadOnly(True)
        ref.setFont(QFont("Consolas", 10))
        ref.setHtml(DSL_REFERENCE_HTML)
        layout.addWidget(ref)


DSL_REFERENCE_HTML = """
<h2>DSL Script Reference</h2>
<p>Mỗi dòng là một lệnh. Dòng trống hoặc bắt đầu bằng <code>#</code> được bỏ qua.</p>

<h3>Lệnh cơ bản</h3>
<table border="1" cellpadding="4" cellspacing="0">
<tr><th>Lệnh</th><th>Mô tả</th></tr>
<tr><td><code>click X Y</code></td><td>Click chuột tại tọa độ (X, Y) trong cửa sổ game</td></tr>
<tr><td><code>rclick X Y</code></td><td>Right-click tại (X, Y)</td></tr>
<tr><td><code>dclick X Y</code></td><td>Double-click tại (X, Y)</td></tr>
<tr><td><code>move X Y</code></td><td>Di chuyển chuột đến (X, Y)</td></tr>
<tr><td><code>drag X1 Y1 X2 Y2</code></td><td>Kéo chuột từ (X1,Y1) đến (X2,Y2)</td></tr>
<tr><td><code>key KEYNAME</code></td><td>Nhấn phím (ví dụ: <code>key enter</code>, <code>key space</code>)</td></tr>
<tr><td><code>type "text"</code></td><td>Gõ chuỗi ký tự</td></tr>
<tr><td><code>wait SECONDS</code></td><td>Chờ N giây (hỗ trợ số thập phân)</td></tr>
<tr><td><code>wait_random MIN MAX</code></td><td>Chờ ngẫu nhiên trong khoảng [MIN, MAX] giây</td></tr>
<tr><td><code>log "message"</code></td><td>In message ra log</td></tr>
</table>

<h3>Template matching</h3>
<table border="1" cellpadding="4" cellspacing="0">
<tr><td><code>find_and_click 'image.png'</code></td><td>Tìm ảnh trên màn hình, click vào giữa nếu tìm thấy</td></tr>
<tr><td><code>find_and_click 'image.png' THRESHOLD</code></td><td>Tìm với ngưỡng tùy chỉnh (0.0-1.0, mặc định 0.8)</td></tr>
<tr><td><code>wait_for 'image.png' TIMEOUT</code></td><td>Chờ cho đến khi tìm thấy ảnh (timeout = giây)</td></tr>
<tr><td><code>wait_and_click 'image.png' TIMEOUT</code></td><td>Chờ tìm ảnh rồi click</td></tr>
<tr><td><code>exists 'image.png'</code></td><td>Kiểm tra ảnh có tồn tại trên màn hình (dùng trong if)</td></tr>
</table>

<h3>Điều khiển luồng</h3>
<pre>
loop N           # Lặp N lần (N = số nguyên, hoặc 'forever')
  ...
end

if exists 'img.png'
  ...
elif exists 'img2.png'
  ...
else
  ...
end

# Biến
set counter 0
set counter + 1      # tăng 1
set counter - 1      # giảm 1
</pre>

<h3>Ví dụ hoàn chỉnh</h3>
<pre>
# Auto farm loop
log "Bắt đầu farm"
loop 50
  wait_and_click 'battle_btn.png' 10
  wait 2
  wait_for 'victory.png' 120
  wait 1
  click 500 400
  wait_random 1 3
end
log "Xong!"
</pre>
"""


# ---------------------------------------------------------------------------
#  Main Window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Onmyoji Bot Tool")
        self.setMinimumSize(900, 650)
        self.resize(1050, 720)

        self._capture: WindowCapture | None = None
        self._capture_worker = CaptureWorker()
        self._capture_worker.frame_ready.connect(self._on_frame)
        self._dsl_engine = DSLEngine()

        self._init_ui()
        self._populate_process_list()

        # refresh process list mỗi 5 giây
        self._proc_timer = QTimer(self)
        self._proc_timer.timeout.connect(self._populate_process_list)
        self._proc_timer.start(5000)

    # ---- UI Setup ---------------------------------------------------------
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 6)

        # ── Top: Window selector ──────────────────────────────────
        selector_group = QGroupBox("Chọn cửa sổ game")
        sel_layout = QHBoxLayout(selector_group)

        sel_layout.addWidget(QLabel("Cửa sổ:"))
        self.combo_windows = QComboBox()
        self.combo_windows.setMinimumWidth(350)
        self.combo_windows.setEditable(False)
        sel_layout.addWidget(self.combo_windows, 1)

        self.btn_refresh = QPushButton("⟳ Refresh")
        self.btn_refresh.setFixedWidth(80)
        self.btn_refresh.clicked.connect(self._populate_process_list)
        sel_layout.addWidget(self.btn_refresh)

        sel_layout.addWidget(QLabel("Hoặc nhập tên:"))
        self.txt_window_name = QLineEdit()
        self.txt_window_name.setPlaceholderText("Tên cửa sổ...")
        self.txt_window_name.setFixedWidth(200)
        sel_layout.addWidget(self.txt_window_name)

        self.btn_attach = QPushButton("▶ Attach")
        self.btn_attach.setFixedWidth(80)
        self.btn_attach.clicked.connect(self._attach_window)
        sel_layout.addWidget(self.btn_attach)

        self.btn_detach = QPushButton("■ Detach")
        self.btn_detach.setFixedWidth(80)
        self.btn_detach.setEnabled(False)
        self.btn_detach.clicked.connect(self._detach_window)
        sel_layout.addWidget(self.btn_detach)

        self.btn_restore = QPushButton("⊞ 1920×1080")
        self.btn_restore.setFixedWidth(100)
        self.btn_restore.setEnabled(False)
        self.btn_restore.setToolTip("Resize cửa sổ game về 1920x1080")
        self.btn_restore.clicked.connect(self._restore_window)
        sel_layout.addWidget(self.btn_restore)

        root_layout.addWidget(selector_group)

        # ── Middle: Preview + Tabs (splitter) ─────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: preview
        preview_box = QGroupBox("Preview")
        pv_layout = QVBoxLayout(preview_box)
        self.preview = PreviewLabel()
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pv_layout.addWidget(self.preview)

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 144)
        self.spin_fps.setValue(15)
        self.spin_fps.valueChanged.connect(lambda v: self._capture_worker.set_fps(v))
        fps_row.addWidget(self.spin_fps)
        fps_row.addStretch()
        pv_layout.addLayout(fps_row)

        preview_box.setMinimumWidth(320)
        splitter.addWidget(preview_box)

        # Right: tabs
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self._feature_tabs: list[FeatureTab] = []

        # Tạo các tab feature
        self.tab_farm = AutoFarmTab()
        self.tab_quest = AutoQuestTab()
        self.tab_console = ScriptConsoleTab()
        self.tab_ref = DSLReferenceTab()

        self._add_feature_tab(self.tab_farm)
        self._add_feature_tab(self.tab_quest)
        self._add_feature_tab(self.tab_console)
        self.tabs.addTab(self.tab_ref, "📖 DSL Reference")

        right_layout.addWidget(self.tabs, 1)

        # Start / Stop toggle button
        ctrl_row = QHBoxLayout()
        self.btn_start = QPushButton("▶  Start")
        self.btn_start.setFixedHeight(36)
        self.btn_start.setStyleSheet("background-color: #2d8c4e; color: white; font-weight: bold; font-size: 13px;")
        self.btn_start.clicked.connect(self._start_feature)
        ctrl_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; font-size: 13px;")
        self.btn_stop.clicked.connect(self._stop_feature)
        self.btn_stop.hide()
        ctrl_row.addWidget(self.btn_stop)
        right_layout.addLayout(ctrl_row)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        root_layout.addWidget(splitter, 1)

        # ── Bottom: Log ───────────────────────────────────────────
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setMaximumHeight(160)
        log_layout.addWidget(self.log_view)

        log_btn_row = QHBoxLayout()
        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.clicked.connect(self.log_view.clear)
        log_btn_row.addWidget(btn_clear_log)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)

        root_layout.addWidget(log_group)

        # Status bar
        self.statusBar().showMessage("Sẵn sàng.")

    def _add_feature_tab(self, tab: FeatureTab):
        tab.log_message.connect(self._append_log)
        tab.status_message.connect(self.statusBar().showMessage)
        if hasattr(tab, "set_dsl_engine"):
            tab.set_dsl_engine(self._dsl_engine)
        self.tabs.addTab(tab, tab.feature_name)
        self._feature_tabs.append(tab)

    # ---- Process list -----------------------------------------------------
    def _populate_process_list(self):
        current_text = self.combo_windows.currentText()
        self.combo_windows.blockSignals(True)
        self.combo_windows.clear()
        windows = list_windows()
        for w in windows:
            label = f"{w['title']}  [{w['process']}]"
            self.combo_windows.addItem(label, w["title"])
        # restore selection
        idx = self.combo_windows.findText(current_text)
        if idx >= 0:
            self.combo_windows.setCurrentIndex(idx)
        self.combo_windows.blockSignals(False)

    # ---- Attach / Detach --------------------------------------------------
    def _attach_window(self):
        # ưu tiên tên nhập tay
        name = self.txt_window_name.text().strip()
        if not name:
            name = self.combo_windows.currentData()
        if not name:
            QMessageBox.warning(self, "Lỗi", "Chọn hoặc nhập tên cửa sổ trước.")
            return
        try:
            self._capture = WindowCapture(name)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không tìm thấy cửa sổ:\n{e}")
            return

        self._dsl_engine.set_capture(self._capture)
        self._capture_worker.set_capture(self._capture)
        self._capture_worker.set_fps(self.spin_fps.value())

        if not self._capture_worker.isRunning():
            self._capture_worker.start()

        self.btn_attach.setEnabled(False)
        self.btn_detach.setEnabled(True)
        self.btn_restore.setEnabled(True)
        self._append_log(f"Đã attach vào: {name}")
        self.statusBar().showMessage(f"Attached: {name}")

    def _detach_window(self):
        self._capture_worker.stop()
        self._capture = None
        self._dsl_engine.set_capture(None)
        self.preview.clear()
        self.preview.setText("No preview")
        self.btn_attach.setEnabled(True)
        self.btn_detach.setEnabled(False)
        self.btn_restore.setEnabled(False)
        self._append_log("Đã detach cửa sổ.")
        self.statusBar().showMessage("Detached.")

    def _restore_window(self):
        if self._capture is None:
            return
        self._dsl_engine.resize_window(1920, 1080)
        self._append_log("Đã resize cửa sổ game về 1920×1080.")

    # ---- Frame callback ---------------------------------------------------
    def _on_frame(self, frame: np.ndarray):
        self.preview.update_frame(frame)
        self._dsl_engine.set_last_frame(frame)

    # ---- Start / Stop feature ---------------------------------------------
    def _current_feature_tab(self) -> FeatureTab | None:
        w = self.tabs.currentWidget()
        if isinstance(w, FeatureTab):
            return w
        return None

    def _any_feature_running(self) -> bool:
        return any(t.is_running() for t in self._feature_tabs)

    def _start_feature(self):
        if self._capture is None:
            QMessageBox.warning(self, "Lỗi", "Attach cửa sổ game trước khi chạy.")
            return
        if self._any_feature_running():
            QMessageBox.warning(self, "Lỗi", "Đã có tính năng đang chạy. Dừng trước khi chạy cái khác.")
            return
        tab = self._current_feature_tab()
        if tab is None:
            QMessageBox.information(self, "Info", "Tab hiện tại không phải feature.")
            return
        self._dsl_engine.reset_stop()
        tab.start()
        self.btn_start.hide()
        self.btn_stop.show()
        # poll khi nào feature dừng
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_feature_status)
        self._poll_timer.start(500)

    def _stop_feature(self):
        for t in self._feature_tabs:
            if t.is_running():
                t.stop()
        self.btn_stop.hide()
        self.btn_start.show()

    def _poll_feature_status(self):
        if not self._any_feature_running():
            self.btn_stop.hide()
            self.btn_start.show()
            if hasattr(self, "_poll_timer"):
                self._poll_timer.stop()

    # ---- Log --------------------------------------------------------------
    def _append_log(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_view.append(f"<span style='color:#888'>[{timestamp}]</span> {msg}")
        self.log_view.moveCursor(QTextCursor.End)

    # ---- Cleanup ----------------------------------------------------------
    def closeEvent(self, event):
        self._stop_feature()
        self._capture_worker.stop()
        event.accept()


# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    from PyQt5.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 46))
    palette.setColor(QPalette.WindowText, QColor(205, 214, 244))
    palette.setColor(QPalette.Base, QColor(24, 24, 37))
    palette.setColor(QPalette.AlternateBase, QColor(30, 30, 46))
    palette.setColor(QPalette.ToolTipBase, QColor(30, 30, 46))
    palette.setColor(QPalette.ToolTipText, QColor(205, 214, 244))
    palette.setColor(QPalette.Text, QColor(205, 214, 244))
    palette.setColor(QPalette.Button, QColor(49, 50, 68))
    palette.setColor(QPalette.ButtonText, QColor(205, 214, 244))
    palette.setColor(QPalette.BrightText, QColor(243, 139, 168))
    palette.setColor(QPalette.Link, QColor(137, 180, 250))
    palette.setColor(QPalette.Highlight, QColor(137, 180, 250))
    palette.setColor(QPalette.HighlightedText, QColor(30, 30, 46))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
