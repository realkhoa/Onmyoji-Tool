"""
ui_tools.py – Giao diện thân thiện, mỗi tab là 1 tính năng game.
Tự động tìm & attach cửa sổ Onmyoji khi khởi động.
"""

import sys
import os
import win32gui
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QSplitter, QCheckBox, QFrame, 
    QSizePolicy, QComboBox, QTabBar, QScrollArea, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer
from qt_material import apply_stylesheet, build_stylesheet

from i18n import t, get_i18n
from ui.comps.theme_toggle import ThemeToggle
from ui.comps.preview_label import PreviewLabel
from ui.comps.log_widget import LogWidget
from helpers.capture import CaptureWorker
from helpers.window import find_game_window
from screenshot import WindowCapture

from ui.tabs.feature_tab import FeatureTab
from ui.tabs.guild_realm_raid import GuildRealmRaidTab
from ui.tabs.personal_realm_raid import PersonalRealmRaidTab
from ui.tabs.auto_demon_parade import AutoDemonParadeTab
from ui.tabs.auto_duel import AutoDuelTab
from ui.tabs.script_console_tab import ScriptConsoleTab
from ui.tabs.auto_click_tab import AutoClickTab
from ui.tabs.soul_tab import SoulTab
from ui.tabs.guide_tab import GuideTab
from ui.tabs.others_tab import OthersTab
from ui.tabs.coming_soon_tab import ComingSoonTab

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
