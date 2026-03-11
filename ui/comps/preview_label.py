import cv2
import numpy as np
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
from i18n import t

class PreviewLabel(QLabel):
    coord_changed = pyqtSignal(int, int)
    coord_selected = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 158)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)
        self.setText(t("status_disconnected").upper())
        self._pixmap: QPixmap | None = None
        self._frame_w = self._frame_h = 0

        self._coord_label = QLabel(self)
        self._coord_label.hide()

    def update_frame(self, frame: np.ndarray):
        if self.text():
            self.setText("")
        h, w = frame.shape[:2]
        self._frame_w, self._frame_h = w, h
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._rescale()

    def _rescale(self):
        if self._pixmap:
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _to_game(self, pos):
        pm = self.pixmap()
        if not pm or self._frame_w == 0:
            return None
        ox = (self.width() - pm.width()) / 2
        oy = (self.height() - pm.height()) / 2
        rx, ry = pos.x() - ox, pos.y() - oy
        if rx < 0 or ry < 0 or rx >= pm.width() or ry >= pm.height():
            return None
        return int(rx / pm.width() * self._frame_w), int(ry / pm.height() * self._frame_h)

    def mouseMoveEvent(self, event):
        coords = self._to_game(event.position())
        if coords:
            self._coord_label.setText(f"X:{coords[0]}  Y:{coords[1]}")
            self._coord_label.adjustSize()
            lx = min(int(event.position().x()) + 12, self.width() - self._coord_label.width() - 4)
            self._coord_label.move(lx, max(int(event.position().y()) - 24, 4))
            self._coord_label.show()
            self.coord_changed.emit(*coords)
        else:
            self._coord_label.hide()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        coords = self._to_game(event.position())
        if coords:
            self.coord_selected.emit(*coords)
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event):
        self._coord_label.hide()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()
