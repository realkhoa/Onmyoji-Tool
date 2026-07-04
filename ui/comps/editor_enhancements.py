import os
import re
import sys
from pathlib import Path
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QCompleter
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QPixmap

from i18n import t

# Path resolution
BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
IMAGES_DIR = BASE_DIR / "images"

# Keywords definitions
DSL_FLOW_KEYWORDS = {
    "loop", "forever", "do", "until", "break", "continue", "if", "elif",
    "else", "exists", "exists_exact", "goto", "wait", "wait_random",
    "resize", "log", "function", "return", "set", "binding", "boolean",
    "slider", "number", "string"
}

DSL_ACTION_KEYWORDS = {
    "click", "rclick", "dclick", "move", "drag", "scroll", "key", "type",
    "find_and_click", "wait_for", "wait_and_click", "count", "drag_to",
    "drag_image", "drag_offset", "find_and_click_largest_shiki",
    "throw_at_largest_shiki"
}

BUILTIN_FUNCTIONS = {
    "rand", "randint", "min", "max", "abs"
}

ALL_STATIC_KEYWORDS = DSL_FLOW_KEYWORDS.union(DSL_ACTION_KEYWORDS).union(BUILTIN_FUNCTIONS)


def get_image_files():
    images = []
    if not IMAGES_DIR.exists():
        return images
    for root, dirs, files in os.walk(IMAGES_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                rel_path = os.path.relpath(os.path.join(root, file), IMAGES_DIR)
                rel_path = rel_path.replace("\\", "/")
                images.append(rel_path)
    return images


def parse_symbols(text):
    # Strip comments and string literals in a single pass to avoid overlapping matching bugs
    pattern = r'#[^\n]*|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\''
    text_clean = re.sub(pattern, '', text)
    
    symbols = set()
    funcs = re.findall(r'\bfunction\s+([a-zA-Z_]\w*)', text_clean, re.IGNORECASE)
    symbols.update(funcs)
    
    vars1 = re.findall(r'\bset\s+([a-zA-Z_]\w*)', text_clean, re.IGNORECASE)
    vars2 = re.findall(r'\b([a-zA-Z_]\w*)\s*[-+*/%]?=(?!=)', text_clean)
    symbols.update(vars1)
    symbols.update(vars2)
    
    labels = re.findall(r'\b([a-zA-Z_]\w*)\s*:', text_clean)
    symbols.update(labels)
    
    bindings = re.findall(r'\bbinding\s+(\$[a-zA-Z_]\w*)', text_clean, re.IGNORECASE)
    symbols.update(bindings)
    
    # Filter out empty or keywords
    symbols = {s for s in symbols if s and s.lower() not in ALL_STATIC_KEYWORDS}
    return list(symbols)


class DSLHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None, is_dark=True):
        super().__init__(parent)
        self.is_dark = is_dark
        self.rules = []
        self.setup_formats()
        self.setup_rules()

    def setup_formats(self):
        self.comment_format = QTextCharFormat()
        self.comment_format.setFontItalic(True)
        
        self.flow_format = QTextCharFormat()
        self.flow_format.setFontWeight(QFont.Weight.Bold)
        
        self.action_format = QTextCharFormat()
        self.action_format.setFontWeight(QFont.Weight.Bold)
        
        self.string_format = QTextCharFormat()
        self.label_format = QTextCharFormat()
        self.number_format = QTextCharFormat()
        self.func_format = QTextCharFormat()
        self.var_format = QTextCharFormat()
        
        self.update_colors()

    def update_colors(self):
        if self.is_dark:
            self.comment_format.setForeground(QColor("#767676"))
            self.flow_format.setForeground(QColor("#c084fc"))      # Purple
            self.action_format.setForeground(QColor("#e11d48"))    # Crimson red
            self.string_format.setForeground(QColor("#22c55e"))    # Lime green
            self.label_format.setForeground(QColor("#f59e0b"))     # Amber
            self.number_format.setForeground(QColor("#60a5fa"))    # Sky blue
            self.func_format.setForeground(QColor("#06b6d4"))      # Cyan
            self.var_format.setForeground(QColor("#fda4af"))       # Rose pink
        else:
            self.comment_format.setForeground(QColor("#8e8e93"))
            self.flow_format.setForeground(QColor("#7c3aed"))
            self.action_format.setForeground(QColor("#be123c"))
            self.string_format.setForeground(QColor("#16a34a"))
            self.label_format.setForeground(QColor("#d97706"))
            self.number_format.setForeground(QColor("#2563eb"))
            self.func_format.setForeground(QColor("#0891b2"))
            self.var_format.setForeground(QColor("#db2777"))

    def setup_rules(self):
        self.rules.clear()
        self.tokenizer = re.compile(
            r'(?P<comment>#[^\n]*)'
            r'|(?P<string>"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')'
            r'|(?P<label>\b[a-zA-Z_]\w*(?=:))'
            r'|(?P<number>\b\d+(?:\.\d+)?\b)'
            r'|(?P<flow>\b(?:loop|forever|do|until|break|continue|if|elif|else|exists|exists_exact|goto|wait|wait_random|resize|log|function|return|set|binding|boolean|slider|number|string)\b)'
            r'|(?P<action>\b(?:click|rclick|dclick|move|drag|scroll|key|type|find_and_click|wait_for|wait_and_click|count|drag_to|drag_image|drag_offset|find_and_click_largest_shiki|throw_at_largest_shiki)\b)'
            r'|(?P<builtin>\b(?:rand|randint|min|max|abs)(?=\())'
            r'|(?P<math>\bmath\.\w+(?=\())'
            r'|(?P<variable>\$[a-zA-Z_]\w*)',
            re.IGNORECASE
        )

    def highlightBlock(self, text):
        for match in self.tokenizer.finditer(text):
            group_name = match.lastgroup
            if not group_name:
                continue
            
            if group_name == 'comment':
                fmt = self.comment_format
            elif group_name == 'string':
                fmt = self.string_format
            elif group_name == 'label':
                fmt = self.label_format
            elif group_name == 'number':
                fmt = self.number_format
            elif group_name == 'flow':
                fmt = self.flow_format
            elif group_name == 'action':
                fmt = self.action_format
            elif group_name in ('builtin', 'math'):
                fmt = self.func_format
            elif group_name == 'variable':
                fmt = self.var_format
            else:
                continue
                
            self.setFormat(match.start(), match.end() - match.start(), fmt)


