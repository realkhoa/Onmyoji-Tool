from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

class OthersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setTabBarAutoHide(True)
        if self.tabs.tabBar():
            self.tabs.tabBar().setDrawBase(False)
        layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_sub_tab_changed)
        self._prev_idx = -1
        self._active = False

    def add_sub_tab(self, widget, label):
        self.tabs.addTab(widget, label)

    def _on_sub_tab_changed(self, index):
        if not self._active:
            return
        if self._prev_idx != -1:
            prev = self.tabs.widget(self._prev_idx)
            if hasattr(prev, "on_deactivated"):
                prev.on_deactivated()
        curr = self.tabs.widget(index)
        if hasattr(curr, "on_activated"):
            curr.on_activated()
        self._prev_idx = index

    def on_activated(self):
        self._active = True
        curr = self.tabs.currentWidget()
        if hasattr(curr, "on_activated"):
            curr.on_activated()
        self._prev_idx = self.tabs.currentIndex()

    def on_deactivated(self):
        self._active = False
        curr = self.tabs.currentWidget()
        if hasattr(curr, "on_deactivated"):
            curr.on_deactivated()
