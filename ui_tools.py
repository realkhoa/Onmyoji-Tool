"""
ui_tools.py – Giao diện thân thiện, mỗi tab là 1 tính năng game.
Tự động tìm & attach cửa sổ Onmyoji khi khởi động.
"""

import sys
import os
import time
import threading
from pathlib import Path

import cv2
import numpy as np
import win32gui
import win32process
import psutil
import win32api
import win32con
import shutil

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTextEdit, QGroupBox,
    QSplitter, QFileDialog, QCheckBox, QFrame, QSizePolicy,
    QSpacerItem, QProgressBar, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget, QLineEdit, QListWidgetItem
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QMutex, QMutexLocker, QRect, QSize
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QTextCursor, QPainter, QPalette

from screenshot import WindowCapture
from dsl_engine import DSLEngine

DSL_DIR = Path(__file__).parent
GAME_WINDOW_KEYWORDS = ["陰陽師Onmyoji"]

# ---------------------------------------------------------------------------
# Global stylesheet – Spotify dark theme
# ---------------------------------------------------------------------------
# Palette constants (keep in sync with apply_dark_palette below)
_BG       = "#121212"   # deepest background
_SURFACE  = "#181818"   # card / group background
_ELEVATED = "#282828"   # inputs, raised surfaces
_BORDER   = "#3e3e3e"   # subtle border
_ACCENT   = "#1db954"   # Spotify green
_ACCENT_H = "#1ed760"   # green hover
_TEXT_PRI = "#ffffff"
_TEXT_SEC = "#b3b3b3"
_TEXT_MUT = "#6a6a6a"
_DANGER   = "#e22134"

