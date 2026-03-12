DARK_STYLE = """
QWidget {
    background-color:#252526; color:#cccccc;
    font-family:"Segoe UI","SF Pro Text",Arial,sans-serif; font-size:11px;
}
QMainWindow,QDialog { background-color:#1e1e1e; }
QGroupBox {
    border:1px solid #3a3a3a; border-radius:5px;
    margin-top:10px; padding:6px 4px 4px 4px;
    font-weight:bold; color:#8ab4e8; font-size:11px;
}
QGroupBox::title { subcontrol-origin:margin; subcontrol-position:top left;
    left:8px; padding:0 4px; }
QSlider::groove:horizontal { height:4px; background:#3c3c3c; border-radius:2px; }
QSlider::handle:horizontal {
    background:#4a90d9; border:1px solid #3a78bd;
    width:14px; height:14px; margin:-5px 0; border-radius:7px;
}
QSlider::handle:horizontal:hover  { background:#5aa0e8; }
QSlider::sub-page:horizontal      { background:#2a5f9e; border-radius:2px; }
QSlider::groove:horizontal:disabled  { background:#2a2a2a; }
QSlider::handle:horizontal:disabled  { background:#404040; border-color:#383838; }
QPushButton {
    background-color:#3c3c3c; border:1px solid #505050;
    border-radius:4px; padding:5px 14px; color:#cccccc; min-height:22px;
}
QPushButton:hover   { background-color:#4a4a4a; border-color:#606060; }
QPushButton:pressed { background-color:#2a2a2a; }
QPushButton:disabled{ background-color:#2e2e2e; color:#666; border-color:#383838; }
QPushButton#export_btn {
    background-color:#1e5c1e; border:1px solid #2a7a2a;
    color:#88ff88; font-weight:bold; font-size:12px;
    min-height:30px; padding:6px 20px;
}
QPushButton#export_btn:hover   { background-color:#256025; }
QPushButton#export_btn:pressed { background-color:#143314; }
QPushButton#export_btn:disabled{ background-color:#1a2e1a; color:#446644; }
QPushButton#reset_btn { background-color:#3a2828; border-color:#583838; color:#ffaaaa; }
QPushButton#reset_btn:hover { background-color:#4a3030; }
QPushButton#zoom_btn {
    background-color:#2a2a3a; border:1px solid #404060;
    color:#aaaaee; padding:2px 8px; min-height:18px; font-size:13px;
}
QPushButton#zoom_btn:hover { background-color:#333350; }
QComboBox {
    background-color:#333333; border:1px solid #505050;
    border-radius:4px; padding:4px 8px; min-height:22px;
}
QComboBox::drop-down { border:none; width:20px; }
QComboBox QAbstractItemView {
    background-color:#2d2d2d; selection-background-color:#3a6ea8;
    border:1px solid #505050;
}
QDoubleSpinBox {
    background-color:#2d2d2d; border:1px solid #484848;
    border-radius:3px; padding:2px 4px;
    min-width:54px; max-width:64px; min-height:20px;
}
QDoubleSpinBox:disabled { color:#555; background-color:#252525; }
QCheckBox::indicator {
    width:14px; height:14px; border:1px solid #555;
    border-radius:3px; background-color:#2d2d2d;
}
QCheckBox::indicator:checked { background-color:#2a5f9e; border-color:#4a90d9; }
QLabel#frame_label  { font-size:18px; font-weight:bold; color:#5bb0ff;
    qproperty-alignment:AlignCenter; }
QLabel#status_label { color:#aaaaaa; font-size:10px; padding:2px 6px; }
QLabel#section_title{ font-size:10px; color:#888888; font-weight:bold;
    letter-spacing:1px; padding:4px 0 2px 0; }
QScrollArea { border:none; }
QScrollBar:vertical { background:#1e1e1e; width:8px; border-radius:4px; }
QScrollBar::handle:vertical { background:#484848; border-radius:4px; min-height:20px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QFrame#separator { background-color:#3a3a3a; max-height:1px; }
QLineEdit {
    background-color:#2d2d2d; border:1px solid #484848;
    border-radius:3px; padding:3px 6px; color:#cccccc;
}
"""
