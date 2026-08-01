"""Dark glassy Qt stylesheet with an icy-cyan accent (Smooth Client vibe)."""

ACCENT = "#38e1ff"
ACCENT_DIM = "#1f9fb8"
BG = "#0d1017"
PANEL = "#161b24"
PANEL_2 = "#1d2431"
TEXT = "#e6edf3"
MUTED = "#8b98a9"

QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
QLabel#title {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#accent {{ color: {ACCENT}; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}

QFrame#card, QFrame#panel {{
    background: {PANEL};
    border: 1px solid #232c3a;
    border-radius: 14px;
}}
QFrame#panel2 {{
    background: {PANEL_2};
    border: 1px solid #2a3444;
    border-radius: 12px;
}}

QPushButton {{
    background: {PANEL_2};
    border: 1px solid #2c3646;
    border-radius: 10px;
    padding: 8px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT_DIM}; }}
QPushButton:pressed {{ background: #202a38; }}

QPushButton#primary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT_DIM}, stop:1 {ACCENT});
    color: #04121a;
    font-weight: 700;
    border: none;
    border-radius: 12px;
    padding: 11px 18px;
}}
QPushButton#primary:hover {{ background: {ACCENT}; }}
QPushButton#danger {{ border-color: #5a2c34; }}
QPushButton#danger:hover {{ border-color: #d9556a; color: #ff9aa8; }}

QComboBox, QLineEdit, QSpinBox {{
    background: {PANEL_2};
    border: 1px solid #2c3646;
    border-radius: 9px;
    padding: 7px 10px;
    selection-background-color: {ACCENT_DIM};
}}
QComboBox:hover, QLineEdit:focus {{ border-color: {ACCENT_DIM}; }}
QComboBox QAbstractItemView {{
    background: {PANEL_2};
    border: 1px solid #2c3646;
    selection-background-color: {ACCENT_DIM};
    border-radius: 8px;
}}

QListWidget {{
    background: {PANEL};
    border: 1px solid #232c3a;
    border-radius: 12px;
    padding: 6px;
}}
QListWidget::item {{
    background: {PANEL_2};
    border: 1px solid #2a3444;
    border-radius: 10px;
    padding: 10px;
    margin: 4px 2px;
}}
QListWidget::item:selected {{
    border: 1px solid {ACCENT};
    background: #1a2635;
}}

QTextEdit#console {{
    background: #090c12;
    border: 1px solid #202836;
    border-radius: 12px;
    color: #b9c6d4;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    padding: 10px;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: #2c3646; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

QProgressBar {{
    background: {PANEL_2};
    border: none;
    border-radius: 8px;
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT_DIM}, stop:1 {ACCENT});
    border-radius: 8px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 9px 16px;
    color: {MUTED};
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabWidget::pane {{ border: none; }}
"""
