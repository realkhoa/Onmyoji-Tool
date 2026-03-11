"""
ui_tools.py – Giao diện thân thiện, mỗi tab là 1 tính năng game.
Tự động tìm & attach cửa sổ Onmyoji khi khởi động.
"""

import sys
import os
import time
import threading
from pathlib import Path

# Tối ưu hoá phần cứng cho QtWebEngine (sửa lỗi ui web bị lag, giật)
# Xoá bỏ --single-process (dễ gây nghẽn) và bật các cờ ép buộc xài GPU cho hiệu năng tốt hơn.
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-logging --log-level=3 "
    "--ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy"
)

import cv2
import numpy as np
import win32gui
import win32process
import psutil
import win32api
import win32con
import shutil

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QTextEdit, QGroupBox,
    QSplitter, QFileDialog, QCheckBox, QFrame, QSizePolicy,
    QSpacerItem, QProgressBar, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget, QLineEdit, QListWidgetItem, QInputDialog, QButtonGroup, QTabBar, QScrollArea, QStackedWidget,
    QPlainTextEdit, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QMutex, QMutexLocker, QRect, QSize, QUrl, QPoint, QDir
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QTextCursor, QPainter, QPalette, QMouseEvent, QWheelEvent, QFontDatabase, QTextFormat, QAction, QActionGroup
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6 import QtSvg # Required for Material Design SVG icons

from screenshot import WindowCapture
from pps_engine import DSLEngine
import qt_material
from qt_material import apply_stylesheet, build_stylesheet

from i18n import t, get_i18n
from i18n import t, get_i18n



class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self._editor.lineNumberAreaPaintEvent(event)


from PyQt6.QtCore import pyqtProperty, QPropertyAnimation, QEasingCurve

class ThemeToggle(QWidget):
    """Custom animated modern toggle switch with internal icons."""
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, width=58, height=30):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._checked = False
        self._thumb_pos = 4.0
        self._anim = None
        
        # Colors
        self._bg_off = QColor("#555555")
        self._bg_on = QColor("#00bcd4")
        self._thumb_color = QColor("#ffffff")

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self._animate(checked)
        self.toggled.emit(checked)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def _animate(self, checked):
        target = float(self.width() - self.height() + 4) if checked else 4.0
        self._anim = QPropertyAnimation(self, b"thumb_pos")
        self._anim.setDuration(250)
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.start()

    @pyqtProperty(float)
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background pill
        bg_col = self._bg_on if self._checked else self._bg_off
        p.setBrush(bg_col)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), self.height()/2, self.height()/2)
        
        # Draw thumb circle
        thumb_size = self.height() - 8
        p.setBrush(self._thumb_color)
        p.drawEllipse(QRect(int(self._thumb_pos), 4, thumb_size, thumb_size))
        
        # Draw icon inside thumb
        p.setPen(QColor("#333333"))
        font = p.font()
        font.setPixelSize(int(thumb_size * 0.7))
        p.setFont(font)
        
        icon = "🌙" if self._checked else "☀️"
        p.drawText(QRect(int(self._thumb_pos), 4, thumb_size, thumb_size), Qt.AlignmentFlag.AlignCenter, icon)
        p.end()


class LineNumberEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        
        # Theme colors
        self._ln_bg = QColor("#1e1e1e")
        self._ln_text = QColor("#b3b3b3")
        self._line_hi = QColor("#2c2c2c")
        
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        self.set_theme(True) # Default dark

    def lineNumberAreaWidth(self):
        digits = len(str(self.blockCount()))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(
                0, rect.y(), self.lineNumberArea.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), self._ln_bg)
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(self._ln_text)
                painter.drawText(
                    0,
                    int(top),
                    self.lineNumberArea.width() - 2,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self._line_hi)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def set_theme(self, is_dark: bool):
        if is_dark:
            self._ln_bg = QColor("#1e1e1e")
            self._ln_text = QColor("#b3b3b3")
            self._line_hi = QColor("#2c2c2c")
            self.setProperty("theme", "dark")
        else:
            self._ln_bg = QColor("#f0f0f0")
            self._ln_text = QColor("#999999")
            self._line_hi = QColor("#e8e8e8")
            self.setProperty("theme", "light")
        
        self.style().unpolish(self)
        self.style().polish(self)
        self.highlightCurrentLine()
        self.lineNumberArea.update()


BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DSL_DIR = BASE_DIR / "dsl"
GAME_WINDOW_KEYWORDS = ["陰陽師Onmyoji"]

