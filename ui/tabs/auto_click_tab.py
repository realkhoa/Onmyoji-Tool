import threading
import time
from pathlib import Path

import win32api
import win32con
import win32gui
import numpy as np
import cv2

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QGroupBox, QSpinBox, QDoubleSpinBox, QButtonGroup, QLineEdit,
    QListWidget, QListWidgetItem, QAbstractItemView, QInputDialog,
    QFileDialog, QScrollArea, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPen, QColor

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
    request_selection_signal = pyqtSignal()


    def __init__(self, parent=None):
        super().__init__(parent)
        self._capture: WindowCapture | None = None
        self._engine = DSLEngine()
        self._running = False
        self._stop_evt = threading.Event()
        self._worker: threading.Thread | None = None
        self._active = False
        self._build_ui()
        self._load_default()

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
        coord_row.addStretch()
        config_layout.addLayout(coord_row)

        # Mode selector (coordinate vs match-image)
        mode_row = QHBoxLayout()
        # Mode label with i18n fallback
        mode_label = t("lbl_mode")
        if mode_label == "lbl_mode":
            mode_label = "Mode:"
        mode_row.addWidget(QLabel(mode_label))
        self._mode_combo = QComboBox()
        c_coord = t("lbl_mode_coord")
        c_match = t("lbl_mode_match")
        if c_coord == "lbl_mode_coord":
            c_coord = "Coordinate"
        if c_match == "lbl_mode_match":
            c_match = "Match Image"
        self._mode_combo.addItems([c_coord, c_match])
        self._mode_combo.setFixedWidth(160)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        mode_row.addStretch()
        config_layout.addLayout(mode_row)

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

        # Condition Row 1: Image
        cond_img_row = QHBoxLayout()
        cond_img_row.setContentsMargins(0, 0, 0, 0)
        cond_img_row.setSpacing(4)
        self._lbl_cond_img = QLabel(t("lbl_cond_img"))
        self._lbl_cond_img.setFixedWidth(80)
        self._lbl_cond_img.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        cond_img_row.addWidget(self._lbl_cond_img)
        self._cond_img = QLineEdit()
        self._cond_img.setPlaceholderText(t("placeholder_cond_img"))
        cond_img_row.addWidget(self._cond_img, 1)
        self._btn_browse_img = QPushButton()
        self._btn_browse_img.setFixedSize(28, 24)
        self._btn_browse_img.setToolTip("Browse image file")
        self._btn_browse_img.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirOpenIcon))
        self._btn_browse_img.clicked.connect(self._browse_image)
        cond_img_row.addWidget(self._btn_browse_img)
        self._btn_pick_rect = QPushButton()
        self._btn_pick_rect.setFixedSize(28, 24)
        self._btn_pick_rect.setToolTip("Capture region from preview")
        self._btn_pick_rect.setIcon(self._make_marquee_icon(16))
        self._btn_pick_rect.clicked.connect(self._on_pick_rect_clicked)
        cond_img_row.addWidget(self._btn_pick_rect)
        config_layout.addLayout(cond_img_row)
        
        # Condition Row 2: Threshold
        cond_th_row = QHBoxLayout()
        cond_th_row.setContentsMargins(0, 0, 0, 0)
        cond_th_row.setSpacing(4)
        self._lbl_cond_thresh = QLabel(t("lbl_thresh"))
        self._lbl_cond_thresh.setFixedWidth(80)
        self._lbl_cond_thresh.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        cond_th_row.addWidget(self._lbl_cond_thresh)
        self._cond_thresh = QDoubleSpinBox()
        self._cond_thresh.setRange(0.0, 1.0)
        self._cond_thresh.setValue(0.8)
        self._cond_thresh.setSingleStep(0.05)
        self._cond_thresh.setFixedWidth(80)
        cond_th_row.addWidget(self._cond_thresh)
        cond_th_row.addStretch()
        config_layout.addLayout(cond_th_row)
        
        self._btn_add = QPushButton(t("btn_add_point"))
        self._btn_add.setObjectName("btn_primary")
        self._btn_add.setFixedHeight(32)
        self._btn_add.clicked.connect(self._add_point)
        config_layout.addWidget(self._btn_add)
        
        layout.addWidget(config_box)

        # apply initial mode visibility
        self._on_mode_changed(self._mode_combo.currentIndex())

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

        script_btns = QHBoxLayout()
        self._btn_save_script = QPushButton("💾 " + (t("btn_save_script") if t("btn_save_script") != "btn_save_script" else "Lưu kịch bản"))
        self._btn_save_script.clicked.connect(self._save_script)
        script_btns.addWidget(self._btn_save_script)
        self._btn_load_script = QPushButton("📂 " + (t("btn_load_script") if t("btn_load_script") != "btn_load_script" else "Tải kịch bản"))
        self._btn_load_script.clicked.connect(self._load_script)
        script_btns.addWidget(self._btn_load_script)
        seq_layout.addLayout(script_btns)

        layout.addWidget(seq_box)

        # 4. Global Options
        opt_box = QGroupBox(t("grp_run_options"))
        opt_layout = QHBoxLayout(opt_box)
        opt_layout.addWidget(QLabel(t("lbl_interval")))
        self._spin_interval = QDoubleSpinBox()
        self._spin_interval.setRange(0.01, 3600.0)
        self._spin_interval.setValue(1.0)
        self._spin_interval.setFixedWidth(80)
        opt_layout.addWidget(self._spin_interval)
        
        opt_layout.addSpacing(20)
        opt_layout.addWidget(QLabel(t("lbl_repeat")))
        self._spin_repeat = QSpinBox()
        self._spin_repeat.setRange(0, 1000000)
        self._spin_repeat.setFixedWidth(100)
        opt_layout.addWidget(self._spin_repeat)
        opt_layout.addStretch()
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

        # Auto-save whenever anything changes
        self._spin_interval.valueChanged.connect(lambda _: self._autosave())
        self._spin_repeat.valueChanged.connect(lambda _: self._autosave())
        self._list_points.model().rowsMoved.connect(lambda *_: self._autosave())

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

    def on_rect_selected(self, x: int, y: int, w: int, h: int):
        frame = self._engine._get_frame()
        if frame is None:
            self.log_signal.emit(t("warning_no_game_attached"))
            return
        
        # Crop safely
        fh, fw = frame.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(fw, x + w), min(fh, y + h)
        
        if x2 <= x1 or y2 <= y1:
            return
            
        crop = frame[y1:y2, x1:x2]
        
        temp_dir = BASE_DIR / "images" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"cond_{int(time.time() * 1000)}.png"
        filepath = temp_dir / filename
        
        cv2.imwrite(str(filepath), crop)
        self._cond_img.setText(f"temp/{filename}")
        # set click coords to center of selected rect (useful for match mode)
        cx = x + w // 2
        cy = y + h // 2
        try:
            self._spin_x.setValue(int(cx))
            self._spin_y.setValue(int(cy))
        except Exception:
            pass
        self.log_signal.emit(f"Saved condition image from preview: {filename}")

    def _on_mode_changed(self, idx: int):
        # show/hide controls based on selected mode
        is_match = (idx == 1)
        # coord controls
        self._spin_x.setVisible(not is_match)
        self._spin_y.setVisible(not is_match)
        # image controls
        self._lbl_cond_img.setVisible(is_match)
        self._cond_img.setVisible(is_match)
        self._btn_browse_img.setVisible(is_match)
        self._btn_pick_rect.setVisible(is_match)
        self._lbl_cond_thresh.setVisible(is_match)
        self._cond_thresh.setVisible(is_match)



    @staticmethod
    def _make_marquee_icon(size: int = 16) -> QIcon:
        """Draw a dashed rectangle (marquee / rectangle-select) icon like Photoshop."""
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(QColor(60, 130, 220), 1, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([2.0, 2.0])
        p.setPen(pen)
        m = 2
        p.drawRect(m, m, size - m * 2 - 1, size - m * 2 - 1)
        # corner handle squares
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(60, 130, 220))
        hs = 2
        for cx, cy in [(m-1, m-1), (size-m-hs, m-1), (m-1, size-m-hs), (size-m-hs, size-m-hs)]:
            p.drawRect(cx, cy, hs, hs)
        p.end()
        return QIcon(pm)

    def _on_pick_rect_clicked(self):
        try:
            if self._mode_combo.currentIndex() == 1:
                self.request_selection_signal.emit()
            else:
                # if not match mode, fall back to pick coords from game
                self._pick_from_game()
        except Exception:
            self.request_selection_signal.emit()

    def _resolve_image_path(self, rel: str) -> str | None:
        if not rel:
            return None
        p = Path(rel)
        if p.is_absolute():
            return str(p)
        # support temp/ and relative paths under DSL_DIR/images
        base = DSL_DIR / "images"
        cand = base / rel
        if cand.exists():
            return str(cand)
        # try temp subdir
        cand2 = base / "temp" / rel.split("/", 1)[-1]
        if cand2.exists():
            return str(cand2)
        return None

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
                seq = [(btn, x, y, None, 0, 'coord')]
            while not self._stop_evt.is_set():
                if repeat > 0 and cnt >= repeat:
                    break
                # iterate through sequence
                for btn_step, px, py, pimg, pth, pmode in seq:
                    if self._stop_evt.is_set():
                        break
                    if pmode == 'match':
                        # match-image mode: find template; skip interval if not found
                        if not pimg:
                            self.log_signal.emit("Skip step — no template provided for match mode")
                            continue
                        match_pos = self._engine._find_template(pimg, pth)
                        if match_pos is None:
                            self.log_signal.emit(f"Skip — template not found: {pimg}")
                            continue
                        click_x, click_y = match_pos
                    else:
                        click_x, click_y = px, py
                    lparam = win32api.MAKELONG(click_x, click_y)
                    if btn_step.lower().startswith("left"):
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
                        time.sleep(0.02)
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
                    else:
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, lparam)
                        time.sleep(0.02)
                        win32gui.PostMessage(self._capture.hwnd, win32con.WM_RBUTTONUP, 0, lparam)
                    self.log_signal.emit(f"Clicked ({click_x},{click_y}) [{btn_step}]")
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
        mode = 'match' if self._mode_combo.currentIndex() == 1 else 'coord'
        if mode == 'match':
            text = f"[{btn[0]}] match {cond_img} >= {thresh}" if cond_img else f"[{btn[0]}] match (no img)"
        else:
            text = f"[{btn[0]}] {x},{y}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, (btn, x, y, cond_img, thresh, mode))
        # set thumbnail icon if image provided and resolvable
        if cond_img:
            img_path = self._resolve_image_path(cond_img)
            if img_path:
                try:
                    pm = QPixmap(img_path)
                    if not pm.isNull():
                        item.setIcon(QIcon(pm.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio)))
                except Exception:
                    pass
        self._list_points.addItem(item)
        self.log_signal.emit(f"Added point: ({x},{y}) btn={btn}")
        self._autosave()

    def _remove_point(self):
        cur = self._list_points.currentRow()
        if cur >= 0:
            item = self._list_points.takeItem(cur)
            self.log_signal.emit(f"Removed point: {item.text()}")
            self._autosave()

    def _clear_points(self):
        self._list_points.clear()
        self.log_signal.emit(t("msg_cleared_points"))
        self._autosave()

    def _edit_point(self, item: QListWidgetItem):
        # allow user to change which mouse button for this step
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, tuple):
            return
        # support both old (5) and new (6) tuple formats
        if len(data) == 6:
            btn, px, py, img, thresh, mode = data
        else:
            btn, px, py, img, thresh = data
            mode = 'match' if img else 'coord'
        choice, ok = QInputDialog.getItem(
            self, t("title_choose_mouse"), "Button", ["Left", "Right"],
            0 if btn.lower().startswith("l") else 1, False
        )
        if ok and choice:
            data = (choice, px, py, img, thresh, mode)
            item.setData(Qt.ItemDataRole.UserRole, data)
            if mode == 'match':
                txt = f"[{choice[0]}] match {img} >= {thresh}" if img else f"[{choice[0]}] match (no img)"
            else:
                txt = f"[{choice[0]}] {px},{py}"
            item.setText(txt)
            self.log_signal.emit(f"Edited point btn={choice} mode={mode}")
            self._autosave()

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

    # ---- save / load DSL ----

    def _autosave(self):
        """Silently save current sequence to dsl/auto-click/default.atcl."""
        save_dir = DSL_DIR / "auto-click"
        save_dir.mkdir(parents=True, exist_ok=True)
        self._write_dsl(save_dir / "default.atcl")

    def _write_dsl(self, path: Path):
        seq = self._get_sequence_points()
        interval = float(self._spin_interval.value())
        repeat = int(self._spin_repeat.value())
        loop_kw = "forever" if repeat == 0 else str(repeat)
        lines = [
            "# Auto Click Script \u2013 generated by Onmyoji Tool",
            f"# interval={interval} repeat={repeat}",
            "",
            f"loop {loop_kw} {{",
        ]
        for btn, px, py, img, thresh, mode in seq:
            btn_str = btn.lower()
            if mode == 'match':
                img_safe = img or ""
                lines.append(f"    # [step] btn={btn_str} mode=match img={img_safe} thresh={thresh}")
                if img_safe:
                    lines.append(f"    find_and_click '{img_safe}' {thresh}")
                else:
                    lines.append(f"    # (no image set)")
            else:
                click_cmd = "click" if btn_str.startswith("l") else "rclick"
                lines.append(f"    # [step] btn={btn_str} mode=coord x={px} y={py}")
                lines.append(f"    {click_cmd} {px} {py}")
            lines.append(f"    wait {interval}")
        lines.append("}")
        try:
            path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:
            self.log_signal.emit(f"Autosave failed: {e}")

    def _save_script(self):
        save_dir = DSL_DIR / "auto-click"
        save_dir.mkdir(parents=True, exist_ok=True)
        default_path = str(save_dir / "default.atcl")
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu kịch bản", default_path, "Auto Click Files (*.atcl);;All Files (*)"
        )
        if not path:
            return
        self._write_dsl(Path(path))
        self.log_signal.emit(f"Saved script: {path}")

    def _load_script(self):
        save_dir = DSL_DIR / "auto-click"
        save_dir.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(
            self, "Tải kịch bản", str(save_dir), "Auto Click Files (*.atcl);;All Files (*)"
        )
        if not path:
            return
        self._load_dsl(Path(path))
        self.log_signal.emit(f"Loaded script: {path} ({self._list_points.count()} steps)")

    def _load_default(self):
        default = DSL_DIR / "auto-click" / "default.atcl"
        if default.exists():
            self._load_dsl(default)

    def _load_dsl(self, path: Path):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            self.log_signal.emit(f"Load failed: {e}")
            return

        self._list_points.clear()

        # parse header for interval/repeat
        for line in text.splitlines():
            m = line.strip()
            if m.startswith("# interval="):
                try:
                    parts = dict(p.split("=") for p in m.lstrip("# ").split())
                    self._spin_interval.setValue(float(parts.get("interval", 1.0)))
                    self._spin_repeat.setValue(int(parts.get("repeat", 0)))
                except Exception:
                    pass
                break

        # parse [step] metadata comments
        for line in text.splitlines():
            m = line.strip()
            if not m.startswith("# [step]"):
                continue
            try:
                meta = dict(p.split("=", 1) for p in m[len("# [step]"):].split())
                btn = meta.get("btn", "left").capitalize()
                mode = meta.get("mode", "coord")
                img = meta.get("img", None) or None
                thresh = float(meta.get("thresh", 0.8))
                px = int(meta.get("x", 0))
                py = int(meta.get("y", 0))

                if mode == 'match':
                    label = f"[{btn[0]}] match {img} >= {thresh}" if img else f"[{btn[0]}] match (no img)"
                else:
                    label = f"[{btn[0]}] {px},{py}"

                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, (btn, px, py, img, thresh, mode))
                if img:
                    img_path = self._resolve_image_path(img)
                    if img_path:
                        pm = QPixmap(img_path)
                        if not pm.isNull():
                            item.setIcon(QIcon(pm.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio)))
                self._list_points.addItem(item)
            except Exception:
                continue

    def _get_sequence_points(self) -> list[tuple[int, int]]:
        pts = []
        for i in range(self._list_points.count()):
            item = self._list_points.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and isinstance(data, tuple) and len(data) == 6:
                btn, px, py, img, thresh, mode = data
                pts.append((btn, int(px), int(py), img, float(thresh), mode))
            else:
                txt = item.text()
                try:
                    # fall back if old format
                    pre, coords = txt.split()
                    px, py = coords.split(",")
                    btn = 'Left' if pre.startswith('[L]') else 'Right'
                    pts.append((btn, int(px), int(py), None, 0.8, 'coord'))
                except Exception:
                    continue
        return pts
