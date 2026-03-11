import threading
import time
from pathlib import Path

import win32api
import win32con
import win32gui
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QGroupBox, QSpinBox, QDoubleSpinBox, QButtonGroup, QLineEdit,
    QListWidget, QListWidgetItem, QAbstractItemView, QInputDialog,
    QFileDialog, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal

from i18n import t
from pps_engine import DSLEngine
from screenshot import WindowCapture

# Need local DSL_DIR for dialogs, importing from main or feature_tab
import sys
BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent.parent))
DSL_DIR = BASE_DIR / "dsl"

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
        
        # self._btn_pick_game = QPushButton(t("btn_pick_game"))
        # self._btn_pick_game.setToolTip(t("tooltip_pick_game"))
        # self._btn_pick_game.clicked.connect(self._pick_from_game)
        # coord_row.addWidget(self._btn_pick_game)
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

        t_thread = threading.Thread(target=waiter, daemon=True)
        t_thread.start()

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
