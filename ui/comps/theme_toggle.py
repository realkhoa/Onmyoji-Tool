from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QColor, QPainter

class ThemeToggle(QWidget):
    """Custom animated modern toggle switch with internal icons."""
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, width=58, height=30):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._checked = False
        self._thumb_pos = 4.0
        self._anim = None
        
        # Colors
        self._bg_off = QColor("#555555")
        self._bg_on = QColor("#00bcd4")
        self._thumb_color = QColor("#ffffff")

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self._animate(checked)
        self.toggled.emit(checked)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def _animate(self, checked):
        target = float(self.width() - self.height() + 4) if checked else 4.0
        self._anim = QPropertyAnimation(self, b"thumb_pos")
        self._anim.setDuration(250)
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.start()

    @pyqtProperty(float)
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background pill
        bg_col = self._bg_on if self._checked else self._bg_off
        p.setBrush(bg_col)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), self.height()/2, self.height()/2)
        
        # Draw thumb circle
        thumb_size = self.height() - 8
        p.setBrush(self._thumb_color)
        p.drawEllipse(QRect(int(self._thumb_pos), 4, thumb_size, thumb_size))
        
        # Draw icon inside thumb
        p.setPen(QColor("#333333"))
        font = p.font()
        font.setPixelSize(int(thumb_size * 0.7))
        p.setFont(font)
        
        icon = "🌙" if self._checked else "☀️"
        p.drawText(QRect(int(self._thumb_pos), 4, thumb_size, thumb_size), Qt.AlignmentFlag.AlignCenter, icon)
        p.end()
