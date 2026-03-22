APP_STYLE = """
QPushButton          { min-width: 150px; min-height: 50px; }
QPushButton#btn_icon { min-width: 0px;   min-height: 0px;  }
QPushButton#btn_danger {
    min-width: 120px; min-height: 34px;
    background-color: #8b1a1a;
    color: #ffdddd;
    border: 1px solid #c0392b;
    border-radius: 6px;
    font-weight: bold;
}
QPushButton#btn_danger:hover { background-color: #a93226; }
QPushButton#btn_danger:pressed { background-color: #6e1010; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { min-width: 200px; min-height: 30px; }
"""
