import logging
import sys
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, QPushButton,
    QSizePolicy, QFileDialog, QCheckBox, QSlider, QLineEdit, QDoubleSpinBox,
    QSpinBox, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIntValidator, QDoubleValidator

from i18n import t, get_i18n
from pps_engine.screenshot import WindowCapture
from pps_engine import DSLEngine, parse_bindings

BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent.parent))
DSL_DIR = BASE_DIR / "dsl"

class FeatureTab(QWidget):
    """Base class for each feature tab.

    The engine is *not* owned here — it is injected by the main window via
    ``set_engine()``.  All feature tabs share one engine so only one feature
    script runs at a time.  Each script is automatically wrapped in
    ``loop forever {}`` so the feature body loops continuously without needing
    an explicit outer loop in the DSL file.
    """
    log_signal = pyqtSignal(str)
    status_message = pyqtSignal(str)
    started_signal = pyqtSignal()
    stopped_signal = pyqtSignal()

    def __init__(self, title_key: str, desc_key: str, default_dsl: str, parent=None):
        super().__init__(parent)
        self._title_key = title_key
        self._desc_key = desc_key
        self.title = t(title_key)          # used in log messages
        self._dsl_file = BASE_DIR / default_dsl if default_dsl else Path()
        self._engine: Optional[DSLEngine] = None   # injected from ToolsWindow
        self._worker: Optional[threading.Thread] = None
        self._running = threading.Event()           # thread-safe start/stop flag
        self._quest_action_fn: Optional[callable] = None  # set by ToolsWindow
        self._active = False
        self._binding_widgets: dict[str, QWidget] = {}
        self._build_ui()
        self._build_binding_controls()
        get_i18n().language_changed.connect(self.update_texts)

    # ------------------------------------------------------------------ #
    # Engine injection                                                      #
    # ------------------------------------------------------------------ #

    def set_engine(self, engine: DSLEngine):
        """Called by ToolsWindow to inject the shared engine."""
        self._engine = engine

    def set_quest_action_fn(self, fn: callable):
        """Called by ToolsWindow to inject a getter for the Utils quest setting."""
        self._quest_action_fn = fn

    # ------------------------------------------------------------------ #
    # Tab lifecycle                                                         #
    # ------------------------------------------------------------------ #

    def on_activated(self):
        self._active = True

    def on_deactivated(self):
        self._active = False

    def set_capture(self, cap: Optional[WindowCapture]):
        if self._engine is not None:
            self._engine.set_capture(cap)

    def set_last_frame(self, frame: np.ndarray):
        if self._engine is not None:
            self._engine.set_last_frame(frame)

    def is_running(self) -> bool:
        return self._running.is_set()

    # ------------------------------------------------------------------ #
    # UI construction                                                       #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        _content = QWidget()
        scroll.setWidget(_content)

        root = QVBoxLayout(_content)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        self._header_lbl = QLabel(t(self._title_key))
        self._header_lbl.setObjectName("feature_header")
        root.addWidget(self._header_lbl)

        self._desc_lbl = QLabel(t(self._desc_key))
        self._desc_lbl.setObjectName("feature_desc")
        self._desc_lbl.setWordWrap(True)
        root.addWidget(self._desc_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # Binding controls (populated dynamically from DSL)
        self._bindings_frame = QWidget()
        self._bindings_layout = QVBoxLayout(self._bindings_frame)
        self._bindings_layout.setContentsMargins(0, 0, 0, 0)
        self._bindings_layout.setSpacing(6)
        root.addWidget(self._bindings_frame)

        # DSL file selector
        file_row = QHBoxLayout()
        self._file_lbl = QLabel(self._dsl_file.name if self._dsl_file.exists() else t("lbl_no_file"))
        self._file_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        file_row.addWidget(self._file_lbl)

        self._btn_browse = QPushButton(t("btn_browse_file"))
        self._btn_browse.clicked.connect(self._browse_dsl)
        file_row.addWidget(self._btn_browse)
        root.addLayout(file_row)

        # Start / Stop
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._btn_start = QPushButton(t("btn_start"))
        self._btn_start.setObjectName("btn_success")
        self._btn_start.clicked.connect(self._start)
        btn_layout.addWidget(self._btn_start)

        self._btn_stop = QPushButton(t("btn_stop"))
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.clicked.connect(self._stop)
        self._btn_stop.hide()
        btn_layout.addWidget(self._btn_stop)
        root.addLayout(btn_layout)

        # Spinner animation while running
        self._gear_timer = QTimer(self)
        self._gear_timer.timeout.connect(self._update_gear_animation)
        self._gear_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._gear_idx = 0

        # Debounced restart when bindings change mid-run
        self._pending_restart = False
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.setInterval(400)
        self._restart_timer.timeout.connect(self._do_restart)

        root.addStretch()

    def update_texts(self, lang=None):
        self.title = t(self._title_key)
        self._header_lbl.setText(self.title)
        self._desc_lbl.setText(t(self._desc_key))
        self._btn_start.setText(t("btn_start"))
        self._btn_stop.setText(t("btn_stop"))
        self._btn_browse.setText(t("btn_browse_file"))
        if not self._dsl_file.exists():
            self._file_lbl.setText(t("lbl_no_file"))

    # ------------------------------------------------------------------ #
    # Binding controls                                                      #
    # ------------------------------------------------------------------ #

    def _browse_dsl(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("title_choose_dsl"), str(DSL_DIR), "DSL Files (*.dsl *.txt);;All (*)"
        )
        if path:
            self._dsl_file = Path(path)
            self._file_lbl.setText(self._dsl_file.name)
            self._build_binding_controls()

    def _build_binding_controls(self):
        while self._bindings_layout.count():
            item = self._bindings_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                sub = item.layout()
                while sub.count():
                    si = sub.takeAt(0)
                    if si.widget():
                        si.widget().deleteLater()
        self._binding_widgets.clear()

        if not self._dsl_file.exists():
            return

        try:
            script = self._dsl_file.read_text(encoding="utf-8")
        except Exception:
            return

        bindings = parse_bindings(script)
        if not bindings:
            return

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        self._bindings_layout.addWidget(sep)

        for b in bindings:
            name: str = b["name"]
            btype: str = b["type"]
            default = b["default"]
            row = QHBoxLayout()
            row.setSpacing(8)

            lbl = QLabel(name.replace("_", " ").capitalize())

            if btype == "boolean":
                w = QCheckBox()
                w.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                if default is not None:
                    w.setChecked(default.lower() in ("true", "1", "yes"))
                row.addWidget(w)
                row.addWidget(lbl)
                row.addStretch()
                self._binding_widgets[name] = w
                w.stateChanged.connect(self._schedule_restart)

            elif btype == "slider":
                lbl.setFixedWidth(120)
                row.addWidget(lbl)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(1, 200)
                slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                slider.setMinimumWidth(120)
                slider.setPageStep(5)
                slider.setTickInterval(10)
                slider.setTickPosition(QSlider.TickPosition.TicksBelow)
                spin = QSpinBox()
                spin.setRange(1, 200)
                spin.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
                try:
                    val = int(default) if default is not None else 10
                except (TypeError, ValueError):
                    val = 10
                slider.setValue(val)
                spin.setValue(val)
                slider.valueChanged.connect(spin.setValue)
                spin.valueChanged.connect(slider.setValue)
                row.addWidget(slider)
                row.addWidget(spin)
                self._binding_widgets[name] = spin
                spin.valueChanged.connect(self._schedule_restart)
                container = QWidget()
                container.setLayout(row)
                self._bindings_layout.addWidget(container)
                continue

            elif btype == "number":
                lbl.setFixedWidth(120)
                row.addWidget(lbl)
                w = QLineEdit()
                w.setValidator(QDoubleValidator())
                w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
                w.setText(default if default is not None else "0")
                w.editingFinished.connect(self._schedule_restart)
                row.addWidget(w)

            else:  # string
                lbl.setFixedWidth(120)
                row.addWidget(lbl)
                w = QLineEdit()
                w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                w.setText(default if default is not None else "")
                w.editingFinished.connect(self._schedule_restart)
                row.addWidget(w)

            row.addStretch()
            self._binding_widgets[name] = w
            container = QWidget()
            container.setLayout(row)
            self._bindings_layout.addWidget(container)

    def get_bindings(self) -> dict:
        result = {}
        for name, w in self._binding_widgets.items():
            if isinstance(w, QCheckBox):
                result[name] = 1.0 if w.isChecked() else 0.0
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                result[name] = w.value()
            elif isinstance(w, QLineEdit):
                text = w.text().strip()
                try:
                    result[name] = float(text)
                except ValueError:
                    result[name] = text
        return result

    # ------------------------------------------------------------------ #
    # Restart on binding change                                            #
    # ------------------------------------------------------------------ #

    def _schedule_restart(self, *_):
        if self._running.is_set():
            self._restart_timer.start()

    def _do_restart(self):
        if not self._running.is_set():
            return
        self._pending_restart = True
        if self._engine is not None:
            self._engine.request_stop()

    # ------------------------------------------------------------------ #
    # Run logic                                                            #
    # ------------------------------------------------------------------ #

    def _update_gear_animation(self):
        char = self._gear_chars[self._gear_idx % len(self._gear_chars)]
        label = t("status_running").split(None, 1)
        suffix = label[1] if len(label) > 1 else label[0]
        self._btn_stop.setText(f"{char} {suffix}")
        self._gear_idx += 1

    def _set_status(self, msg: str, color: str = "#1db954"):
        if "⚠" in msg or "❌" in msg:
            self.log_signal.emit(f"[{self.title}] {msg}")

    def _start(self):
        if self._running.is_set():
            return
        if not self._dsl_file.exists():
            self._set_status(t("msg_file_not_found"), "#e22134")
            self.log_signal.emit(f"[{self.title}] {t('msg_file_not_found')}: {self._dsl_file}")
            return
        if self._engine is None or self._engine._capture is None:
            self._set_status(t("warning_no_game_attached"), "#e22134")
            self.log_signal.emit(f"[{self.title}] {t('warning_no_game_attached')}")
            return

        script = self._dsl_file.read_text(encoding="utf-8")
        self._running.set()
        self._engine.reset_stop()
        self._btn_start.hide()
        self._btn_stop.show()
        self._gear_timer.start(100)
        self.started_signal.emit()
        self._worker = threading.Thread(target=self._run, args=(script,), daemon=True)
        self._worker.start()

    def _run(self, script: str):
        # Inject wanted-quest handler at the top of the body if Accept is chosen.
        if self._quest_action_fn and self._quest_action_fn() == "Accept":
            script = "find_and_click 'coop_wanted_quest_accept.png'\n" + script
        # Wrap the feature body in the master loop so the tool continuously
        # repeats the feature until the user clicks Stop.
        wrapped = f"loop forever {{\n{script}\n}}"
        try:
            self._engine.execute(
                wrapped,
                log_fn=lambda m: self.log_signal.emit(f"[{self.title}] {m}"),
                bindings=self.get_bindings(),
            )
        except Exception as e:
            logger.error("DSL execution error in tab '%s': %s", self.title, e)
            self.log_signal.emit(f"[{self.title}] ❌ Lỗi: {e}")
        finally:
            self._running.clear()
            self._on_stopped()

    def _on_stopped(self):
        self._gear_timer.stop()
        self._btn_stop.hide()
        self._btn_stop.setText(t("btn_stop"))
        self._btn_start.show()
        self.stopped_signal.emit()
        if self._pending_restart:
            self._pending_restart = False
            self._start()

    def _stop(self):
        if self._engine is not None:
            self._engine.request_stop()
        self._running.clear()
        self._on_stopped()
        self.log_signal.emit(f"[{self.title}] Đã dừng.")
