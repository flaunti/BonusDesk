APP_STYLE = r"""
* { font-family: "Segoe UI Variable", "Segoe UI"; font-size: 13px; }
QMainWindow, QDialog, QWidget#root { background: #f4f7fb; color: #162033; }
QWidget { color: #162033; }
QFrame#sidebar { background: #10243e; border-right: 1px solid #193653; }
QFrame#card { background: #ffffff; border: 1px solid #dce5ef; border-radius: 12px; }
QLabel#brand { font-size: 20px; font-weight: 750; color: #ffffff; }
QLabel#brandAccent { font-size: 11px; font-weight: 600; color: #9fb3ca; }
QLabel#sidebarMeta { color: #8fa5bd; font-size: 11px; }
QLabel#pageTitle { font-size: 24px; font-weight: 750; color: #162033; }
QLabel#sectionTitle { font-size: 16px; font-weight: 700; color: #162033; }
QLabel#muted { color: #66758a; }
QLabel#money { font-size: 27px; font-weight: 800; color: #2563eb; }
QLabel#warning { color: #8a4b14; background: #fff5e9; border: 1px solid #f2d4ad; border-radius: 8px; padding: 8px; }
QLabel#success { color: #0e6f68; background: #e8f7f5; border: 1px solid #bee6e1; border-radius: 8px; padding: 8px; }
QLabel#evidenceLink { color: #2563eb; background: transparent; padding: 1px 2px; }
QPushButton { background: #ffffff; border: 1px solid #cfd9e5; border-radius: 8px; padding: 8px 12px; color: #26364a; font-weight: 600; }
QPushButton:hover { background: #f5f8fc; border-color: #9fb1c5; }
QPushButton:pressed { background: #eaf0f7; }
QPushButton:disabled { color: #a4afbd; background: #f0f3f7; border-color: #e1e6ed; }
QPushButton#primary, QPushButton#success { background: #2563eb; border-color: #2563eb; color: white; }
QPushButton#primary:hover, QPushButton#success:hover { background: #1d4ed8; border-color: #1d4ed8; }
QPushButton#danger { background: #fff4f2; border-color: #efc5c1; color: #b8423a; }
QPushButton#danger:hover { background: #ffe9e6; border-color: #dd938d; }
QPushButton#nav { text-align: left; background: transparent; border: 0; padding: 10px 14px; color: #b9c8d9; }
QPushButton#nav:hover { background: #17324f; color: #ffffff; }
QPushButton#nav:checked { background: #1b3d62; color: #ffffff; border-left: 3px solid #63b3ff; }
QLineEdit, QTextEdit, QComboBox, QSpinBox { background: #ffffff; border: 1px solid #cfd9e5; border-radius: 7px; padding: 7px; color: #162033; selection-background-color: #bdd4ff; selection-color: #10243e; }
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #2563eb; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #cfd9e5; selection-background-color: #e8f1ff; selection-color: #173a69; }
QListWidget, QTableWidget { background: #ffffff; border: 1px solid #dce5ef; border-radius: 9px; gridline-color: #e5ebf2; outline: none; alternate-background-color: #f8fafc; }
QListWidget::item { padding: 11px; border-bottom: 1px solid #e7edf4; color: #26364a; }
QListWidget::item:hover { background: #f5f8fc; }
QListWidget::item:selected { background: #e8f1ff; color: #173a69; }
QHeaderView::section { background: #f1f5f9; color: #59697e; border: 0; border-bottom: 1px solid #dce5ef; padding: 9px; font-weight: 700; }
QTableWidget::item { padding: 6px; color: #26364a; }
QTableWidget::item:selected { background: #e8f1ff; color: #173a69; }
QTableCornerButton::section { background: #f1f5f9; border: 0; border-bottom: 1px solid #dce5ef; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #c6d2df; min-height: 28px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: #9fb1c5; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: transparent; width: 10px; }
QTabBar::tab { background: #f1f5f9; color: #66758a; padding: 9px 16px; border: 1px solid #dce5ef; }
QTabBar::tab:selected { background: #ffffff; color: #2563eb; }
QMenu { background: #ffffff; border: 1px solid #cfd9e5; padding: 5px; }
QMenu::item { padding: 7px 24px 7px 10px; border-radius: 5px; }
QMenu::item:selected { background: #e8f1ff; color: #173a69; }
QStatusBar { background: #eef3f8; color: #66758a; border-top: 1px solid #dce5ef; }
QToolTip { background: #10243e; color: white; border: 1px solid #284967; padding: 5px; }
"""
