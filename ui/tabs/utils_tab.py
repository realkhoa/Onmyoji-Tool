import subprocess
import win32gui

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QGroupBox, QPushButton, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal

from i18n import t, get_i18n


class UtilsTab(QWidget):
    """Utils tab — standalone utilities that can run alongside any feature."""

    log_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self._hwnd: int | None = None
        self._build_ui()
        get_i18n().language_changed.connect(self.update_texts)

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        self._header = QLabel(t("tab_utils"))
        self._header.setObjectName("feature_header")
        layout.addWidget(self._header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # ── Wanted quest action ─────────────────────────────────────────
        quest_row = QHBoxLayout()
        self._quest_lbl = QLabel(t("lbl_quest_action"))
        quest_row.addWidget(self._quest_lbl)
        self._quest_combo = QComboBox()
        self._quest_combo.addItems([t("quest_accept"), t("quest_decline")])
        quest_row.addWidget(self._quest_combo)
        quest_row.addStretch()
        layout.addLayout(quest_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        # ── Steam ────────────────────────────────────────────────────────
        self._grp_steam = QGroupBox(t("grp_steam"))
        steam_layout = QHBoxLayout(self._grp_steam)
        steam_layout.setContentsMargins(12, 8, 12, 8)

        self._btn_kill_steam = QPushButton(t("btn_kill_steam"))
        self._btn_kill_steam.setToolTip(t("tooltip_kill_steam"))
        self._btn_kill_steam.setObjectName("btn_danger")
        self._btn_kill_steam.clicked.connect(self._kill_steam)
        steam_layout.addWidget(self._btn_kill_steam)
        steam_layout.addStretch()

        layout.addWidget(self._grp_steam)

        # ── Window Rename ────────────────────────────────────────────────
        self._grp_rename = QGroupBox(t("grp_win_rename"))
        rename_layout = QHBoxLayout(self._grp_rename)
        rename_layout.setContentsMargins(12, 8, 12, 8)

        self._lbl_new_title = QLabel(t("lbl_new_title"))
        rename_layout.addWidget(self._lbl_new_title)

        self._edit_title = QLineEdit()
        self._edit_title.setPlaceholderText("陰陽師Onmyoji")
        self._edit_title.setMinimumWidth(200)
        rename_layout.addWidget(self._edit_title, 1)

        self._btn_rename = QPushButton(t("btn_rename_win"))
        self._btn_rename.setToolTip(t("tooltip_rename_win"))
        self._btn_rename.clicked.connect(self._rename_window)
        rename_layout.addWidget(self._btn_rename)

        layout.addWidget(self._grp_rename)

        layout.addStretch()

    # ── i18n ────────────────────────────────────────────────────────────────

    def update_texts(self, lang=None):
        self._header.setText(t("tab_utils"))
        self._quest_lbl.setText(t("lbl_quest_action"))
        cur = self._quest_combo.currentIndex()
        self._quest_combo.blockSignals(True)
        self._quest_combo.setItemText(0, t("quest_accept"))
        self._quest_combo.setItemText(1, t("quest_decline"))
        self._quest_combo.setCurrentIndex(cur)
        self._quest_combo.blockSignals(False)
        self._grp_steam.setTitle(t("grp_steam"))
        self._btn_kill_steam.setText(t("btn_kill_steam"))
        self._btn_kill_steam.setToolTip(t("tooltip_kill_steam"))
        self._grp_rename.setTitle(t("grp_win_rename"))
        self._lbl_new_title.setText(t("lbl_new_title"))
        self._btn_rename.setText(t("btn_rename_win"))
        self._btn_rename.setToolTip(t("tooltip_rename_win"))

    # ── Actions ──────────────────────────────────────────────────────────────

    def _kill_steam(self):
        """Terminate all steam.exe processes."""
        try:
            import psutil  # optional fast path
            killed = False
            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] and proc.info["name"].lower() == "steam.exe":
                    proc.kill()
                    killed = True
            if killed:
                self.log_signal.emit(t("msg_steam_killed"))
            else:
                self.log_signal.emit(t("msg_steam_not_found"))
        except ImportError:
            # Fallback: taskkill
            try:
                result = subprocess.run(
                    ["taskkill", "/f", "/im", "steam.exe"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    self.log_signal.emit(t("msg_steam_killed"))
                else:
                    self.log_signal.emit(t("msg_steam_not_found"))
            except Exception as e:
                self.log_signal.emit(t("msg_steam_kill_error", error=e))
        except Exception as e:
            self.log_signal.emit(t("msg_steam_kill_error", error=e))

    def _rename_window(self):
        """Change the title of the currently attached game window."""
        if not self._hwnd:
            self.log_signal.emit(t("msg_rename_no_window"))
            return
        new_title = self._edit_title.text().strip()
        if not new_title:
            return
        try:
            win32gui.SetWindowText(self._hwnd, new_title)
            self.log_signal.emit(t("msg_renamed_ok", title=new_title))
        except Exception as e:
            self.log_signal.emit(f"[ERROR] SetWindowText: {e}")

    # ── Public API ───────────────────────────────────────────────────────────

    def quest_action(self) -> str:
        return "Accept" if self._quest_combo.currentIndex() == 0 else "Decline"

    def set_capture(self, cap):
        """Track the HWND of the attached window."""
        self._hwnd = cap.hwnd if cap is not None else None

    def on_activated(self):
        self._active = True

    def on_deactivated(self):
        self._active = False

    def is_running(self) -> bool:
        return False

    def set_last_frame(self, frame):
        pass