# ---------------------------------------------------------------------------
# Global stylesheet – Spotify dark theme
# ---------------------------------------------------------------------------
# Palette constants removed – qt-material handles theming




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
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)
        self.setText(t("status_disconnected").upper())
        self._pixmap: QPixmap | None = None
        self._frame_w = self._frame_h = 0

        self._coord_label = QLabel(self)
        self._coord_label.hide()

    def update_frame(self, frame: np.ndarray):
        if self.text():
            self.setText("")
        h, w = frame.shape[:2]
        self._frame_w, self._frame_h = w, h
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._rescale()

    def _rescale(self):
        if self._pixmap:
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

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
        coords = self._to_game(event.position())
        if coords:
            self._coord_label.setText(f"X:{coords[0]}  Y:{coords[1]}")
            self._coord_label.adjustSize()
            lx = min(int(event.position().x()) + 12, self.width() - self._coord_label.width() - 4)
            self._coord_label.move(lx, max(int(event.position().y()) - 24, 4))
            self._coord_label.show()
            self.coord_changed.emit(*coords)
        else:
            self._coord_label.hide()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        coords = self._to_game(event.position())
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
        self._fps = 15  # default

    def set_fps(self, fps: int):
        """Adjust capture frame rate (frames per second)."""
        with QMutexLocker(self._mutex):
            self._fps = max(1, fps)

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
            # sleep based on current fps setting
            with QMutexLocker(self._mutex):
                fps = self._fps
            interval = int(1000 / fps) if fps > 0 else 67
            self.msleep(interval)

    def stop(self):
        self._running = False
        self.wait()


# ---------------------------------------------------------------------------
# Log Widget
# ---------------------------------------------------------------------------

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


# Draggable Tab Bar removed as requested


# ---------------------------------------------------------------------------
# Base Feature Tab
# ---------------------------------------------------------------------------

class FeatureTab(QWidget):
    """Base class cho mỗi tab tính năng."""
    log_signal = pyqtSignal(str)
    status_message = pyqtSignal(str)
    started_signal = pyqtSignal()
    stopped_signal = pyqtSignal()

    def __init__(self, title: str, description: str, default_dsl: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._dsl_file = BASE_DIR / default_dsl if default_dsl else Path()
        self._engine = DSLEngine()
        self._worker: threading.Thread | None = None
        self._running = False
        self._active = False
        self._build_ui(description)

    def on_activated(self):
        """Called when this tab is selected."""
        self._active = True

    def on_deactivated(self):
        """Called when this tab is deselected."""
        self._active = False

    def _build_ui(self, description: str):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Header ──────────────────────────────────────────────────
        header = QLabel(self.title)
        header.setObjectName("feature_header")
        root.addWidget(header)

        desc_lbl = QLabel(description)
        desc_lbl.setObjectName("feature_desc")
        desc_lbl.setWordWrap(True)
        root.addWidget(desc_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # ── DSL file selector ────────────────────────────────────────
        file_row = QHBoxLayout()
        self._file_lbl = QLabel(self._dsl_file.name if self._dsl_file.exists() else "Chưa chọn file")
        self._file_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        file_row.addWidget(self._file_lbl)

        self._btn_browse = QPushButton(t("btn_browse_file"))
        self._btn_browse.setFixedWidth(100)
        self._btn_browse.clicked.connect(self._browse_dsl)
        file_row.addWidget(self._btn_browse)
        root.addLayout(file_row)

        # ── Start / Stop ─────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._btn_start = QPushButton(t("btn_start"))
        self._btn_start.setFixedHeight(34)
        self._btn_start.setObjectName("btn_success")
        self._btn_start.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._btn_start.clicked.connect(self._start)
        btn_layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton(t("btn_stop"))
        self._btn_stop.setFixedHeight(34)
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._btn_stop.clicked.connect(self._stop)
        self._btn_stop.hide()
        btn_layout.addWidget(self._btn_stop)
        root.addLayout(btn_layout)

        # Gear animation
        self._gear_timer = QTimer(self)
        self._gear_timer.timeout.connect(self._update_gear_animation)
        self._gear_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._gear_idx = 0

        root.addStretch()

    def set_capture(self, cap: WindowCapture | None):
        self._engine.set_capture(cap)

    def set_last_frame(self, frame: np.ndarray):
        self._engine.set_last_frame(frame)

    def is_running(self) -> bool:
        return self._running

    def _browse_dsl(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("title_choose_dsl"), str(DSL_DIR), "DSL Files (*.dsl *.txt);;All (*)"
        )
        if path:
            self._dsl_file = Path(path)
            self._file_lbl.setText(self._dsl_file.name)

    def _update_gear_animation(self):
        char = self._gear_chars[self._gear_idx % len(self._gear_chars)]
        self._btn_stop.setText(f"{char} Đang chạy...")
        self._gear_idx += 1

    def _set_status(self, msg: str, color: str = "#1db954"):
        # status text removed from UI, but we can log it
        if "⚠" in msg or "❌" in msg:
             self.log_signal.emit(f"[{self.title}] {msg}")

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
        self._gear_timer.start(100)
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
        self._gear_timer.stop()
        self._btn_stop.hide()
        self._btn_stop.setText("■ Dừng lại")
        self._btn_start.show()
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
            description=t("desc_guild_raid"),
            default_dsl="dsl/builtin/guild_realm_raid.dsl",
            parent=parent,
        )


class PersonalRealmRaidTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="⚔ Phá kết giới cá nhân",
            description=t("desc_personal_raid"),
            default_dsl="dsl/builtin/personal_realm_raid.dsl",
            parent=parent,
        )


class AutoDemonParadeTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="🎯 Ném đậu (Bách Quỷ Dạ Hành)",
            description=t("desc_demon_parade"),
            default_dsl="dsl/builtin/auto_demon_parade.dsl",
            parent=parent,
        )


class AutoDuelTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="⚔️ PVP",
            description=t("desc_pvp"),
            default_dsl="dsl/builtin/auto_duel.dsl",
            parent=parent,
        )


class ScriptConsoleTab(FeatureTab):
    def __init__(self, parent=None):
        super().__init__(
            title="💻 CLI",
            description=t("desc_cli"),
            default_dsl="",  # start empty
            parent=parent,
        )
        # hide file selector since CLI uses direct editor
        try:
            self._file_lbl.hide()
            self._btn_browse.hide()
        except AttributeError:
            pass
        # insert editor area
        layout = self.layout()
        self.script_edit = LineNumberEditor()
        self.script_edit.setObjectName("script_editor")
        self.script_edit.setPlaceholderText(t("placeholder_dsl"))
        layout.insertWidget(2, self.script_edit, 1)
        # load/save buttons below editor
        btn_row = QHBoxLayout()
        self.btn_load = QPushButton(t("btn_load"))
        self.btn_save = QPushButton(t("btn_save"))
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch()
        layout.insertLayout(3, btn_row)

        self.btn_load.clicked.connect(self._load)
        self.btn_save.clicked.connect(self._save)

        self._worker_thread: threading.Thread | None = None

    def _start(self):
        # override FeatureTab behaviour to read from editor
        if self._running:
            return
        if self._engine._capture is None:
            self._set_status("⚠ Chưa attach cửa sổ game!", "#e22134")
            self.log_signal.emit("[Console] Chưa attach cửa sổ game.")
            return
        script = self.script_edit.toPlainText().strip()
        if not script:
            self.log_signal.emit("[Console] " + t("msg_script_empty"))
            return
        self._running = True
        self._engine.reset_stop()
        self._btn_start.hide()
        self._btn_stop.show()
        self._set_status("⟳ Đang chạy...", "#1db954")
        self.started_signal.emit()
        self._worker_thread = threading.Thread(target=self._run, args=(script,), daemon=True)
        self._worker_thread.start()
        self.log_signal.emit("[Console] " + t("msg_running_script"))

    def _run(self, script: str):
        try:
            self._engine.execute(script, log_fn=lambda msg: self.log_signal.emit(f"[Console] {msg}"))
        except Exception as e:
            self.log_signal.emit(f"[Console] Lỗi: {e}")
        finally:
            self._running = False
            self._on_stopped()

    def _stop(self):
        self._engine.request_stop()
        self._running = False
        self._on_stopped()

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(self, t("title_load_script"), "", "Script Files (*.txt *.dsl);;All (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.script_edit.setPlainText(f.read())

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, t("title_save_script"), "", "Script Files (*.txt *.dsl);;All (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.script_edit.toPlainText())


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
        self._active = False
        self._build_ui()

    def on_activated(self):
        self._active = True

    def on_deactivated(self):
        self._active = False

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Wrap everything in a scroll area for responsiveness
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_layout.addWidget(scroll)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        scroll.setWidget(container)

        # 1. Header
        header_lbl = QLabel(t("tab_autoclick"))
        header_lbl.setObjectName("feature_header")
        layout.addWidget(header_lbl)
        
        desc = QLabel(t("lbl_autoclick_desc"))
        desc.setWordWrap(True)
        desc.setObjectName("feature_desc")
        layout.addWidget(desc)

        # 2. Point Config Group
        config_box = QGroupBox(t("grp_point_config"))
        config_layout = QVBoxLayout(config_box)
        config_layout.setSpacing(10)
        
        # Coords row
        coord_row = QHBoxLayout()
        self._spin_x = QSpinBox()
        self._spin_x.setRange(0, 10000)
        self._spin_x.setPrefix("X: ")
        self._spin_y = QSpinBox()
        self._spin_y.setRange(0, 10000)
        self._spin_y.setPrefix("Y: ")
        coord_row.addWidget(self._spin_x)
        coord_row.addWidget(self._spin_y)
        
        self._btn_pick_game = QPushButton(t("btn_pick_game"))
        self._btn_pick_game.setToolTip(t("tooltip_pick_game"))
        self._btn_pick_game.clicked.connect(self._pick_from_game)
        coord_row.addWidget(self._btn_pick_game)
        config_layout.addLayout(coord_row)

        # Mouse button row
        mouse_row = QHBoxLayout()
        mouse_row.addWidget(QLabel(t("lbl_mouse")))
        self._btn_left = QPushButton(t("btn_left"))
        self._btn_left.setCheckable(True)
        self._btn_left.setChecked(True)
        self._btn_left.setFixedWidth(80)
        self._btn_right = QPushButton(t("btn_right"))
        self._btn_right.setCheckable(True)
        self._btn_right.setFixedWidth(80)
        
        self._btn_grp = QButtonGroup(self)
        self._btn_grp.addButton(self._btn_left)
        self._btn_grp.addButton(self._btn_right)
        
        mouse_row.addWidget(self._btn_left)
        mouse_row.addWidget(self._btn_right)
        mouse_row.addStretch()
        config_layout.addLayout(mouse_row)

        # Condition row
        cond_row = QHBoxLayout()
        cond_row.addWidget(QLabel(t("lbl_cond_img")))
        self._cond_img = QLineEdit()
        self._cond_img.setPlaceholderText(t("placeholder_cond_img"))
        cond_row.addWidget(self._cond_img)
        self._btn_browse_img = QPushButton("...")
        self._btn_browse_img.setFixedWidth(40)
        self._btn_browse_img.clicked.connect(self._browse_image)
        cond_row.addWidget(self._btn_browse_img)
        cond_row.addWidget(QLabel(t("lbl_thresh")))
        self._cond_thresh = QDoubleSpinBox()
        self._cond_thresh.setRange(0.0, 1.0)
        self._cond_thresh.setValue(0.8)
        self._cond_thresh.setSingleStep(0.05)
        self._cond_thresh.setFixedWidth(70)
        cond_row.addWidget(self._cond_thresh)
        config_layout.addLayout(cond_row)
        
        self._btn_add = QPushButton(t("btn_add_point"))
        self._btn_add.setObjectName("btn_primary")
        self._btn_add.setFixedHeight(32)
        self._btn_add.clicked.connect(self._add_point)
        config_layout.addWidget(self._btn_add)
        
        layout.addWidget(config_box)

        # 3. Sequence Group
        seq_box = QGroupBox(t("grp_sequence"))
        seq_layout = QVBoxLayout(seq_box)
        
        self._list_points = QListWidget()
        self._list_points.setFixedHeight(160)
        self._list_points.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list_points.itemDoubleClicked.connect(self._edit_point)
        seq_layout.addWidget(self._list_points, 1)
        
        list_btns = QHBoxLayout()
        self._btn_remove = QPushButton(t("btn_remove_point"))
        self._btn_remove.clicked.connect(self._remove_point)
        list_btns.addWidget(self._btn_remove)
        self._btn_clear = QPushButton(t("btn_clear_points"))
        self._btn_clear.clicked.connect(self._clear_points)
        list_btns.addWidget(self._btn_clear)
        seq_layout.addLayout(list_btns)
        
        layout.addWidget(seq_box)

        # 4. Global Options
        opt_box = QGroupBox(t("grp_run_options"))
        opt_layout = QHBoxLayout(opt_box)
        opt_layout.addWidget(QLabel(t("lbl_interval")))
        self._spin_interval = QDoubleSpinBox()
        self._spin_interval.setRange(0.01, 3600.0)
        self._spin_interval.setValue(1.0)
        opt_layout.addWidget(self._spin_interval)
        
        opt_layout.addSpacing(20)
        opt_layout.addWidget(QLabel(t("lbl_repeat")))
        self._spin_repeat = QSpinBox()
        self._spin_repeat.setRange(0, 1000000)
        opt_layout.addWidget(self._spin_repeat)
        layout.addWidget(opt_box)

        # 5. Control (Final check on success/danger names)
        ctrl_layout = QVBoxLayout()
        self._btn_start = QPushButton(t("btn_start"))
        self._btn_start.setObjectName("btn_success")
        self._btn_start.setFixedHeight(45)
        self._btn_start.clicked.connect(self._start)
        ctrl_layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton(t("btn_stop"))
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.setFixedHeight(45)
        self._btn_stop.clicked.connect(self._stop)
        self._btn_stop.hide()
        ctrl_layout.addWidget(self._btn_stop)

        self._status_lbl = QLabel(t("status_ready"))
        self._status_lbl.setObjectName("status_label")
        self._status_lbl.setProperty("type", "success")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_layout.addWidget(self._status_lbl)
        
        layout.addLayout(ctrl_layout)
        layout.addStretch()

    def set_capture(self, cap: WindowCapture | None):
        self._capture = cap
        self._engine.set_capture(cap)

    def is_running(self) -> bool:
        return self._running

    def set_last_frame(self, frame: np.ndarray):
        self._engine.set_last_frame(frame)

    def on_preview_selected(self, x: int, y: int):
        self._spin_x.setValue(x)
        self._spin_y.setValue(y)
        self.log_signal.emit(f"Picked from preview: ({x},{y})")

    def _pick_from_game(self):
        if self._capture is None:
            self.log_signal.emit(t("warning_no_game_attached"))
            return
        self.log_signal.emit(t("msg_pick_game_wait"))

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
            self.log_signal.emit(t("warning_no_game_attached"))
            return
        x = int(self._spin_x.value())
        y = int(self._spin_y.value())
        btn = self._btn_grp.checkedButton().text()
        interval = float(self._spin_interval.value())
        repeat = int(self._spin_repeat.value())

        self._running = True
        self._stop_evt.clear()
        self._btn_start.hide()
        self._btn_stop.show()
        self.started_signal.emit()
        self._status_lbl.setText(t("status_running"))

        def runner():
            cnt = 0
            # build sequence from list; if empty use single point
            seq = self._get_sequence_points()
            if not seq:
                seq = [(btn, x, y, None, 0)]
            while not self._stop_evt.is_set():
                if repeat > 0 and cnt >= repeat:
                    break
                # iterate through sequence
                for btn_step, px, py, pimg, pth in seq:
                    if self._stop_evt.is_set():
                        break
                    # check per-point condition if any
                    if pimg:
                        found = self._engine._find_template(pimg, pth) is not None
                        if not found:
                            self.log_signal.emit(f"Skip ({px},{py}) — condition not met: {pimg}")
                            continue
                    lparam = win32api.MAKELONG(px, py)
                    if btn_step.lower().startswith("left"):
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                        time.sleep(0.02)
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
                    else:
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lparam)
                        time.sleep(0.02)
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_RBUTTONUP, 0, lparam)
                    self.log_signal.emit(f"Clicked ({px},{py}) [{btn_step}]")
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
        self._status_lbl.setText(t("status_stopped"))
        self._status_lbl.setProperty("type", "info")
        self._status_lbl.style().unpolish(self._status_lbl)
        self._status_lbl.style().polish(self._status_lbl)
        self.stopped_signal.emit()

    def _stop(self):
        self._stop_evt.set()
        self._running = False
        self._on_stopped()
        self.log_signal.emit(t("msg_autoclick_stopped"))

    # ---- sequence helpers ----
    def _add_point(self):
        x = int(self._spin_x.value())
        y = int(self._spin_y.value())
        btn = self._btn_grp.checkedButton().text()
        cond_img = self._cond_img.text().strip()
        if cond_img == "":
            cond_img = None
        thresh = float(self._cond_thresh.value())
        text = f"[{btn[0]}] {x},{y}"
        if cond_img:
            text += f"  | if {cond_img} >= {thresh}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, (btn, x, y, cond_img, thresh))
        self._list_points.addItem(item)
        self.log_signal.emit(f"Added point: ({x},{y}) btn={btn}")


    def _remove_point(self):
        cur = self._list_points.currentRow()
        if cur >= 0:
            item = self._list_points.takeItem(cur)
            self.log_signal.emit(f"Removed point: {item.text()}")

    def _clear_points(self):
        self._list_points.clear()
        self.log_signal.emit(t("msg_cleared_points"))

    def _edit_point(self, item: QListWidgetItem):
        # allow user to change which mouse button for this step
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, tuple):
            return
        btn, px, py, img, thresh = data
        choice, ok = QInputDialog.getItem(
            self, t("title_choose_mouse"), "Button", ["Left", "Right"],
            0 if btn.lower().startswith("l") else 1, False
        )
        if ok and choice:
            data = (choice, px, py, img, thresh)
            item.setData(Qt.ItemDataRole.UserRole, data)
            txt = f"[{choice[0]}] {px},{py}"
            if img:
                txt += f"  | if {img} >= {thresh}"
            item.setText(txt)
            self.log_signal.emit(f"Edited point ({px},{py}) btn={choice}")

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, t("title_choose_template"), str(DSL_DIR / 'images'), "PNG Files (*.png);;All Files (*)")
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
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and isinstance(data, tuple) and len(data) == 5:
                btn, px, py, img, thresh = data
                pts.append((btn, int(px), int(py), img, float(thresh)))
            else:
                txt = item.text()
                try:
                    # fall back if old format
                    pre, coords = txt.split()
                    px, py = coords.split(",")
                    btn = 'Left' if pre.startswith('[L]') else 'Right'
                    pts.append((btn, int(px), int(py), None, 0.8))
                except Exception:
                    continue
        return pts