APP_STYLE = """
* { font-family: 'Segoe UI'; font-size: 10pt; color: #ffffff; }

QMainWindow, QDialog { background: #121212; }
QWidget { background: transparent; }

/* ── Inputs ─────────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #282828;
    border: 1px solid #3e3e3e;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 28px;
    color: #ffffff;
    selection-background-color: #1db954;
    selection-color: #000000;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 2px solid #1db954;
    padding: 3px 7px;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { width: 10px; height: 10px; }
QComboBox QAbstractItemView {
    background: #282828; border: 1px solid #3e3e3e;
    selection-background-color: #1db954; selection-color: #000; color: #fff;
}

/* ── Buttons ─────────────────────────────────────────────────── */
QPushButton {
    background: #282828;
    border: 1px solid #3e3e3e;
    border-radius: 20px;
    padding: 5px 16px;
    min-height: 28px;
    color: #ffffff;
}
QPushButton:hover  { background: #333333; border-color: #1db954; color: #1db954; }
QPushButton:pressed{ background: #1db954; border-color: #1db954; color: #000000; }
QPushButton:disabled { background: #1a1a1a; border-color: #2a2a2a; color: #535353; }

QPushButton#btn_primary {
    background: #1db954; border: 1px solid #1db954; color: #000000; font-weight: 700;
    border-radius: 20px;
}
QPushButton#btn_primary:hover   { background: #1ed760; border-color: #1ed760; }
QPushButton#btn_primary:pressed { background: #169c46; }

QPushButton#btn_success {
    background: #1db954; border: 1px solid #1db954; color: #000000; font-weight: 700;
    border-radius: 20px;
}
QPushButton#btn_success:hover   { background: #1ed760; border-color: #1ed760; }
QPushButton#btn_success:pressed { background: #169c46; }
QPushButton#btn_success:disabled { background: #1a3d27; border-color: #1a3d27; color: #4a7a5a; }

QPushButton#btn_danger {
    background: #e22134; border: 1px solid #e22134; color: #ffffff; font-weight: 700;
    border-radius: 20px;
}
QPushButton#btn_danger:hover   { background: #c91d2c; border-color: #c91d2c; }
QPushButton#btn_danger:pressed { background: #a0161f; }

/* ── Tabs ────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    border-top: 1px solid #333333;
    background: #181818;
}
QTabBar {
    background: #121212;
}
QTabBar::tab {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 22px;
    color: #b3b3b3;
    font: 10pt 'Segoe UI';
}
QTabBar::tab:hover:!selected { color: #ffffff; border-bottom: 2px solid #535353; }
QTabBar::tab:selected {
    color: #ffffff;
    font-weight: 700;
    border-bottom: 2px solid #1db954;
}

/* ── GroupBox ────────────────────────────────────────────────── */
QGroupBox {
    font-weight: 600;
    color: #b3b3b3;
    border: 1px solid #333333;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 8px;
    background: #181818;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: #1db954;
}

/* ── List ────────────────────────────────────────────────────── */
QListWidget {
    background: #282828;
    border: 1px solid #333333;
    border-radius: 6px;
    outline: none;
    color: #ffffff;
}
QListWidget::item { padding: 5px 10px; color: #ffffff; }
QListWidget::item:hover    { background: #333333; }
QListWidget::item:selected { background: #1db954; color: #000000; }

/* ── Text areas ──────────────────────────────────────────────── */
QTextEdit, QPlainTextEdit {
    background: #282828;
    border: 1px solid #333333;
    border-radius: 6px;
    color: #ffffff;
    font-family: 'Consolas';
    font-size: 9pt;
}

/* ── CheckBox ────────────────────────────────────────────────── */
QCheckBox { spacing: 6px; color: #b3b3b3; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 2px solid #535353;
    border-radius: 3px;
    background: #282828;
}
QCheckBox::indicator:hover   { border-color: #1db954; }
QCheckBox::indicator:checked { background: #1db954; border-color: #1db954; }

/* ── Splitter ────────────────────────────────────────────────── */
QSplitter::handle:horizontal {
    width: 1px; background: #333333;
}
QSplitter::handle:horizontal:hover { background: #1db954; }

/* ── ScrollBar ───────────────────────────────────────────────── */
QScrollBar:vertical {
    background: #121212; width: 6px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #535353; border-radius: 3px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #1db954; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar:horizontal {
    background: #121212; height: 6px; margin: 0;
}
QScrollBar::handle:horizontal {
    background: #535353; border-radius: 3px; min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background: #1db954; }

/* ── ToolTip ─────────────────────────────────────────────────── */
QToolTip {
    background: #282828; border: 1px solid #535353;
    color: #ffffff; padding: 4px 8px; border-radius: 4px;
}

/* ── Status label (named widget) ─────────────────────────────── */
QLabel#status_lbl {
    background: #1a1a1a;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: 600;
}

/* ── Label secondary ─────────────────────────────────────────── */
QLabel { color: #ffffff; }
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_game_window() -> str | None:
    """Tìm cửa sổ game theo keyword. Trả về tên cửa sổ hoặc None."""
    found = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        for kw in GAME_WINDOW_KEYWORDS:
            if kw in title:
                found.append(title)
                return

    win32gui.EnumWindows(_cb, None)
    return found[0] if found else None


# ---------------------------------------------------------------------------
# Preview Label
# ---------------------------------------------------------------------------

class PreviewLabel(QLabel):
    coord_changed = pyqtSignal(int, int)
    coord_selected = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 158)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#1a1a1a; border:1px solid #333333; border-radius:6px;")
        self.setMouseTracking(True)
        self._pixmap: QPixmap | None = None
        self._frame_w = self._frame_h = 0

        self._coord_label = QLabel(self)
        self._coord_label.setStyleSheet(
            "background:rgba(0,0,0,180); color:#1db954; padding:2px 6px;"
            "font:bold 10px 'Consolas'; border-radius:3px;"
        )
        self._coord_label.hide()

    def update_frame(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        self._frame_w, self._frame_h = w, h
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._rescale()

    def _rescale(self):
        if self._pixmap:
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _to_game(self, pos):
        pm = self.pixmap()
        if not pm or self._frame_w == 0:
            return None
        ox = (self.width() - pm.width()) / 2
        oy = (self.height() - pm.height()) / 2
        rx, ry = pos.x() - ox, pos.y() - oy
        if rx < 0 or ry < 0 or rx >= pm.width() or ry >= pm.height():
            return None
        return int(rx / pm.width() * self._frame_w), int(ry / pm.height() * self._frame_h)

    def mouseMoveEvent(self, event):
        coords = self._to_game(event.pos())
        if coords:
            self._coord_label.setText(f"X:{coords[0]}  Y:{coords[1]}")
            self._coord_label.adjustSize()
            lx = min(event.x() + 12, self.width() - self._coord_label.width() - 4)
            self._coord_label.move(lx, max(event.y() - 24, 4))
            self._coord_label.show()
            self.coord_changed.emit(*coords)
        else:
            self._coord_label.hide()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        coords = self._to_game(event.pos())
        if coords:
            self.coord_selected.emit(*coords)
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event):
        self._coord_label.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


# ---------------------------------------------------------------------------
# Capture Worker
# ---------------------------------------------------------------------------

class CaptureWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._capture: WindowCapture | None = None
        self._mutex = QMutex()

    def set_capture(self, cap: WindowCapture | None):
        with QMutexLocker(self._mutex):
            self._capture = cap

    def run(self):
        self._running = True
        while self._running:
            with QMutexLocker(self._mutex):
                cap = self._capture
            if cap:
                try:
                    frame = cap.capture()
                    if frame is not None:
                        self.frame_ready.emit(frame)
                except Exception:
                    pass
            self.msleep(67)  # ~15 fps

    def stop(self):
        self._running = False
        self.wait()


# ---------------------------------------------------------------------------
# Log Widget
# ---------------------------------------------------------------------------

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))
        self.setMaximumHeight(140)
        self.setStyleSheet("background:#282828; border:none;")

    def append_log(self, msg: str, color: str = "#b3b3b3"):
        ts = time.strftime("%H:%M:%S")
        self.append(f'<span style="color:#6a6a6a">[{ts}]</span> <span style="color:{color}">{msg}</span>')
        self.moveCursor(QTextCursor.End)

    def append_ok(self, msg): self.append_log(msg, "#1db954")
    def append_err(self, msg): self.append_log(msg, "#e22134")
    def append_info(self, msg): self.append_log(msg, "#4da6ff")


# ---------------------------------------------------------------------------
# Base Feature Tab
# ---------------------------------------------------------------------------

class FeatureTab(QWidget):
    """Base class cho mỗi tab tính năng."""
    log_signal = pyqtSignal(str)
    started_signal = pyqtSignal()
    stopped_signal = pyqtSignal()

    def __init__(self, title: str, description: str, default_dsl: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._dsl_file = Path(default_dsl)
        self._engine = DSLEngine()
        self._worker: threading.Thread | None = None
        self._running = False
        self._build_ui(description)

    def _build_ui(self, description: str):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Header ──────────────────────────────────────────────────
        header = QLabel(self.title)
        header.setFont(QFont("Segoe UI", 15, QFont.Bold))
        header.setStyleSheet("color:#1db954; letter-spacing:0.5px;")
        root.addWidget(header)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color:#b3b3b3; font-size:11px;")
        root.addWidget(desc_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:#333333; max-height:1px;")
        root.addWidget(sep)

        # ── DSL file selector ────────────────────────────────────────
        file_row = QHBoxLayout()
        self._file_lbl = QLabel(self._dsl_file.name if self._dsl_file.exists() else "Chưa chọn file")
        self._file_lbl.setStyleSheet(
            "background:#282828; border:1px solid #3e3e3e; border-radius:4px;"
            "padding:4px 8px; color:#b3b3b3; font:10px 'Consolas';"
        )
        self._file_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        file_row.addWidget(self._file_lbl)

        self._btn_browse = QPushButton("📂 Đổi file")
        self._btn_browse.setFixedWidth(100)
        self._btn_browse.clicked.connect(self._browse_dsl)
        file_row.addWidget(self._btn_browse)
        root.addLayout(file_row)

        # ── Start / Stop ─────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        self._btn_start = QPushButton("▶  Bắt đầu")
        self._btn_start.setFixedHeight(40)
        self._btn_start.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._btn_start.setObjectName("btn_success")
        self._btn_start.clicked.connect(self._start)
        btn_layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton("■  Dừng lại")
        self._btn_stop.setFixedHeight(40)
        self._btn_stop.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.clicked.connect(self._stop)
        self._btn_stop.hide()
        btn_layout.addWidget(self._btn_stop)
        root.addLayout(btn_layout)

        # ── Status bar ───────────────────────────────────────────────
        self._status_lbl = QLabel("Sẵn sàng")
        self._status_lbl.setObjectName("status_lbl")
        self._status_lbl.setStyleSheet("color:#1db954; font-weight:600;")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(self._status_lbl)

        root.addStretch()

    def set_capture(self, cap: WindowCapture | None):
        self._engine.set_capture(cap)

    def set_last_frame(self, frame: np.ndarray):
        self._engine.set_last_frame(frame)

    def is_running(self) -> bool:
        return self._running

    def _browse_dsl(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn DSL script", str(DSL_DIR), "DSL Files (*.dsl *.txt);;All (*)"
        )
        if path:
            self._dsl_file = Path(path)
            self._file_lbl.setText(self._dsl_file.name)

    def _set_status(self, msg: str, color: str = "#1db954"):
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color:{color}; font-weight:600;"
        )

    def _start(self):
        if self._running:
            return
        # ensure we load a user-editable copy of builtin DSL templates
        if not self._dsl_file.exists():
            self._set_status("⚠ Không tìm thấy file DSL!", "#e22134")
            self.log_signal.emit(f"[{self.title}] File không tồn tại: {self._dsl_file}")
            return
        if self._engine._capture is None:
            self._set_status("⚠ Chưa attach cửa sổ game!", "#e22134")
            self.log_signal.emit(f"[{self.title}] Chưa attach cửa sổ game.")
            return

        script = self._dsl_file.read_text(encoding="utf-8")
        self._running = True
        self._engine.reset_stop()
        self._btn_start.hide()
        self._btn_stop.show()
        self._set_status("⟳ Đang chạy...", "#1db954")
        self.started_signal.emit()
        self._worker = threading.Thread(target=self._run, args=(script,), daemon=True)
        self._worker.start()

    def _run(self, script: str):
        try:
            self._engine.execute(
                script,
                log_fn=lambda m: self.log_signal.emit(f"[{self.title}] {m}")
            )
        except Exception as e:
            self.log_signal.emit(f"[{self.title}] ❌ Lỗi: {e}")
        finally:
            self._running = False
            self._on_stopped()


    def _on_stopped(self):
        self._btn_stop.hide()
        self._btn_start.show()
        self._set_status("Đã dừng", "#e22134")
        self.stopped_signal.emit()

    def _stop(self):
        self._engine.request_stop()
        self._running = False
        self._on_stopped()
        self.log_signal.emit(f"[{self.title}] Đã dừng.")


# ---------------------------------------------------------------------------
# Tab: Phá kết giới guild
# ---------------------------------------------------------------------------

class GuildRealmRaidTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="⚔ Phá kết giới guild",
            description=(
                "Tự động tham gia và tấn công kết giới trong Guild Realm Raid (Phá kết giới). "
                "Script mặc định: guild_realm_raid.dsl"
            ),
            default_dsl="dsl/builtin/guild_realm_raid.dsl",
            parent=parent,
        )


class PersonalRealmRaidTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="⚔ Phá kết giới cá nhân",
            description=(
                "Tự động phá kết giới chế độ cá nhân. Script mặc định: dsl/builtin/personal_realm_raid.dsl"
            ),
            default_dsl="dsl/builtin/personal_realm_raid.dsl",
            parent=parent,
        )


class AutoClickTab(QWidget):
    log_signal = pyqtSignal(str)
    started_signal = pyqtSignal()
    stopped_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._capture: WindowCapture | None = None
        self._engine = DSLEngine()
        self._running = False
        self._stop_evt = threading.Event()
        self._worker: threading.Thread | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        header = QLabel("🖱 Auto Click")
        header.setFont(QFont("Segoe UI", 15, QFont.Bold))
        header.setStyleSheet("color:#1db954; letter-spacing:0.5px;")
        root.addWidget(header)

        desc = QLabel("Click tự động vào tọa độ đã chọn (hỗ trợ lấy tọa độ từ preview hoặc lấy trực tiếp từ cửa sổ game). Double-click preview để lấy tọa độ.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#b3b3b3; font-size:11px;")
        root.addWidget(desc)

        # Coordinate row
        coord_row = QHBoxLayout()
        self._spin_x = QSpinBox()
        self._spin_x.setRange(0, 10000)
        self._spin_x.setPrefix("X: ")
        self._spin_y = QSpinBox()
        self._spin_y.setRange(0, 10000)
        self._spin_y.setPrefix("Y: ")
        coord_row.addWidget(self._spin_x)
        coord_row.addWidget(self._spin_y)

        self._btn_pick_game = QPushButton("🔎 Lấy từ game")
        self._btn_pick_game.clicked.connect(self._pick_from_game)
        coord_row.addWidget(self._btn_pick_game)
        root.addLayout(coord_row)

        hint = QLabel("(Hoặc double-click vào preview để lấy tọa độ)")
        hint.setStyleSheet("color:#6a6a6a; font-size:11px;")
        root.addWidget(hint)

        # Condition row (per-point)
        cond_row = QHBoxLayout()
        cond_row.addWidget(QLabel("If image (optional):"))
        self._cond_img = QLineEdit()
        self._cond_img.setPlaceholderText("images/example.png")
        cond_row.addWidget(self._cond_img, 1)
        self._btn_browse_img = QPushButton("Browse")
        self._btn_browse_img.setFixedWidth(80)
        self._btn_browse_img.clicked.connect(self._browse_image)
        cond_row.addWidget(self._btn_browse_img)
        cond_row.addWidget(QLabel("Thresh:"))
        self._cond_thresh = QDoubleSpinBox()
        self._cond_thresh.setRange(0.0, 1.0)
        self._cond_thresh.setSingleStep(0.01)
        self._cond_thresh.setValue(0.8)
        self._cond_thresh.setFixedWidth(100)
        cond_row.addWidget(self._cond_thresh)
        root.addLayout(cond_row)

        # Points list (sequence)
        seq_row = QHBoxLayout()
        self._list_points = QListWidget()
        self._list_points.setFixedHeight(140)
        seq_row.addWidget(self._list_points, 1)

        seq_btns = QVBoxLayout()
        self._btn_add = QPushButton("➕ Thêm")
        self._btn_add.clicked.connect(self._add_point)
        seq_btns.addWidget(self._btn_add)
        self._btn_remove = QPushButton("➖ Xóa")
        self._btn_remove.clicked.connect(self._remove_point)
        seq_btns.addWidget(self._btn_remove)
        self._btn_clear = QPushButton("🧹 Xóa hết")
        self._btn_clear.clicked.connect(self._clear_points)
        seq_btns.addWidget(self._btn_clear)
        seq_btns.addStretch()
        seq_row.addLayout(seq_btns)
        root.addLayout(seq_row)

        # Options row
        opts = QHBoxLayout()
        opts.addWidget(QLabel("Button:"))
        self._cmb_button = QComboBox()
        self._cmb_button.addItems(["Left", "Right"])
        opts.addWidget(self._cmb_button)

        opts.addSpacing(8)
        opts.addWidget(QLabel("Interval(s):"))
        self._spin_interval = QDoubleSpinBox()
        self._spin_interval.setRange(0.01, 3600.0)
        self._spin_interval.setSingleStep(0.1)
        self._spin_interval.setValue(1.0)
        opts.addWidget(self._spin_interval)

        opts.addSpacing(8)
        opts.addWidget(QLabel("Repeat (0=infinite):"))
        self._spin_repeat = QSpinBox()
        self._spin_repeat.setRange(0, 1000000)
        self._spin_repeat.setValue(0)
        opts.addWidget(self._spin_repeat)

        root.addLayout(opts)

        # Start/Stop
        btn_row = QHBoxLayout()
        self._btn_start = QPushButton("▶  Bắt đầu")
        self._btn_start.setFixedHeight(40)
        self._btn_start.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._btn_start.setObjectName("btn_success")
        self._btn_start.clicked.connect(self._start)
        btn_row.addWidget(self._btn_start)
        self._btn_stop = QPushButton("■  Dừng lại")
        self._btn_stop.setFixedHeight(40)
        self._btn_stop.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.clicked.connect(self._stop)
        self._btn_stop.hide()
        btn_row.addWidget(self._btn_stop)
        root.addLayout(btn_row)

        self._status_lbl = QLabel("Sẵn sàng")
        self._status_lbl.setStyleSheet("color:#1db954; font-weight:600;")
        root.addWidget(self._status_lbl)

    def set_capture(self, cap: WindowCapture | None):
        self._capture = cap
        self._engine.set_capture(cap)

    def set_last_frame(self, frame: np.ndarray):
        pass

    def on_preview_selected(self, x: int, y: int):
        self._spin_x.setValue(x)
        self._spin_y.setValue(y)
        self.log_signal.emit(f"Picked from preview: ({x},{y})")

    def _pick_from_game(self):
        if self._capture is None:
            self.log_signal.emit("⚠ Chưa attach cửa sổ game!")
            return
        self.log_signal.emit("Nhấn vào cửa sổ game để lấy tọa độ...")

        def waiter():
            # wait for a mouse click in the system, then read cursor
            prev_state = 0
            while True:
                if self._stop_evt.is_set():
                    return
                state = win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000
                if state and not prev_state:
                    pos = win32gui.GetCursorPos()
                    try:
                        client = win32gui.ScreenToClient(self._capture.hwnd, pos)
                    except Exception:
                        client = pos
                    x, y = int(client[0]), int(client[1])
                    self._spin_x.setValue(x)
                    self._spin_y.setValue(y)
                    self.log_signal.emit(f"Picked from game: ({x},{y})")
                    return
                prev_state = state
                time.sleep(0.01)

        t = threading.Thread(target=waiter, daemon=True)
        t.start()

    def _start(self):
        if self._running:
            return
        if self._capture is None:
            self.log_signal.emit("⚠ Chưa attach cửa sổ game!")
            return
        x = int(self._spin_x.value())
        y = int(self._spin_y.value())
        btn = self._cmb_button.currentText()
        interval = float(self._spin_interval.value())
        repeat = int(self._spin_repeat.value())

        self._running = True
        self._stop_evt.clear()
        self._btn_start.hide()
        self._btn_stop.show()
        self.started_signal.emit()
        self._status_lbl.setText("⟳ Đang chạy...")

        def runner():
            cnt = 0
            # build sequence from list; if empty use single point
            seq = self._get_sequence_points()
            if not seq:
                seq = [(x, y)]
            while not self._stop_evt.is_set():
                if repeat > 0 and cnt >= repeat:
                    break
                # iterate through sequence
                for px, py, pimg, pth in seq:
                    if self._stop_evt.is_set():
                        break
                    # check per-point condition if any
                    if pimg:
                        found = self._engine._find_template(pimg, pth) is not None
                        if not found:
                            self.log_signal.emit(f"Skip ({px},{py}) — condition not met: {pimg}")
                            continue
                    lparam = win32api.MAKELONG(px, py)
                    if btn.lower().startswith("left"):
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                        time.sleep(0.02)
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
                    else:
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lparam)
                        time.sleep(0.02)
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_RBUTTONUP, 0, lparam)
                    self.log_signal.emit(f"Clicked ({px},{py}) [{btn}]")
                    # sleep interval but check stop event
                    slept = 0.0
                    while slept < interval:
                        if self._stop_evt.is_set():
                            break
                        time.sleep(min(0.1, interval - slept))
                        slept += 0.1
                cnt += 1
            self._running = False
            self._on_stopped()

        self._worker = threading.Thread(target=runner, daemon=True)
        self._worker.start()

    def _on_stopped(self):
        self._btn_stop.hide()
        self._btn_start.show()
        self._status_lbl.setText("Đã dừng")
        self.stopped_signal.emit()

    def _stop(self):
        self._stop_evt.set()
        self._running = False
        self._on_stopped()
        self.log_signal.emit("AutoClick đã dừng.")

    # ---- sequence helpers ----
    def _add_point(self):
        x = int(self._spin_x.value())
        y = int(self._spin_y.value())
        cond_img = self._cond_img.text().strip()
        if cond_img == "":
            cond_img = None
        thresh = float(self._cond_thresh.value())
        text = f"{x},{y}"
        if cond_img:
            text += f"  | if {cond_img} >= {thresh}"
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, (x, y, cond_img, thresh))
        self._list_points.addItem(item)
        self.log_signal.emit(f"Added point: ({x},{y})")

    def _remove_point(self):
        cur = self._list_points.currentRow()
        if cur >= 0:
            item = self._list_points.takeItem(cur)
            self.log_signal.emit(f"Removed point: {item.text()}")

    def _clear_points(self):
        self._list_points.clear()
        self.log_signal.emit("Cleared points list")

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh template", str(DSL_DIR / 'images'), "PNG Files (*.png);;All Files (*)")
        if path:
            try:
                base = str(DSL_DIR / 'images')
                if path.startswith(base):
                    rel = Path(path).relative_to(DSL_DIR / 'images')
                    self._cond_img.setText(str(rel).replace('\\', '/'))
                else:
                    self._cond_img.setText(path)
            except Exception:
                self._cond_img.setText(path)

    def _get_sequence_points(self) -> list[tuple[int, int]]:
        pts = []
        for i in range(self._list_points.count()):
            item = self._list_points.item(i)
            data = item.data(Qt.UserRole)
            if data and isinstance(data, tuple) and len(data) == 4:
                px, py, img, thresh = data
                pts.append((int(px), int(py), img, float(thresh)))
            else:
                txt = item.text()
                try:
                    px, py = txt.split(",")
                    pts.append((int(px), int(py), None, 0.8))
                except Exception:
                    continue
        return pts


# ---------------------------------------------------------------------------
# Tab: Placeholder cho các tính năng tương lai
# ---------------------------------------------------------------------------

class ComingSoonTab(QWidget):
    def __init__(self, feature_name: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        icon = QLabel("🚧")
        icon.setFont(QFont("Segoe UI", 32))
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)
        lbl = QLabel(f"{feature_name}\nĐang phát triển...")
        lbl.setFont(QFont("Segoe UI", 13))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color:#b3b3b3;")
        layout.addWidget(lbl)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class ToolsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Onmyoji Bot – Tools")
        self.setMinimumSize(820, 580)
        self.resize(960, 640)

        self._capture: WindowCapture | None = None
        self._capture_worker = CaptureWorker()
        self._capture_worker.frame_ready.connect(self._on_frame)

        self._feature_tabs: list[FeatureTab] = []
        self._init_ui()

        # Auto-attach timer
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._try_auto_attach)
        self._auto_timer.start(1000)
        # Thử ngay lần đầu
        self._try_auto_attach()

    # ── UI ──────────────────────────────────────────────────────────────

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Connection status banner ─────────────────────────────────
        self._conn_bar = QFrame()
        self._conn_bar.setObjectName("conn_bar")
        self._conn_bar.setStyleSheet(
            "QFrame#conn_bar { background:#181818; border-bottom:1px solid #333333; }"
        )
        self._conn_bar.setFixedHeight(44)
        cb_layout = QHBoxLayout(self._conn_bar)
        cb_layout.setContentsMargins(12, 0, 12, 0)
        cb_layout.setSpacing(10)

        self._dot = QLabel("●")
        self._dot.setFont(QFont("Segoe UI", 16))
        self._dot.setStyleSheet("color:#e22134;")
        self._dot.setFixedWidth(24)
        cb_layout.addWidget(self._dot)

        self._window_lbl = QLabel("Chưa tìm thấy cửa sổ game")
        self._window_lbl.setFont(QFont("Segoe UI", 10))
        self._window_lbl.setStyleSheet("color:#6a6a6a;")
        cb_layout.addWidget(self._window_lbl, 1)

        self._chk_auto = QCheckBox("Tự động kết nối")
        self._chk_auto.setChecked(True)
        self._chk_auto.stateChanged.connect(self._on_auto_toggle)
        cb_layout.addWidget(self._chk_auto)

        self._btn_manual_attach = QPushButton("🔗 Kết nối ngay")
        self._btn_manual_attach.setFixedHeight(28)
        self._btn_manual_attach.clicked.connect(self._manual_attach)
        cb_layout.addWidget(self._btn_manual_attach)

        root.addWidget(self._conn_bar)

        # ── Splitter: preview left | tabs right ──────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # Left: preview
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)

        preview_group = QGroupBox("Màn hình game")
        pg_layout = QVBoxLayout(preview_group)
        self._preview = PreviewLabel()
        self._preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pg_layout.addWidget(self._preview)

        self._coord_lbl = QLabel("X: –  Y: –")
        self._coord_lbl.setStyleSheet("color:#6a6a6a; font:10px 'Consolas';")
        self._coord_lbl.setAlignment(Qt.AlignRight)
        self._preview.coord_changed.connect(lambda x, y: self._coord_lbl.setText(f"X:{x}  Y:{y}"))
        pg_layout.addWidget(self._coord_lbl)

        left_layout.addWidget(preview_group, 1)

        # Resize 1920×1080 button
        self._btn_restore = QPushButton("⊞  Resize 1920×1080")
        self._btn_restore.setFixedHeight(30)
        self._btn_restore.setEnabled(False)
        self._btn_restore.clicked.connect(self._restore_window)
        left_layout.addWidget(self._btn_restore)

        left.setMinimumWidth(260)
        # allow preview pane to grow freely when window is resized
        # left.setMaximumWidth(380)
        splitter.addWidget(left)

        # Right: tabs
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # Feature tabs
        self._tab_guild = GuildRealmRaidTab()
        self._add_feature_tab(self._tab_guild, "⚔ Kết giới Guild")
        self._tab_personal = PersonalRealmRaidTab()
        self._add_feature_tab(self._tab_personal, "⚔ Kết giới Cá nhân")
        self._tab_autoclick = AutoClickTab()
        # connect preview double-click to autoclick picker
        try:
            self._preview.coord_selected.connect(self._tab_autoclick.on_preview_selected)
        except Exception:
            pass
        self._add_feature_tab(self._tab_autoclick, "🖱 Auto Click")
        self._tabs.addTab(ComingSoonTab("Tính năng khác"), "➕ Khác")

        right_layout.addWidget(self._tabs, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, 1)

        # ── Log ──────────────────────────────────────────────────────
        log_box = QGroupBox("Nhật ký hoạt động")
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(6, 4, 6, 4)
        self._log = LogWidget()
        log_layout.addWidget(self._log)

        log_btn_row = QHBoxLayout()
        btn_clear = QPushButton("🗑 Xóa log")
        btn_clear.setFixedWidth(90)
        btn_clear.clicked.connect(self._log.clear)
        log_btn_row.addWidget(btn_clear)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)

        root.addWidget(log_box)

    def _add_feature_tab(self, tab: FeatureTab, label: str):
        tab.log_signal.connect(self._on_log)
        tab.started_signal.connect(self._on_feature_started)
        tab.stopped_signal.connect(self._on_feature_stopped)
        self._tabs.addTab(tab, label)
        self._feature_tabs.append(tab)

    # ── Auto-attach ──────────────────────────────────────────────────────

    def _try_auto_attach(self):
        if not self._chk_auto.isChecked():
            return
        if self._capture is not None:
            # Kiểm tra cửa sổ vẫn còn tồn tại
            if win32gui.IsWindow(self._capture.hwnd):
                return
            # Cửa sổ bị đóng → detach
            self._do_detach(silent=True)

        name = find_game_window()
        if name:
            self._do_attach(name)

    def _manual_attach(self):
        name = find_game_window()
        if name:
            self._do_attach(name)
            self._log.append_ok(f"Đã kết nối: {name}")
        else:
            self._log.append_err("Không tìm thấy cửa sổ Onmyoji đang chạy.")

    def _do_attach(self, name: str):
        try:
            cap = WindowCapture(name)
        except Exception as e:
            self._log.append_err(f"Lỗi kết nối: {e}")
            return
        self._capture = cap
        for tab in self._feature_tabs:
            tab.set_capture(cap)
        if not self._capture_worker.isRunning():
            self._capture_worker.set_capture(cap)
            self._capture_worker.start()
        else:
            self._capture_worker.set_capture(cap)
        self._conn_bar.setStyleSheet(
            "QFrame#conn_bar { background:#0d2a1a; border-bottom:2px solid #1db954; }"
        )
        self._dot.setStyleSheet("color:#1db954;")
        self._window_lbl.setText(f"  {name}")
        self._window_lbl.setStyleSheet("color:#1db954; font-weight:600;")
        self._btn_restore.setEnabled(True)
        self._log.append_ok(f"Đã kết nối: {name}")

    def _do_detach(self, silent=False):
        self._capture_worker.set_capture(None)
        self._capture = None
        for tab in self._feature_tabs:
            tab.set_capture(None)
        self._preview.clear()
        self._preview.setStyleSheet("background:#1a1a1a; border:1px solid #333333; border-radius:6px;")
        self._conn_bar.setStyleSheet(
            "QFrame#conn_bar { background:#2d1017; border-bottom:2px solid #e22134; }"
        )
        self._dot.setStyleSheet("color:#e22134;")
        self._window_lbl.setText("Chưa tìm thấy cửa sổ game")
        self._window_lbl.setStyleSheet("color:#6a6a6a;")
        self._btn_restore.setEnabled(False)
        if not silent:
            self._log.append_info("Đã ngắt kết nối.")

    def _on_auto_toggle(self, state):
        if state == Qt.Checked:
            self._auto_timer.start(1000)
            self._log.append_info("Bật tự động kết nối.")
        else:
            self._auto_timer.stop()
            self._log.append_info("Tắt tự động kết nối.")

    # ── Frame / Feature callbacks ─────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray):
        self._preview.update_frame(frame)
        for tab in self._feature_tabs:
            tab.set_last_frame(frame)

    def _on_feature_started(self):
        # Khoá các tab khác ko cho bấm Start khi đang chạy
        sender = self.sender()
        for tab in self._feature_tabs:
            if tab is not sender:
                tab._btn_start.setEnabled(False)

    def _on_feature_stopped(self):
        for tab in self._feature_tabs:
            tab._btn_start.setEnabled(True)

    def _on_log(self, msg: str):
        self._log.append_log(msg)

    def _restore_window(self):
        if self._capture:
            from dsl_engine import DSLEngine
            eng = DSLEngine()
            eng.set_capture(self._capture)
            eng.resize_window(1920, 1080)
            self._log.append_ok("Đã resize cửa sổ game về 1920×1080.")

    # ── Cleanup ───────────────────────────────────────────────────────────

    def closeEvent(self, event):
        for tab in self._feature_tabs:
            if tab.is_running():
                tab._stop()
        self._capture_worker.stop()
        event.accept()


# ---------------------------------------------------------------------------
# Dark palette + entry point
# ---------------------------------------------------------------------------

def apply_light_palette(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(18, 18, 18))
    p.setColor(QPalette.WindowText,      QColor(255, 255, 255))
    p.setColor(QPalette.Base,            QColor(40, 40, 40))
    p.setColor(QPalette.AlternateBase,   QColor(24, 24, 24))
    p.setColor(QPalette.ToolTipBase,     QColor(40, 40, 40))
    p.setColor(QPalette.ToolTipText,     QColor(255, 255, 255))
    p.setColor(QPalette.Text,            QColor(255, 255, 255))
    p.setColor(QPalette.Button,          QColor(40, 40, 40))
    p.setColor(QPalette.ButtonText,      QColor(255, 255, 255))
    p.setColor(QPalette.BrightText,      QColor(226, 33, 52))
    p.setColor(QPalette.Link,            QColor(29, 185, 84))
    p.setColor(QPalette.Highlight,       QColor(29, 185, 84))
    p.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(p)
    app.setStyleSheet(APP_STYLE)


def main():
    app = QApplication(sys.argv)
    apply_light_palette(app)
    win = ToolsWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
