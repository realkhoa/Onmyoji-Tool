import cv2
import numpy as np
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from i18n import t

class PreviewLabel(QLabel):
    coord_changed = pyqtSignal(int, int)
    coord_selected = pyqtSignal(int, int)
    rect_selected = pyqtSignal(int, int, int, int)


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

        # For rect selection
        self._selection_mode = False
        self._selecting_rect = False
        self._rect_start: QPoint | None = None
        self._rect_current: QPoint | None = None

    def set_selection_mode(self, mode: bool):
        self._selection_mode = mode
        if not mode:
            self._selecting_rect = False
            self._rect_start = None
            self._rect_current = None
            self.update()


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

    def mousePressEvent(self, event):
        if self._selection_mode and event.button() == Qt.MouseButton.LeftButton:
            self._selecting_rect = True
            self._rect_start = event.position().toPoint()
            self._rect_current = self._rect_start
            self.update()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._selecting_rect and self._rect_start:
            self._rect_current = event.position().toPoint()
            self.update()

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

    def mouseReleaseEvent(self, event):
        if self._selecting_rect and event.button() == Qt.MouseButton.LeftButton:
            self._selecting_rect = False
            if self._rect_start and self._rect_current:
                p1 = self._to_game(self._rect_start)
                p2 = self._to_game(self._rect_current)
                if p1 and p2:
                    x1, y1 = p1
                    x2, y2 = p2
                    gx, gy = min(x1, x2), min(y1, y2)
                    gw, gh = abs(x2 - x1), abs(y2 - y1)
                    if gw > 0 and gh > 0:
                        self.rect_selected.emit(gx, gy, gw, gh)
            
            self._selection_mode = False
            self._rect_start = None
            self._rect_current = None
            self.update()
            return

        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._selecting_rect and self._rect_start and self._rect_current:
            painter = QPainter(self)
            pen = QPen(QColor(0, 255, 0, 200), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            x = min(self._rect_start.x(), self._rect_current.x())
            y = min(self._rect_start.y(), self._rect_current.y())
            w = abs(self._rect_start.x() - self._rect_current.x())
            h = abs(self._rect_start.y() - self._rect_current.y())
            
            painter.drawRect(x, y, w, h)
            # draw a translucent fill
            painter.fillRect(x, y, w, h, QColor(0, 255, 0, 40))

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
