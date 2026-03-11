from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from i18n import t

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