# ---------------------------------------------------------------------------
# Tab: Placeholder cho các tính năng tương lai
# ---------------------------------------------------------------------------

class SoulTab(FeatureTab):
    """Tab treo rắn. Có selector chủ phòng / được mời, thay đổi script accordingly."""
    def __init__(self, parent=None):
        # default to host
        super().__init__(
            title="🐍 Treo rắn",
            description=t("desc_soul"),
            default_dsl="dsl/builtin/auto_soul_host.dsl",
            parent=parent,
        )
        # insert combo right after header
        root = self.layout()
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([t("mode_host"), t("mode_invited")])
        self._mode_combo.setMaxVisibleItems(10)
        self._mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._mode_combo.currentIndexChanged.connect(self._mode_changed)
        # combo should appear before the description label (index 1)
        root.insertWidget(1, self._mode_combo)

    def _mode_changed(self, idx: int):
        if idx == 0:
            self._dsl_file = Path("dsl/builtin/auto_soul_host.dsl")
        else:
            self._dsl_file = Path("dsl/builtin/auto_soul_invited.dsl")
        self._file_lbl.setText(self._dsl_file.name)


class GuideTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Thêm trình duyệt nhúng web guide
        self.browser = QWebEngineView()
        self._url = "https://guidemyoji.com/summon-room-patterns/"
        layout.addWidget(self.browser)
        self._loaded = False

    def on_activated(self):
        if not self._loaded:
            self.browser.setUrl(QUrl(self._url))
            self._loaded = True

    def on_deactivated(self):
        # Stop and clear browser to save memory
        self.browser.stop()
        self.browser.setUrl(QUrl("about:blank"))
        self._loaded = False


class OthersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setTabBarAutoHide(True)
        if self.tabs.tabBar():
            self.tabs.tabBar().setDrawBase(False)
        layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_sub_tab_changed)
        self._prev_idx = -1
        self._active = False

    def add_sub_tab(self, widget, label):
        self.tabs.addTab(widget, label)

    def _on_sub_tab_changed(self, index):
        if not self._active:
            return
        if self._prev_idx != -1:
            prev = self.tabs.widget(self._prev_idx)
            if hasattr(prev, "on_deactivated"):
                prev.on_deactivated()
        curr = self.tabs.widget(index)
        if hasattr(curr, "on_activated"):
            curr.on_activated()
        self._prev_idx = index

    def on_activated(self):
        self._active = True
        curr = self.tabs.currentWidget()
        if hasattr(curr, "on_activated"):
            curr.on_activated()
        self._prev_idx = self.tabs.currentIndex()

    def on_deactivated(self):
        self._active = False
        curr = self.tabs.currentWidget()
        if hasattr(curr, "on_deactivated"):
            curr.on_deactivated()


class ComingSoonTab(QWidget):
    def __init__(self, feature_name: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("🚧")
        icon.setObjectName("coming_soon_icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        lbl = QLabel(t("lbl_coming_soon", feature=feature_name))
        lbl.setObjectName("coming_soon_text")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self._current_theme = 'dark_teal.xml'
        self._init_ui()
        # Set switch to match initial dark theme
        self._theme_switch.blockSignals(True)
        self._theme_switch.setChecked(True)
        self._theme_switch.blockSignals(False)

        # Auto-attach timer
        self._auto_timer = QTimer(self)
        self._auto_timer.timeout.connect(self._try_auto_attach)
        self._auto_timer.start(1000)
        
        get_i18n().language_changed.connect(self.update_texts)
        self.update_texts(get_i18n().current_lang)
        
        # Thử ngay lần đầu
        self._try_auto_attach()

    # ── UI ──────────────────────────────────────────────────────────────

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Header Panel ──────────────────────────────────────────
        self._header = QFrame()
        self._header.setObjectName("header_panel")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(32, 12, 32, 12)
        header_layout.setSpacing(10)
        
        # Consistent height for all header sub-elements
        top_h = 32

        # Theme Toggle Switch
        self._theme_switch = ThemeToggle()
        self._theme_switch.setChecked(True)  # Default dark check (app starts dark)
        self._theme_switch.toggled.connect(self._toggle_theme)
        header_layout.addWidget(self._theme_switch)

        # Language Switcher
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Tiếng Việt", "English", "Français", "中文"])
        self._lang_combo.setCurrentIndex(["vi_VN", "en_US", "fr_FR", "zh_CN"].index(get_i18n().current_lang))
        self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        header_layout.addWidget(self._lang_combo)

        header_layout.addStretch()

        # Connection Status Display
        self._conn_panel = QFrame()
        self._conn_panel.setObjectName("conn_panel")
        self._conn_panel.setFixedHeight(top_h)
        cp_layout = QHBoxLayout(self._conn_panel)
        cp_layout.setContentsMargins(10, 0, 10, 0)
        cp_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._window_lbl = QLabel(t("status_disconnected"))
        self._window_lbl.setObjectName("window_label")
        self._window_lbl.setProperty("status", "disconnected")
        cp_layout.addWidget(self._window_lbl)

        self._chk_auto = QCheckBox()
        self._chk_auto.setToolTip(t("auto_connect_tooltip"))
        self._chk_auto.setChecked(True)
        self._chk_auto.stateChanged.connect(self._on_auto_toggle)
        cp_layout.addWidget(self._chk_auto)

        header_layout.addWidget(self._conn_panel)

        # Connect/Disconnect Button
        self._btn_manual_attach = QPushButton(t("btn_connect"))
        self._btn_manual_attach.setObjectName("btn_small")
        self._btn_manual_attach.setFixedHeight(top_h)
        self._btn_manual_attach.clicked.connect(self._manual_attach)
        header_layout.addWidget(self._btn_manual_attach)
        
        root.addWidget(self._header)


        # ── Splitter: preview left | tabs right ──────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: preview
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)

        preview_group = QGroupBox(t("group_game_screen"))
        pg_layout = QVBoxLayout(preview_group)
        self._preview = PreviewLabel()
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pg_layout.addWidget(self._preview)

        self._coord_lbl = QLabel(t("coord_placeholder"))
        self._coord_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._preview.coord_changed.connect(lambda x, y: self._coord_lbl.setText(t("coord_format", x=x, y=y)))
        pg_layout.addWidget(self._coord_lbl)

        left_layout.addWidget(preview_group, 1)

        # Resize button removed as requested

        left.setMinimumWidth(260)
        # allow preview pane to grow freely when window is resized
        # left.setMaximumWidth(380)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(0)

        # Scrollable Tab Bar container
        self._tab_scroll = QScrollArea()
        self._tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tab_scroll.setWidgetResizable(True)
        self._tab_scroll.setFixedHeight(45)

        self._tab_bar = QTabBar()
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setUsesScrollButtons(False)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        self._tab_scroll.setWidget(self._tab_bar)
        
        right_layout.addWidget(self._tab_scroll)

        self._stack = QStackedWidget()
        right_layout.addWidget(self._stack, 1)

        self._prev_tab_idx = -1

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

        # treo rắn tab with host/invited selector
        self._tab_soul = SoulTab()
        self._add_feature_tab(self._tab_soul, "🐍 Treo rắn")

        # Ném đậu tab
        self._tab_demon_parade = AutoDemonParadeTab()
        self._add_feature_tab(self._tab_demon_parade, "🎯 Bách Quỷ Dạ Hành")

        # Auto PvP tab
        self._tab_auto_duel = AutoDuelTab()
        self._add_feature_tab(self._tab_auto_duel, "⚔️ PVP")

        # Other tabs nested under 'Khác'
        self._tab_others = OthersTab()
        self._tab_console = ScriptConsoleTab()
        self._tab_others.add_sub_tab(self._tab_console, "💻 CLI")
        self._tab_guide = GuideTab()
        self._tab_others.add_sub_tab(self._tab_guide, "📚 Guide")
        self._coming_soon = ComingSoonTab("Tính năng khác")
        self._tab_others.add_sub_tab(self._coming_soon, "🚧 Placeholder")
        
        # Add the 'Others' container to main bar
        # Connect signals for sub-tabs to ToolsWindow logs/lock logic
        self._add_feature_tab(self._tab_console, "💻 CLI", nested=True)
        self._add_feature_tab(self._tab_guide, "📚 Guide", nested=True)
        self._add_feature_tab(self._tab_others, "➕ Khác")

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)
        root.addWidget(splitter, 1)

        # ── Log ──────────────────────────────────────────────────────
        log_box = QGroupBox(t("group_activity_log"))
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(6, 4, 6, 4)
        self._log = LogWidget()
        log_layout.addWidget(self._log)

        log_btn_row = QHBoxLayout()
        btn_clear = QPushButton(t("btn_clear_log"))
        btn_clear.setFixedWidth(90)
        btn_clear.clicked.connect(self._log.clear)
        log_btn_row.addWidget(btn_clear)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)

        root.addWidget(log_box)

    def _add_feature_tab(self, tab: QWidget, label: str, nested: bool = False):
        if hasattr(tab, "log_signal"):
            tab.log_signal.connect(self._on_log)
        if hasattr(tab, "started_signal"):
            tab.started_signal.connect(self._on_feature_started)
        if hasattr(tab, "stopped_signal"):
            tab.stopped_signal.connect(self._on_feature_stopped)
        
        if not nested:
            self._tab_bar.addTab(label)
            self._stack.addWidget(tab)
        
        if hasattr(tab, "is_running"):
            self._feature_tabs.append(tab)

    # ── Auto-attach ──────────────────────────────────────────────────────

    def _on_lang_changed(self, idx):
        langs = ["vi_VN", "en_US", "fr_FR", "zh_CN"]
        get_i18n().load_language(langs[idx])

    def update_texts(self, lang):
        if self._capture:
            self._window_lbl.setText(t("status_connected", name=self._log_name if hasattr(self, '_log_name') else "Onmyoji"))
            self._btn_manual_attach.setText(t("btn_disconnect"))
        else:
            self._window_lbl.setText(t("status_disconnected"))
            self._btn_manual_attach.setText(t("btn_connect"))
            
        self._chk_auto.setToolTip(t("auto_connect_tooltip"))
        
        # Update tabs
        self._tab_bar.setTabText(0, t("tab_guild_raid"))
        self._tab_bar.setTabText(1, t("tab_personal_raid"))
        self._tab_bar.setTabText(2, t("tab_autoclick"))
        self._tab_bar.setTabText(3, t("tab_soul"))
        self._tab_bar.setTabText(4, t("tab_demon_parade"))
        self._tab_bar.setTabText(5, t("tab_pvp"))
        self._tab_bar.setTabText(6, t("tab_cli"))
        self._tab_bar.setTabText(7, t("tab_guide"))
        self._tab_bar.setTabText(8, t("tab_others"))

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
        if self._capture:
            self._do_detach()
            return
        name = find_game_window()
        if name:
            self._do_attach(name)
        else:
             self._log.append_err(t("error_no_window"))

    def _do_attach(self, name: str):
        try:
            cap = WindowCapture(name)
        except Exception as e:
            self._log.append_err(t("error_connection", error=e))
            return
        self._capture = cap
        for tab in self._feature_tabs:
            tab.set_capture(cap)
        if not self._capture_worker.isRunning():
            self._capture_worker.set_capture(cap)
            # apply current fps value first
            self._capture_worker.set_fps(15)
            self._capture_worker.start()
        else:
            self._capture_worker.set_capture(cap)
        self._btn_manual_attach.setText(t("btn_disconnect"))
        self._window_lbl.setText(t("status_connected", name=name))
        self._window_lbl.setProperty("status", "connected")
        self._window_lbl.style().unpolish(self._window_lbl)
        self._window_lbl.style().polish(self._window_lbl)
        self._log_name = name; self._log.append_ok(t("msg_connected", name=name))

    def _do_detach(self, silent=False):
        self._capture_worker.set_capture(None)
        self._capture = None
        for tab in self._feature_tabs:
            tab.set_capture(None)
        self._preview.clear()
        self._preview.setText(t("status_disconnected").upper())
        self._btn_manual_attach.setText(t("btn_connect"))
        self._window_lbl.setText(t("status_disconnected"))
        self._window_lbl.setProperty("status", "disconnected")
        self._window_lbl.style().unpolish(self._window_lbl)
        self._window_lbl.style().polish(self._window_lbl)
        if not silent:
            self._log.append_info(t("msg_disconnected"))

    def _on_auto_toggle(self, state):
        if state == Qt.CheckState.Checked:
            self._auto_timer.start(1000)
            self._log.append_info(t("msg_auto_connect_on"))
        else:
            self._auto_timer.stop()
            self._log.append_info(t("msg_auto_connect_off"))

    # ── Frame / Feature callbacks ─────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray):
        self._preview.update_frame(frame)
        # Tối ưu: Chỉ gửi frame cho tab đang hiện hoặc tab đang chạy script
        curr_tab = self._stack.currentWidget()
        
        # Hỗ trợ tab lồng nhau trong 'Khác'
        active_widgets = [curr_tab]
        if isinstance(curr_tab, OthersTab):
            active_widgets.append(curr_tab.tabs.currentWidget())

        for tab in self._feature_tabs:
            if tab in active_widgets or tab.is_running():
                tab.set_last_frame(frame)

    def _on_tab_changed(self, index: int):
        # Notify previous tab
        if self._prev_tab_idx != -1:
            prev_tab = self._stack.widget(self._prev_tab_idx)
            if hasattr(prev_tab, "on_deactivated"):
                prev_tab.on_deactivated()
        
        # Notify new tab
        self._stack.setCurrentIndex(index)
        curr_tab = self._stack.widget(index)
        if hasattr(curr_tab, "on_activated"):
            curr_tab.on_activated()
        
        self._prev_tab_idx = index

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

    def _toggle_theme(self, checked: bool):
        # checked = True -> Dark mode, False -> Light mode
        # Use standard material themes as base
        base_theme = 'dark_teal.xml' if checked else 'light_teal.xml'
        mode_qss_file = 'dark_styles.qss' if checked else 'light_styles.qss'
        self._current_theme = mode_qss_file
        
        app = QApplication.instance()
        try:
            if hasattr(app, '_theme_cache') and mode_qss_file in app._theme_cache:
                app.setStyleSheet(app._theme_cache[mode_qss_file])
                self._log.append_info(t("msg_theme_changed", theme=t("theme_dark") if checked else t("theme_light")) + " (Instant)")
            else:
                # Fallback if cache missing
                from qt_material import build_stylesheet
                extra = {
                    'danger': '#e22134',
                    'warning': '#ffc107',
                    'success': '#1db954',
                    'font_family': 'Consolas',
                    'density_scale': '-1',
                }
                qss = build_stylesheet(base_theme, extra=extra)
                
                # Merge with custom mode-specific QSS
                try:
                    mode_qss = (BASE_DIR / mode_qss_file).read_text(encoding="utf-8")
                    qss += "\n" + mode_qss
                except:
                    pass
                    
                app.setStyleSheet(qss)
                self._log.append_info(t("msg_theme_changed", theme=t("theme_dark") if checked else t("theme_light")))
            
            # Propagate theme change to all LineNumberEditor instances
            for tab in self._feature_tabs:
                if hasattr(tab, "script_edit") and isinstance(tab.script_edit, LineNumberEditor):
                    tab.script_edit.set_theme(checked)
                    
        except Exception as e:
            self._log.append_err(t("error_theme_change", error=e))

    # _restore_window removed

    # ── Cleanup ───────────────────────────────────────────────────────────

    def closeEvent(self, event):
        for tab in self._feature_tabs:
            if tab.is_running():
                tab._stop()
        self._capture_worker.stop()
        event.accept()


