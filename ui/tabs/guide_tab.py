from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl

class GuideTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Thêm trình duyệt nhúng web guide
        self.browser = QWebEngineView()
        self._url = "https://guidemyoji.com/summon-room-patterns/"
        layout.addWidget(self.browser)
        self._loaded = False

    def on_activated(self):
        if not self._loaded:
            self.browser.setUrl(QUrl(self._url))
            self._loaded = True

    def on_deactivated(self):
        # Stop and clear browser to save memory
        self.browser.stop()
        self.browser.setUrl(QUrl("about:blank"))
        self._loaded = False
