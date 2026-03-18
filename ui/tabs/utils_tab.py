from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox
)
from PyQt6.QtCore import Qt

from i18n import t, get_i18n


class UtilsTab(QWidget):
    """Utils tab — standalone utilities that can run alongside any feature."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False
        self._build_ui()
        get_i18n().language_changed.connect(self.update_texts)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._header = QLabel(t("tab_utils"))
        self._header.setObjectName("feature_header")
        layout.addWidget(self._header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Wanted quest action
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

        self._wip_lbl = QLabel(t("lbl_utils_wip"))
        self._wip_lbl.setObjectName("feature_desc")
        self._wip_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wip_lbl.setWordWrap(True)
        layout.addWidget(self._wip_lbl)

        layout.addStretch()

    def update_texts(self, lang=None):
        self._header.setText(t("tab_utils"))
        self._quest_lbl.setText(t("lbl_quest_action"))
        cur = self._quest_combo.currentIndex()
        self._quest_combo.blockSignals(True)
        self._quest_combo.setItemText(0, t("quest_accept"))
        self._quest_combo.setItemText(1, t("quest_decline"))
        self._quest_combo.setCurrentIndex(cur)
        self._quest_combo.blockSignals(False)
        self._wip_lbl.setText(t("lbl_utils_wip"))

    def quest_action(self) -> str:
        # Return the canonical English value based on index, not display text
        return "Accept" if self._quest_combo.currentIndex() == 0 else "Decline"

    def on_activated(self):
        self._active = True

    def on_deactivated(self):
        self._active = False

    def is_running(self) -> bool:
        return False

    def set_capture(self, cap):
        pass

    def set_last_frame(self, frame):
        pass
