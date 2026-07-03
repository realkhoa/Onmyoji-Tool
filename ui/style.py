APP_STYLE = """
QMainWindow {
    background-color: #0d0d0f;
}

QWidget {
    color: #f4f4f5;
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QFrame#sidebar_frame {
    background-color: #121214;
    border-right: 1px solid #1f1f23;
}

QLabel#sidebar_title {
    font-size: 18px;
    font-weight: bold;
    color: #e11d48;
}

QLabel#sidebar_subtitle {
    font-size: 10px;
    color: #71717a;
}

QListWidget#sidebar_list {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget#sidebar_list::item {
    height: 38px;
    padding-left: 8px;
    color: #a1a1aa;
    border-radius: 6px;
    margin: 2px 6px;
}

QListWidget#sidebar_list::item:hover {
    background-color: #1c1917;
    color: #f4f4f5;
}

QListWidget#sidebar_list::item:selected {
    background-color: #be123c;
    color: #ffffff;
    font-weight: bold;
}

QGroupBox {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 2px;
    color: #e4e4e7;
    font-weight: bold;
}

QPushButton {
    background-color: #18181b;
    border: 1px solid #27272a;
    color: #e4e4e7;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 26px;
}

QPushButton:hover {
    background-color: #27272a;
    border-color: #3f3f46;
}

QPushButton:pressed {
    background-color: #09090b;
}

QPushButton#btn_success {
    background-color: #be123c;
    border: 1px solid #e11d48;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#btn_success:hover {
    background-color: #e11d48;
    border-color: #fda4af;
}

QPushButton#btn_success:pressed {
    background-color: #9f1239;
}

QPushButton#btn_danger {
    background-color: #1c1917;
    border: 1px solid #be123c;
    color: #f43f5e;
    font-weight: bold;
}

QPushButton#btn_danger:hover {
    background-color: #be123c;
    color: #ffffff;
}

QPushButton#btn_danger:pressed {
    background-color: #9f1239;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
    color: #e4e4e7;
    padding: 4px 8px;
    min-height: 26px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #be123c;
}

QComboBox::drop-down {
    border: none;
}

QScrollBar:vertical {
    background-color: #0d0d0f;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #27272a;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #be123c;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QSplitter::handle {
    background-color: #18181b;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QLabel#conn_status_led {
    min-width: 8px;
    min-height: 8px;
    max-width: 8px;
    max-height: 8px;
    border-radius: 4px;
    margin-right: 6px;
}
QLabel#conn_status_led[status="connected"] {
    background-color: #22c55e;
}
QLabel#conn_status_led[status="disconnected"] {
    background-color: #71717a;
}
"""

