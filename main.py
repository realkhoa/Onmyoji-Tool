"""
ui_tools.py – Giao diện thân thiện, mỗi tab là 1 tính năng game.
Tự động tìm & attach cửa sổ Onmyoji khi khởi động.
"""

import logging
import sys
import os
import win32gui
import numpy as np
from pathlib import Path

# ── Logging setup ────────────────────────────────────────────────────────────
def _configure_logging():
    log_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    log_file = log_dir / "onmyoji_tool.log"
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )

_configure_logging()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QSplitter, QCheckBox, QFrame, 
    QSizePolicy, QComboBox, QStackedWidget, QListWidget
)
from PyQt6.QtCore import Qt, QTimer



from i18n import t, get_i18n
from ui.style import APP_STYLE
from ui.comps.preview_label import PreviewLabel
from ui.comps.log_widget import LogWidget
from ui.comps.line_number_area import LineNumberEditor
from helpers.capture import CaptureWorker
from helpers.window import find_game_window, list_all_windows
from pps_engine.screenshot import WindowCapture

from pps_engine import DSLEngine

from ui.tabs.feature_tab import FeatureTab
from ui.tabs.guild_realm_raid import GuildRealmRaidTab
from ui.tabs.personal_realm_raid import PersonalRealmRaidTab
from ui.tabs.auto_demon_parade import AutoDemonParadeTab
from ui.tabs.auto_duel import AutoDuelTab
from ui.tabs.script_console_tab import ScriptConsoleTab
from ui.tabs.auto_click_tab import AutoClickTab
from ui.tabs.soul_tab import SoulTab
from ui.tabs.guide_tab import GuideTab
from ui.tabs.coming_soon_tab import ComingSoonTab
from ui.tabs.utils_tab import UtilsTab

# Tối ưu hoá phần cứng cho QtWebEngine (sửa lỗi ui web bị lag, giật)
# Xoá bỏ --single-process (dễ gây nghẽn) và bật các cờ ép buộc xài GPU cho hiệu năng tốt hơn.
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-logging --log-level=3 "
    "--ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy"
)

BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DSL_DIR = BASE_DIR / "dsl"
GAME_WINDOW_KEYWORDS = ["陰陽師Onmyoji"]

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

        # Single shared DSL engine — all feature tabs run through this one instance
        # so only one feature script executes at a time.
        self._engine = DSLEngine()

        self._feature_tabs: list[FeatureTab] = []
        self._init_ui()

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
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar Frame ──────────────────────────────────────────
        self._sidebar_frame = QFrame()
        self._sidebar_frame.setObjectName("sidebar_frame")
        self._sidebar_frame.setFixedWidth(220)
        
        sidebar_layout = QVBoxLayout(self._sidebar_frame)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(12)

        # Logo Area
        self._logo_title = QLabel("ONMYOJI BOT")
        self._logo_title.setObjectName("sidebar_title")
        self._logo_sub = QLabel(t("logo_subtitle"))
        self._logo_sub.setObjectName("sidebar_subtitle")
        
        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(2)
        logo_layout.addWidget(self._logo_title)
        logo_layout.addWidget(self._logo_sub)
        sidebar_layout.addLayout(logo_layout)

        # Navigation
        self._sidebar_list = QListWidget()
        self._sidebar_list.setObjectName("sidebar_list")
        for _ in range(10):
            self._sidebar_list.addItem("")
        self._sidebar_list.currentRowChanged.connect(self._on_tab_changed)
        sidebar_layout.addWidget(self._sidebar_list, 1)

        # Connection Status Panel
        self._conn_panel = QFrame()
        self._conn_panel.setObjectName("conn_panel")
        
        conn_layout = QVBoxLayout(self._conn_panel)
        conn_layout.setContentsMargins(0, 0, 0, 0)
        conn_layout.setSpacing(8)
        
        led_lbl_layout = QHBoxLayout()
        led_lbl_layout.setContentsMargins(0, 0, 0, 0)
        led_lbl_layout.setSpacing(6)
        
        self._conn_led = QLabel()
        self._conn_led.setObjectName("conn_status_led")
        self._conn_led.setFixedSize(8, 8)
        self._conn_led.setProperty("status", "disconnected")
        
        self._window_lbl = QLabel(t("status_disconnected"))
        self._window_lbl.setObjectName("window_label")
        
        led_lbl_layout.addWidget(self._conn_led)
        led_lbl_layout.addWidget(self._window_lbl)
        led_lbl_layout.addStretch()
        conn_layout.addLayout(led_lbl_layout)
        
        self._chk_auto = QCheckBox()
        self._chk_auto.setToolTip(t("auto_connect_tooltip"))
        self._chk_auto.setChecked(True)
        self._chk_auto.stateChanged.connect(self._on_auto_toggle)
        conn_layout.addWidget(self._chk_auto)
        
        self._btn_manual_attach = QPushButton(t("btn_connect"))
        self._btn_manual_attach.clicked.connect(self._manual_attach)
        conn_layout.addWidget(self._btn_manual_attach)
        
        sidebar_layout.addWidget(self._conn_panel)
        
        # ── Right Content Area ─────────────────────────────────────
        right_content = QWidget()
        right_layout = QVBoxLayout(right_content)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        # Top Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Tiếng Việt", "English", "Français", "中文"])
        try:
            self._lang_combo.setCurrentIndex(["vi_VN", "en_US", "fr_FR", "zh_CN"].index(get_i18n().current_lang))
        except ValueError:
            self._lang_combo.setCurrentIndex(0)
        self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        header_layout.addWidget(self._lang_combo)
        
        header_layout.addStretch()
        
        self._proc_combo = QComboBox()
        self._proc_combo.setToolTip(t("tooltip_proc_combo"))
        self._proc_combo.hide()
        header_layout.addWidget(self._proc_combo)
        
        top_h = 32
        self._btn_refresh_proc = QPushButton("↻")
        self._btn_refresh_proc.setObjectName("btn_icon")
        self._btn_refresh_proc.setFixedSize(top_h, top_h)
        self._btn_refresh_proc.setToolTip(t("tooltip_refresh_proc"))
        self._btn_refresh_proc.clicked.connect(self._refresh_proc_list)
        self._btn_refresh_proc.hide()
        header_layout.addWidget(self._btn_refresh_proc)
        
        right_layout.addLayout(header_layout)

        # ── Splitter ────────────────────────────────────────────────
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
        
        # Preview on/off toggle
        preview_bottom = QHBoxLayout()
        self._chk_preview = QCheckBox(t("preview_toggle"))
        self._chk_preview.setChecked(True)
        self._chk_preview.toggled.connect(self._preview.set_preview_enabled)
        preview_bottom.addWidget(self._chk_preview)
        
        self._coord_lbl = QLabel(t("coord_placeholder"))
        self._coord_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._preview.coord_changed.connect(lambda x, y: self._coord_lbl.setText(t("coord_format", x=x, y=y)))
        preview_bottom.addWidget(self._coord_lbl, 1)
        pg_layout.addLayout(preview_bottom)
        
        left_layout.addWidget(preview_group, 1)
        left.setMinimumWidth(260)
        splitter.addWidget(left)
        
        self._stack = QStackedWidget()
        splitter.addWidget(self._stack)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)
        right_layout.addWidget(splitter, 5)

        # ── Log ──────────────────────────────────────────────────────
        log_box = QGroupBox(t("group_activity_log"))
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(6, 4, 6, 4)
        self._log = LogWidget()
        log_layout.addWidget(self._log)
        
        log_btn_row = QHBoxLayout()
        btn_clear = QPushButton(t("btn_clear_log"))
        btn_clear.clicked.connect(self._log.clear)
        log_btn_row.addWidget(btn_clear)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)
        
        right_layout.addWidget(log_box, 1)

        root.addWidget(self._sidebar_frame)
        root.addWidget(right_content)

        self._prev_tab_idx = -1

        # ── Utils tab (first, runs independently) ────────────────────────
        self._tab_utils = UtilsTab()
        self._add_feature_tab(self._tab_utils) # index 0

        self._tab_guild = GuildRealmRaidTab()
        self._tab_guild.set_engine(self._engine)
        self._add_feature_tab(self._tab_guild) # index 1

        self._tab_personal = PersonalRealmRaidTab()
        self._tab_personal.set_engine(self._engine)
        self._add_feature_tab(self._tab_personal) # index 2

        self._tab_autoclick = AutoClickTab()
        try:
            self._preview.coord_selected.connect(self._tab_autoclick.on_preview_selected)
            self._tab_autoclick.request_selection_signal.connect(lambda: self._preview.set_selection_mode(True))
            self._preview.rect_selected.connect(self._tab_autoclick.on_rect_selected)
        except Exception:
            pass
        self._add_feature_tab(self._tab_autoclick) # index 3

        self._tab_soul = SoulTab()
        self._tab_soul.set_engine(self._engine)
        self._add_feature_tab(self._tab_soul) # index 4

        self._tab_demon_parade = AutoDemonParadeTab()
        self._tab_demon_parade.set_engine(self._engine)
        self._add_feature_tab(self._tab_demon_parade) # index 5

        self._tab_auto_duel = AutoDuelTab()
        self._tab_auto_duel.set_engine(self._engine)
        self._add_feature_tab(self._tab_auto_duel) # index 6

        self._tab_console = ScriptConsoleTab()
        self._tab_console.set_engine(self._engine)
        self._add_feature_tab(self._tab_console) # index 7

        self._tab_guide = GuideTab()
        self._add_feature_tab(self._tab_guide) # index 8

        self._coming_soon = ComingSoonTab("tab_others")
        self._add_feature_tab(self._coming_soon) # index 9

        # Pass the Utils quest-action getter to every feature tab
        for tab in self._feature_tabs:
            if hasattr(tab, "set_quest_action_fn"):
                tab.set_quest_action_fn(self._tab_utils.quest_action)

        self._sidebar_list.setCurrentRow(0)

    def _add_feature_tab(self, tab: QWidget):
        if hasattr(tab, "log_signal"):
            tab.log_signal.connect(self._on_log)
        if hasattr(tab, "started_signal"):
            tab.started_signal.connect(self._on_feature_started)
        if hasattr(tab, "stopped_signal"):
            tab.stopped_signal.connect(self._on_feature_stopped)
        
        self._stack.addWidget(tab)
        
        if hasattr(tab, "is_running"):
            self._feature_tabs.append(tab)

    # ── Auto-attach ──────────────────────────────────────────────────────

    def _on_lang_changed(self, idx):
        langs = ["vi_VN", "en_US", "fr_FR", "zh_CN"]
        if 0 <= idx < len(langs):
            get_i18n().load_language(langs[idx])

    def update_texts(self, lang=None):
        self.setWindowTitle(t("app_title"))
        self._logo_sub.setText(t("logo_subtitle"))
        self._proc_combo.setToolTip(t("tooltip_proc_combo"))
        self._btn_refresh_proc.setToolTip(t("tooltip_refresh_proc"))
        if self._capture:
            self._window_lbl.setText(t("status_connected", name=self._log_name if hasattr(self, '_log_name') else "Onmyoji"))
            self._btn_manual_attach.setText(t("btn_disconnect"))
        else:
            self._window_lbl.setText(t("status_disconnected"))
            self._btn_manual_attach.setText(t("btn_connect"))
            
        self._chk_auto.setToolTip(t("auto_connect_tooltip"))
        self._chk_auto.setText(t("auto_connect_tooltip"))
        self._chk_preview.setText(t("preview_toggle"))
        
        # Update sidebar items with localized text and icons
        if self._sidebar_list.count() >= 10:
            self._sidebar_list.item(0).setText(t("tab_utils"))
            self._sidebar_list.item(1).setText(t("tab_guild_raid"))
            self._sidebar_list.item(2).setText(t("tab_personal_raid"))
            self._sidebar_list.item(3).setText(t("tab_autoclick"))
            self._sidebar_list.item(4).setText(t("tab_soul"))
            self._sidebar_list.item(5).setText(t("tab_demon_parade"))
            self._sidebar_list.item(6).setText(t("tab_pvp"))
            self._sidebar_list.item(7).setText(t("tab_cli"))
            self._sidebar_list.item(8).setText(t("tab_guide"))
            self._sidebar_list.item(9).setText(t("tab_others"))

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
        # If auto-connect is off and user has selected a process, use that
        if not self._chk_auto.isChecked() and self._proc_combo.currentText():
            name = self._proc_combo.currentText()
        else:
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
        # Shared engine gets the capture directly; tabs also forward it for
        # AutoClickTab (which has its own internal engine).
        self._engine.set_capture(cap)
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
        
        self._conn_led.setProperty("status", "connected")
        self._conn_led.style().unpolish(self._conn_led)
        self._conn_led.style().polish(self._conn_led)
        
        self._window_lbl.setProperty("status", "connected")
        self._window_lbl.style().unpolish(self._window_lbl)
        self._window_lbl.style().polish(self._window_lbl)
        self._log_name = name; self._log.append_ok(t("msg_connected", name=name))

    def _do_detach(self, silent=False):
        self._capture_worker.set_capture(None)
        self._capture = None
        self._engine.set_capture(None)
        for tab in self._feature_tabs:
            tab.set_capture(None)
        self._preview.clear()
        self._preview.setText(t("status_disconnected").upper())
        self._btn_manual_attach.setText(t("btn_connect"))
        self._window_lbl.setText(t("status_disconnected"))
        
        self._conn_led.setProperty("status", "disconnected")
        self._conn_led.style().unpolish(self._conn_led)
        self._conn_led.style().polish(self._conn_led)
        
        self._window_lbl.setProperty("status", "disconnected")
        self._window_lbl.style().unpolish(self._window_lbl)
        self._window_lbl.style().polish(self._window_lbl)
        if not silent:
            self._log.append_info(t("msg_disconnected"))

    def _on_auto_toggle(self, state):
        auto_on = (state == Qt.CheckState.Checked.value or state == Qt.CheckState.Checked)
        if auto_on:
            self._auto_timer.start(1000)
            self._proc_combo.hide()
            self._btn_refresh_proc.hide()
            self._log.append_info(t("msg_auto_connect_on"))
        else:
            self._auto_timer.stop()
            self._refresh_proc_list()
            self._proc_combo.show()
            self._btn_refresh_proc.show()
            self._log.append_info(t("msg_auto_connect_off"))

    def _refresh_proc_list(self):
        """Populate the process dropdown with all visible window titles."""
        current = self._proc_combo.currentText()
        titles = list_all_windows()
        self._proc_combo.blockSignals(True)
        self._proc_combo.clear()
        self._proc_combo.addItems(titles)
        # Restore previous selection if still present
        idx = self._proc_combo.findText(current)
        if idx >= 0:
            self._proc_combo.setCurrentIndex(idx)
        self._proc_combo.blockSignals(False)

    # ── Frame / Feature callbacks ─────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray):
        self._preview.update_frame(frame)
        curr_tab = self._stack.currentWidget()
        for tab in self._feature_tabs:
            if tab == curr_tab or tab.is_running():
                tab.set_last_frame(frame)

    def _on_tab_changed(self, index: int):
        if index == -1:
            return
        if self._prev_tab_idx != -1:
            prev_tab = self._stack.widget(self._prev_tab_idx)
            if prev_tab and hasattr(prev_tab, "on_deactivated"):
                prev_tab.on_deactivated()
        
        self._stack.setCurrentIndex(index)
        curr_tab = self._stack.widget(index)
        if curr_tab and hasattr(curr_tab, "on_activated"):
            curr_tab.on_activated()
        
        self._prev_tab_idx = index

    def _on_feature_started(self):
        # Khoá các tab khác ko cho bấm Start khi đang chạy
        sender = self.sender()
        for tab in self._feature_tabs:
            if tab is not sender and hasattr(tab, "_btn_start"):
                tab._btn_start.setEnabled(False)

    def _on_feature_stopped(self):
        for tab in self._feature_tabs:
            if hasattr(tab, "_btn_start"):
                tab._btn_start.setEnabled(True)

    def _on_log(self, msg: str):
        self._log.append_log(msg)

    # _restore_window removed

    # ── Cleanup ───────────────────────────────────────────────────────────

    def closeEvent(self, event):
        for tab in self._feature_tabs:
            if tab.is_running():
                tab._stop()
        self._capture_worker.stop()
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    

    app.setStyleSheet(APP_STYLE)
    win = ToolsWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
