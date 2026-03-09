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

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTextEdit, QGroupBox,
    QSplitter, QFileDialog, QCheckBox, QFrame, QSizePolicy,
    QSpacerItem, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QMutex, QMutexLocker, QRect, QSize
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QTextCursor, QPainter, QPalette

from screenshot import WindowCapture
from dsl_engine import DSLEngine

DSL_DIR = Path(__file__).parent
GAME_WINDOW_KEYWORDS = ["陰陽師Onmyoji"]


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 158)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#1e1e2e; border:1px solid #444; border-radius:4px;")
        self.setMouseTracking(True)
        self._pixmap: QPixmap | None = None
        self._frame_w = self._frame_h = 0

        self._coord_label = QLabel(self)
        self._coord_label.setStyleSheet(
            "background:rgba(0,0,0,180); color:#00ff88; padding:2px 6px;"
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
        self.setStyleSheet("background:#12121d; border:none;")

    def append_log(self, msg: str, color: str = "#cdd6f4"):
        ts = time.strftime("%H:%M:%S")
        self.append(f'<span style="color:#555">[{ts}]</span> <span style="color:{color}">{msg}</span>')
        self.moveCursor(QTextCursor.End)

    def append_ok(self, msg): self.append_log(msg, "#a6e3a1")
    def append_err(self, msg): self.append_log(msg, "#f38ba8")
    def append_info(self, msg): self.append_log(msg, "#89b4fa")


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
        header.setStyleSheet("color:#cba6f7;")
        root.addWidget(header)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color:#a6adc8; font-size:11px;")
        root.addWidget(desc_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#313244;")
        root.addWidget(sep)

        # ── DSL file selector ────────────────────────────────────────
        file_row = QHBoxLayout()
        self._file_lbl = QLabel(self._dsl_file.name if self._dsl_file.exists() else "Chưa chọn file")
        self._file_lbl.setStyleSheet(
            "background:#1e1e2e; border:1px solid #45475a; border-radius:4px;"
            "padding:4px 8px; color:#cdd6f4; font:10px 'Consolas';"
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
        self._btn_start.setFixedHeight(48)
        self._btn_start.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self._btn_start.setStyleSheet("""
            QPushButton {
                background:#2d8c4e; color:white; border-radius:8px;
            }
            QPushButton:hover { background:#3aad61; }
            QPushButton:pressed { background:#206636; }
        """)
        self._btn_start.clicked.connect(self._start)
        btn_layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton("■  Dừng lại")
        self._btn_stop.setFixedHeight(48)
        self._btn_stop.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self._btn_stop.setStyleSheet("""
            QPushButton {
                background:#c0392b; color:white; border-radius:8px;
            }
            QPushButton:hover { background:#e74c3c; }
            QPushButton:pressed { background:#922b21; }
        """)
        self._btn_stop.clicked.connect(self._stop)
        self._btn_stop.hide()
        btn_layout.addWidget(self._btn_stop)
        root.addLayout(btn_layout)

        # ── Status bar ───────────────────────────────────────────────
        self._status_lbl = QLabel("Sẵn sàng")
        self._status_lbl.setStyleSheet(
            "background:#313244; border-radius:4px; padding:4px 10px;"
            "color:#a6e3a1; font:bold 11px 'Segoe UI';"
        )
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

    def _set_status(self, msg: str, color: str = "#a6e3a1"):
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(
            f"background:#313244; border-radius:4px; padding:4px 10px;"
            f"color:{color}; font:bold 11px 'Segoe UI';"
        )

    def _start(self):
        if self._running:
            return
        if not self._dsl_file.exists():
            self._set_status("⚠ Không tìm thấy file DSL!", "#f38ba8")
            self.log_signal.emit(f"[{self.title}] File không tồn tại: {self._dsl_file}")
            return
        if self._engine._capture is None:
            self._set_status("⚠ Chưa attach cửa sổ game!", "#f38ba8")
            self.log_signal.emit(f"[{self.title}] Chưa attach cửa sổ game.")
            return

        script = self._dsl_file.read_text(encoding="utf-8")
        self._running = True
        self._engine.reset_stop()
        self._btn_start.hide()
        self._btn_stop.show()
        self._set_status("⟳ Đang chạy...", "#89b4fa")
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
        self._set_status("Đã dừng", "#f38ba8")
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
            default_dsl="guild_realm_raid.dsl",
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
        lbl.setStyleSheet("color:#6c7086;")
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

        # ── Top bar: game status ─────────────────────────────────────
        top_bar = QHBoxLayout()

        # Indicator dot + tên cửa sổ
        self._dot = QLabel("●")
        self._dot.setFont(QFont("Segoe UI", 14))
        self._dot.setStyleSheet("color:#f38ba8;")
        self._dot.setFixedWidth(22)
        top_bar.addWidget(self._dot)

        self._window_lbl = QLabel("Chưa tìm thấy cửa sổ game")
        self._window_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self._window_lbl.setStyleSheet("color:#a6adc8;")
        top_bar.addWidget(self._window_lbl, 1)

        self._chk_auto = QCheckBox("Tự động kết nối")
        self._chk_auto.setChecked(True)
        self._chk_auto.setStyleSheet("color:#cdd6f4;")
        self._chk_auto.stateChanged.connect(self._on_auto_toggle)
        top_bar.addWidget(self._chk_auto)

        self._btn_manual_attach = QPushButton("🔗 Kết nối ngay")
        self._btn_manual_attach.setFixedHeight(28)
        self._btn_manual_attach.clicked.connect(self._manual_attach)
        top_bar.addWidget(self._btn_manual_attach)

        root.addLayout(top_bar)

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
        self._coord_lbl.setStyleSheet("color:#585b70; font:10px 'Consolas';")
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
        left.setMaximumWidth(380)
        splitter.addWidget(left)

        # Right: tabs
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setStyleSheet("""
            QTabBar::tab { padding:8px 18px; font-size:11px; }
            QTabBar::tab:selected { font-weight:bold; }
        """)

        # Feature tabs
        self._tab_guild = GuildRealmRaidTab()
        self._add_feature_tab(self._tab_guild, "⚔ Kết giới Guild")
        self._tab_personal = PersonalRealmRaidTab()
        self._add_feature_tab(self._tab_personal, "⚔ Kết giới Cá nhân")        
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
        self._dot.setStyleSheet("color:#a6e3a1;")
        self._window_lbl.setText(f"🟢  {name}")
        self._window_lbl.setStyleSheet("color:#a6e3a1; font-weight:bold;")
        self._btn_restore.setEnabled(True)
        self._log.append_ok(f"Đã kết nối: {name}")

    def _do_detach(self, silent=False):
        self._capture_worker.set_capture(None)
        self._capture = None
        for tab in self._feature_tabs:
            tab.set_capture(None)
        self._preview.clear()
        self._preview.setStyleSheet("background:#1e1e2e; border:1px solid #444; border-radius:4px;")
        self._dot.setStyleSheet("color:#f38ba8;")
        self._window_lbl.setText("Chưa tìm thấy cửa sổ game")
        self._window_lbl.setStyleSheet("color:#a6adc8;")
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

def apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(30, 30, 46))
    p.setColor(QPalette.WindowText,      QColor(205, 214, 244))
    p.setColor(QPalette.Base,            QColor(24, 24, 37))
    p.setColor(QPalette.AlternateBase,   QColor(30, 30, 46))
    p.setColor(QPalette.ToolTipBase,     QColor(30, 30, 46))
    p.setColor(QPalette.ToolTipText,     QColor(205, 214, 244))
    p.setColor(QPalette.Text,            QColor(205, 214, 244))
    p.setColor(QPalette.Button,          QColor(49, 50, 68))
    p.setColor(QPalette.ButtonText,      QColor(205, 214, 244))
    p.setColor(QPalette.BrightText,      QColor(243, 139, 168))
    p.setColor(QPalette.Link,            QColor(137, 180, 250))
    p.setColor(QPalette.Highlight,       QColor(137, 180, 250))
    p.setColor(QPalette.HighlightedText, QColor(30, 30, 46))
    app.setPalette(p)


def main():
    app = QApplication(sys.argv)
    apply_dark_palette(app)
    win = ToolsWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
