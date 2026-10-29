# 莫蘭迪奶茶：灰米白、燕麥色與低彩度褐色。
# 主按鈕與選取項目使用深色文字，維持淺色填色上的可讀性。
THEME_COLORS = {
    "light": {
        "BG_PRIMARY": "#f4f0eb", "BG_SECONDARY": "#eae4dd", "BG_TERTIARY": "#efe9e2",
        "TEXT_PRIMARY": "#514840", "TEXT_SECONDARY": "#70665d", "TEXT_TERTIARY": "#7a6f65",
        "BORDER_PRIMARY": "#e1d8ce", "BORDER_SECONDARY": "#cdc1b5", "TEXT_DISABLED": "#a29588",
        "ACCENT": "#b5a394", "ACCENT_HOVER": "#c2b2a3", "ACCENT_PRESSED": "#a18f7e",
        "ON_ACCENT": "#332c26", "SUCCESS": "#7f927f", "DANGER": "#ba9891",
    },
    "dark": {
        "BG_PRIMARY": "#363330", "BG_SECONDARY": "#2d2b28", "BG_TERTIARY": "#403c37",
        "TEXT_PRIMARY": "#e8e1da", "TEXT_SECONDARY": "#c7bcb0", "TEXT_TERTIARY": "#aea396",
        "BORDER_PRIMARY": "#514b45", "BORDER_SECONDARY": "#655c53", "TEXT_DISABLED": "#8f8377",
        "ACCENT": "#b8a99b", "ACCENT_HOVER": "#c5b8aa", "ACCENT_PRESSED": "#a49383",
        "ON_ACCENT": "#332c26", "SUCCESS": "#a2b19b", "DANGER": "#ba9891",
    },
}