# ---------------------------------------------------------------------------
# Entry point – qt-material theme
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    
    # Global theme config (consistent across toggles)
    extra = {
        'danger': '#e22134',
        'warning': '#ffc107',
        'success': '#1db954',
        'font_family': 'Consolas',
        'density_scale': '-1',
    }
    
    # Pre-cache stylesheets to avoid lag during switching
    try:
        def get_merged_qss(base_xml, mode_qss_name):
            base_qss = build_stylesheet(base_xml, extra=extra)
            try:
                mode_qss = (BASE_DIR / mode_qss_name).read_text(encoding="utf-8")
                return base_qss + "\n" + mode_qss
            except:
                return base_qss

        app._theme_cache = {
            'dark_styles.qss': get_merged_qss('dark_teal.xml', 'dark_styles.qss'),
            'light_styles.qss': get_merged_qss('light_teal.xml', 'light_styles.qss'),
        }
    except Exception as e:
        print(f"[THEME CACHE ERROR] {e}")
        app._theme_cache = {}

    # Apply the initial theme
    try:
        if 'dark_styles.qss' in app._theme_cache:
            app.setStyleSheet(app._theme_cache['dark_styles.qss'])
        else:
            # Absolute fallback
            apply_stylesheet(app, theme='dark_teal.xml', extra=extra)
    except Exception as e:
        print(f"[THEME ERROR] {e}")

    win = ToolsWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
