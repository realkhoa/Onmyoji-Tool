from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from i18n import t, get_i18n

class ComingSoonTab(QWidget):
    def __init__(self, feature_key: str, parent=None):
        super().__init__(parent)
        self._feature_key = feature_key
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("🚧")
        icon.setObjectName("coming_soon_icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        self._lbl = QLabel()
        self._lbl.setObjectName("coming_soon_text")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lbl)
        self.update_texts()
        get_i18n().language_changed.connect(self.update_texts)

    def update_texts(self, lang=None):
        self._lbl.setText(t("lbl_coming_soon", feature=t(self._feature_key)))