# --- 主題樣式表 (QSS) ---
STYLESHEET = """
/* --- 字型：macOS 優先 (PingFang TC)，Windows 為輔 --- */
* {
    font-family: "PingFang TC", "Heiti TC", "Noto Sans TC", "Microsoft JhengHei", "Segoe UI", sans-serif;
}

/* --- General Window --- */
#MainWindow {
    background-color: {BG_PRIMARY};
}

/* --- Labels --- */
QLabel {
    color: {TEXT_SECONDARY};
    font-size: 13px;
    font-weight: 500;
}
#TitleLabel {
    color: {TEXT_PRIMARY};
    font-size: 30px;
    font-weight: 800;
    letter-spacing: 1px;
}
#SubtitleLabel {
    color: {TEXT_TERTIARY};
    font-size: 13px;
    font-weight: 400;
}
#PromptHintLabel {
    color: {TEXT_TERTIARY};
    font-size: 11px;
    font-weight: 400;
}

/* --- Buttons --- */
QPushButton {
    background-color: {BG_PRIMARY};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_SECONDARY};
    border-radius: 12px;
    padding: 9px 18px;
    font-size: 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: {BG_SECONDARY};
    border-color: {ACCENT};
}
#PrimaryButton, .QDialogButtonBox QPushButton[text="Yes"], .QDialogButtonBox QPushButton[text="OK"], .QDialogButtonBox QPushButton[text="確定"] {
    background-color: {ACCENT};
    color: {ON_ACCENT};
    border: none;
    border-radius: 14px;
    padding: 12px 18px;
    font-size: 15px;
    font-weight: 600;
}
#PrimaryButton:hover, .QDialogButtonBox QPushButton[text="Yes"]:hover, .QDialogButtonBox QPushButton[text="OK"]:hover, .QDialogButtonBox QPushButton[text="確定"]:hover {
    background-color: {ACCENT_HOVER};
}
#PrimaryButton:pressed, .QDialogButtonBox QPushButton[text="Yes"]:pressed, .QDialogButtonBox QPushButton[text="OK"]:pressed, .QDialogButtonBox QPushButton[text="確定"]:pressed {
    background-color: {ACCENT_PRESSED};
}
#MainWindow[theme="dark"] #PrimaryButton,
#MainWindow[theme="dark"] .QDialogButtonBox QPushButton[text="Yes"],
#MainWindow[theme="dark"] .QDialogButtonBox QPushButton[text="OK"],
#MainWindow[theme="dark"] .QDialogButtonBox QPushButton[text="確定"] {
    background-color: {ACCENT};
}
#MainWindow[theme="dark"] #PrimaryButton:hover,
#MainWindow[theme="dark"] .QDialogButtonBox QPushButton[text="Yes"]:hover,
#MainWindow[theme="dark"] .QDialogButtonBox QPushButton[text="OK"]:hover,
#MainWindow[theme="dark"] .QDialogButtonBox QPushButton[text="確定"]:hover {
    background-color: {ACCENT_HOVER};
}

/* --- 語言下拉按鈕：地球圖示 + 目前語言簡稱 --- */
#LangButton {
    background-color: {BG_SECONDARY};
    color: {TEXT_SECONDARY};
    border: none;
    border-radius: 10px;
    padding: 4px 12px;
    font-size: 13px;
    font-weight: 600;
}
#LangButton:hover {
    background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
}
#LangButton::menu-indicator {
    image: none;
    width: 0px;
}

/* --- 關閉按鈕的特殊樣式 --- */
#CloseButton:hover {
    background-color: {DANGER}; /* 柔和珊瑚粉，可愛風 */
    border-color: {DANGER};
}
#CloseButton:hover svg, #CloseButton:hover path, #CloseButton:hover line {
    stroke: {ON_ACCENT};
}


/* --- File List --- */
#FileList {
    background-color: {BG_TERTIARY};
    border: 1px solid {BORDER_PRIMARY};
    border-radius: 14px;
    color: {TEXT_SECONDARY};
    padding: 6px;
}
#FileList::item {
    padding: 8px;
    border-radius: 8px;
}
#FileList::item:selected {
    background-color: {ACCENT};
    color: {ON_ACCENT};
}
/* Style for drag-over feedback */
#FileList[dragging="true"] {
    border: 2px dashed {ACCENT};
}
#FileCountLabel {
    color: {TEXT_TERTIARY};
    font-size: 11px;
    background-color: {BG_SECONDARY};
    padding: 3px 10px;
    border-radius: 8px;
}


/* --- Inputs & Combos --- */
QLineEdit, QComboBox {
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SECONDARY};
    border-radius: 10px;
    padding: 9px 12px;
}
QLineEdit:focus, QComboBox:focus {
    border: 2px solid {ACCENT};
}
QComboBox::drop-down {
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 36px;
}
QComboBox { padding-right: 38px; }
QComboBox::down-arrow {
    image: url({DOWN_ARROW_URL}); /* Will be loaded from resources with absolute path */
    width: 18px;
    height: 18px;
}
#SettingsButton { padding: 4px; }
#SettingsButton::menu-indicator { image: none; width: 0px; }
#UpdateDetails {
    background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_PRIMARY};
    border-radius: 10px;
    padding: 12px;
    font-size: 13px;
}

QComboBox QAbstractItemView {
    background-color: {BG_PRIMARY};
    border: 1px solid {BORDER_SECONDARY};
    border-radius: 10px;
    outline: 0px; /* Remove focus outline */
}

QComboBox QAbstractItemView::item:hover {
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
}

QComboBox QAbstractItemView::item:disabled {
    color: {TEXT_DISABLED};
    background-color: transparent;
}

/* --- Checkbox：圓潤可愛的勾選框 --- */
QCheckBox {
    color: {TEXT_SECONDARY};
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 2px solid {BORDER_SECONDARY};
    background-color: {BG_PRIMARY};
}
QCheckBox::indicator:hover {
    border-color: {ACCENT};
}
QCheckBox::indicator:checked {
    background-color: {ACCENT};
    border-color: {ACCENT};
}

/* --- Dialogs --- */
#CustomDialog {
    border: 1px solid {BORDER_PRIMARY};
    border-radius: 16px;
}
#DialogTitleLabel {
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 600;
}
#DialogInfoLabel, #MessageBoxText {
    color: {TEXT_SECONDARY};
    font-size: 14px;
}

/* --- Progress Bar --- */
QProgressBar {
    border: 1px solid {BORDER_PRIMARY};
    border-radius: 8px;
    text-align: center;
    background-color: {BG_TERTIARY};
    color: {TEXT_SECONDARY};
    min-height: 16px;
}
QProgressBar::chunk {
    background-color: {ACCENT};
    border-radius: 7px;
}

/* --- Result List --- */
#ResultList {
    background-color: {BG_SECONDARY};
    border: 1px solid {BORDER_PRIMARY};
    border-radius: 14px;
}

/* --- Log View --- */
#LogView, QPlainTextEdit {
    background-color: {BG_TERTIARY};
    border: 1px solid {BORDER_PRIMARY};
    border-radius: 10px;
    color: {TEXT_SECONDARY};
    font-size: 13px;
    padding: 8px;
}

/* --- Scrollbar：奶茶色細捲軸 --- */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background-color: {BORDER_SECONDARY};
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: {ACCENT};
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background-color: {BORDER_SECONDARY};
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: {ACCENT};
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* --- Tabs：結果視窗的分頁（奶茶色圓角膠囊） --- */
QTabWidget::pane {
    border: 1px solid {BORDER_PRIMARY};
    border-radius: 10px;
    background-color: {BG_TERTIARY};
    top: 4px;
}
QTabBar::tab {
    background-color: {BG_SECONDARY};
    color: {TEXT_SECONDARY};
    padding: 6px 14px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 4px;
    font-size: 12px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: {ACCENT};
    color: {ON_ACCENT};
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
}

/* --- Menu：圓角卡片式下拉選單 --- */
QMenu {
    background-color: {BG_PRIMARY};
    border: 1px solid {BORDER_SECONDARY};
    border-radius: 12px;
    color: {TEXT_PRIMARY};
    padding: 6px;
}
QMenu::item {
    padding: 8px 24px 8px 10px;
    border-radius: 8px;
    min-width: 110px;
    font-size: 13px;
}
QMenu::item:selected {
    background-color: {ACCENT};
    color: {ON_ACCENT};
}
QMenu::item:checked {
    color: {TEXT_PRIMARY};
    font-weight: 700;
}
QMenu::indicator {
    width: 16px;
    height: 16px;
    margin-left: 4px;
}
"""

# --- SVG 圖示資源 ---
SVG_ICONS = {
    "settings.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m9 3 1-1h4l1 1 .5 2 2 1 2-.5 1.5 2.5-.5 2-1.5 1v2l1.5 1 .5 2-1.5 2.5-2-.5-2 1-.5 2-1 1h-4l-1-1-.5-2-2-1-2 .5L3 16l.5-2L5 13v-2l-1.5-1L3 8l1.5-2.5 2 .5 2-1z"/><circle cx="12" cy="12" r="3"/></svg>""",
    "sun.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#70665d" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>""",
    "moon.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#c7bcb0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>""",
    "down_arrow_light.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#aea396" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>""",
    "down_arrow_dark.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#c7bcb0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>""",
    "check.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="{SUCCESS_COLOR}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>""",
    "info.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>""",
    "question.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>""",
    "error.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>""",
    # --- 地球圖示 ---
    "globe.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>""",
    # --- 視窗控制圖示 ---
    "minimize.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>""",
    "maximize.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>""",
    "restore.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/></svg>""",
    "close.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{ICON_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>"""
}