class DSLCompleter(QCompleter):
    def __init__(self, parent=None, is_dark=True):
        super().__init__([], parent)
        self.is_dark = is_dark
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.update_style()

    def update_style(self):
        popup = self.popup()
        popup.setObjectName("completer_popup")
        if self.is_dark:
            popup.setStyleSheet("""
                QAbstractItemView#completer_popup {
                    background-color: #18181b;
                    border: 1px solid #27272a;
                    color: #e4e4e7;
                    selection-background-color: #be123c;
                    selection-color: #ffffff;
                    border-radius: 6px;
                    outline: 0;
                    padding: 4px;
                }
            """)
        else:
            popup.setStyleSheet("""
                QAbstractItemView#completer_popup {
                    background-color: #ffffff;
                    border: 1px solid #e4e4e7;
                    color: #18181b;
                    selection-background-color: #be123c;
                    selection-color: #ffffff;
                    border-radius: 6px;
                    outline: 0;
                    padding: 4px;
                }
            """)


class ImagePreviewPopup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setObjectName("image_preview_popup")
        self.setStyleSheet("""
            QFrame#image_preview_popup {
                background-color: #121214;
                border: 1.5px solid #be123c;
                border-radius: 8px;
            }
            QLabel {
                color: #f4f4f5;
                font-family: "Segoe UI", sans-serif;
                font-size: 11px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        
        self.img_lbl = QLabel(self)
        self.img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.img_lbl)
        
        self.info_lbl = QLabel(self)
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_lbl)
        
        self.adjustSize()
        
    def show_image(self, file_path, filename):
        pixmap = QPixmap(str(file_path))
        if pixmap.isNull():
            return False
            
        w, h = pixmap.width(), pixmap.height()
        scaled_pixmap = pixmap.scaled(
            160, 160, 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.img_lbl.setPixmap(scaled_pixmap)
        self.info_lbl.setText(t("image_preview_info", filename=filename, w=w, h=h))
        self.adjustSize()
        return True
