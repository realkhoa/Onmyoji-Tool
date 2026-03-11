import sys
import threading
from pathlib import Path

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QPushButton, QSizePolicy, QFileDialog
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from i18n import t
from screenshot import WindowCapture
from pps_engine import DSLEngine

BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent.parent))
DSL_DIR = BASE_DIR / "dsl"

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
