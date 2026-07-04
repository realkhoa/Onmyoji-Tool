import re
from PyQt6.QtWidgets import QWidget, QPlainTextEdit, QTextEdit
from PyQt6.QtCore import QSize, QRect, Qt, QTimer, QStringListModel
from PyQt6.QtGui import QPainter, QColor, QTextFormat

from ui.comps.editor_enhancements import (
    DSLHighlighter,
    DSLCompleter,
    ImagePreviewPopup,
    parse_symbols,
    get_image_files,
    ALL_STATIC_KEYWORDS,
    IMAGES_DIR
)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self._editor.lineNumberAreaPaintEvent(event)


class LineNumberEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        
        # Theme colors
        self._ln_bg = QColor("#1e1e1e")
        self._ln_text = QColor("#b3b3b3")
        self._line_hi = QColor("#2c2c2c")
        
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        
        # Editor enhancements initialization
        self._completer = None
        self._hovered_file = None
        self._hover_pos = None
        self._symbol_cache = []
        
        self.highlighter = DSLHighlighter(self.document(), is_dark=True)
        self.preview_popup = ImagePreviewPopup(self)
        
        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self.show_hover_preview)
        
        self.verticalScrollBar().valueChanged.connect(self.preview_popup.hide)
        self.verticalScrollBar().valueChanged.connect(self._hover_timer.stop)
        self.horizontalScrollBar().valueChanged.connect(self.preview_popup.hide)
        self.horizontalScrollBar().valueChanged.connect(self._hover_timer.stop)
        
        self._symbol_timer = QTimer(self)
        self._symbol_timer.setSingleShot(True)
        self._symbol_timer.timeout.connect(self.refresh_symbols)
        self.textChanged.connect(self.on_text_changed)
        
        self.viewport().setMouseTracking(True)
        self._image_cache = get_image_files()
        
        completer = DSLCompleter(self, is_dark=True)
        self.setCompleter(completer)
        
        self.set_theme(True) # Default dark

    def setCompleter(self, completer):
        if self._completer:
            try:
                self._completer.activated.disconnect(self.insertCompletion)
            except (TypeError, RuntimeError):
                pass
        self._completer = completer
        if not completer:
            return
        completer.setWidget(self)
        completer.activated.connect(self.insertCompletion)

    def insertCompletion(self, completion):
        if self._completer.widget() is not self:
            return
        tc = self.textCursor()
        prefix = self.textUnderCursor()
        tc.movePosition(tc.MoveOperation.Left, tc.MoveMode.KeepAnchor, len(prefix))
        tc.insertText(completion)
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        block_text = tc.block().text()
        pos_in_block = tc.positionInBlock()
        # Find prefix containing word characters, forward slash, period, or starting quotes
        match = re.search(r'[\'"]?[\$a-zA-Z0-9_\/.]*$', block_text[:pos_in_block])
        if match:
            return match.group(0)
        return ""

    def on_text_changed(self):
        self._symbol_timer.start(300)

    def refresh_symbols(self):
        new_symbols = parse_symbols(self.toPlainText())
        if set(new_symbols) != set(self._symbol_cache):
            self._symbol_cache = new_symbols
            self.updateCompleterModel()

    def updateCompleterModel(self):
        if not self._completer:
            return
        
        symbols = self._symbol_cache
        quoted_images = []
        for img in self._image_cache:
            quoted_images.append(img)          # e.g. home_explore.png
            quoted_images.append(f'"{img}"')    # e.g. "home_explore.png"
            quoted_images.append(f"'{img}'")    # e.g. 'home_explore.png'
        all_completions = sorted(list(
            ALL_STATIC_KEYWORDS.union(symbols).union(quoted_images)
        ))
        
        model = self._completer.model()
        if not isinstance(model, QStringListModel):
            model = QStringListModel(self._completer)
            self._completer.setModel(model)
        model.setStringList(all_completions)

    def keyPressEvent(self, e):
        if self._completer and self._completer.popup().isVisible():
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                e.ignore()
                return
        
        is_shortcut = (e.modifiers() & Qt.KeyboardModifier.ControlModifier) and e.key() == Qt.Key.Key_Space
        
        if not is_shortcut:
            super().keyPressEvent(e)
            
        if not self._completer:
            return
            
        is_visible = self._completer.popup().isVisible()
        is_backspace = e.key() == Qt.Key.Key_Backspace
        is_trigger_char = bool(e.text() and (e.text().isalnum() or e.text() in ('_', '"', "'", '/', '.', '$')))
        
        should_trigger = is_shortcut or (is_visible and is_backspace) or is_trigger_char
        
        if not should_trigger:
            self._completer.popup().hide()
            return
            
        completion_prefix = self.textUnderCursor()
        
        has_modifier = (e.modifiers() != Qt.KeyboardModifier.NoModifier) and not is_shortcut
        if not is_shortcut and not is_backspace and (has_modifier or not e.text() or len(completion_prefix) < 1):
            self._completer.popup().hide()
            return
            
        if completion_prefix != self._completer.completionPrefix():
            self._completer.setCompletionPrefix(completion_prefix)
            self._completer.popup().setCurrentIndex(self._completer.completionModel().index(0, 0))
            
        cr = self.cursorRect()
        cr.setWidth(self._completer.popup().sizeHintForColumn(0) + self._completer.popup().verticalScrollBar().sizeHint().width())
        self._completer.complete(cr)

    def get_image_token_at_cursor(self, cursor):
        text = cursor.block().text()
        index = cursor.positionInBlock()
        
        matches = re.finditer(r'"([^"\\]*(?:\\.[^"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'', text)
        for match in matches:
            start = match.start()
            end = match.end()
            if start <= index <= end:
                filename = match.group(1) or match.group(2)
                if filename:
                    filename_lower = filename.lower()
                    for cached in self._image_cache:
                        if cached.lower() == filename_lower:
                            return cached
        return None

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        cursor = self.cursorForPosition(pos)
        filename = self.get_image_token_at_cursor(cursor)
        
        if filename:
            if filename != self._hovered_file:
                self._hover_timer.stop()
                self.preview_popup.hide()
                self._hovered_file = filename
                self._hover_pos = event.globalPosition().toPoint()
                self._hover_timer.start(400)
        else:
            if self._hovered_file is not None:
                self._hover_timer.stop()
                self._hovered_file = None
                self._hover_pos = None
                self.preview_popup.hide()
                
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_timer.stop()
        self._hovered_file = None
        self._hover_pos = None
        self.preview_popup.hide()
        super().leaveEvent(event)

    def hideEvent(self, event):
        self._hover_timer.stop()
        self.preview_popup.hide()
        super().hideEvent(event)

    def focusOutEvent(self, event):
        self._hover_timer.stop()
        self.preview_popup.hide()
        super().focusOutEvent(event)

    def showEvent(self, event):
        self._image_cache = get_image_files()
        super().showEvent(event)
        self.updateCompleterModel()

    def show_hover_preview(self):
        self._hover_timer.stop()
        if not self._hovered_file:
            return
            
        full_path = IMAGES_DIR / self._hovered_file
        if full_path.exists():
            if self.preview_popup.show_image(full_path, self._hovered_file):
                if self._hover_pos:
                    screen = self.screen().geometry()
                    popup_w = self.preview_popup.width()
                    popup_h = self.preview_popup.height()
                    new_x = self._hover_pos.x() + 15
                    new_y = self._hover_pos.y() + 15
                    
                    if new_x + popup_w > screen.right():
                        new_x = self._hover_pos.x() - popup_w - 15
                    if new_y + popup_h > screen.bottom():
                        new_y = self._hover_pos.y() - popup_h - 15
                        
                    new_x = max(screen.left(), new_x)
                    new_y = max(screen.top(), new_y)
                    
                    self.preview_popup.move(new_x, new_y)
                    self.preview_popup.show()

    def lineNumberAreaWidth(self):
        digits = len(str(self.blockCount()))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(
                0, rect.y(), self.lineNumberArea.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._hover_timer.stop()
        self.preview_popup.hide()
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), self._ln_bg)
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(self._ln_text)
                painter.drawText(
                    0,
                    int(top),
                    self.lineNumberArea.width() - 2,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self._line_hi)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def set_theme(self, is_dark: bool):
        if is_dark:
            self._ln_bg = QColor("#1e1e1e")
            self._ln_text = QColor("#b3b3b3")
            self._line_hi = QColor("#2c2c2c")
            self.setProperty("theme", "dark")
        else:
            self._ln_bg = QColor("#f0f0f0")
            self._ln_text = QColor("#999999")
            self._line_hi = QColor("#e8e8e8")
            self.setProperty("theme", "light")
        
        self.style().unpolish(self)
        self.style().polish(self)
        self.highlightCurrentLine()
        self.lineNumberArea.update()

        # Update enhancements themes
        if hasattr(self, 'highlighter') and self.highlighter:
            self.highlighter.is_dark = is_dark
            self.highlighter.update_colors()
            self.highlighter.setup_rules()
            self.highlighter.rehighlight()
            
        if hasattr(self, '_completer') and self._completer:
            self._completer.is_dark = is_dark
            self._completer.update_style()
