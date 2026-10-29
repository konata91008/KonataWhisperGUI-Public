import sys
import os
import subprocess
import tempfile
import shutil
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QFileDialog, QGridLayout, QLabel, QListWidget, QListWidgetItem,
    QComboBox, QLineEdit, QCheckBox, QHBoxLayout, QVBoxLayout, QDialog,
    QDialogButtonBox, QSizeGrip, QMenu, QAction, QGraphicsDropShadowEffect,
    QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, QSize, QSettings, QEvent, QProcess
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem, QColor

# 從專案的其他模組中匯入
from .assets import STYLESHEET, SVG_ICONS, THEME_COLORS
from .widgets import (
    CustomComboBoxDelegate, CustomMessageBox, ProgressDialog, ResultDialog
)
from core.tasks import WorkerThread, download_task, transcription_task
from core.translations import TRANSLATIONS
from core.version import PROJECT_ROOT, VERSION_TEXT
from core.update_translations import update_strings
from .update_dialog import UpdateDialog
from core.subtitle_ai import APIConfig, load_api_profiles, save_api_profiles
from core.ai_translations import ai_strings
from core.gpu_setup import load_runtime

# --- 主視窗 (已更新) ---
class WhisperGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle("TJKSub")
        self.setGeometry(100, 100, 940, 760)
        self.setMinimumWidth(860)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._offset = None
        
        self.temp_dir = tempfile.mkdtemp()
        self.create_svg_files()

        # --- 語言切換相關 ---
        self.current_lang = 'zh_TW'
        self.translations = TRANSLATIONS[self.current_lang]
        # ---

        self.themes = ["light", "dark"]
        self.current_theme_index = 0
        self.current_colors = {}
        self.file_times = []
        self.file_results = []
        self.current_run_logs = []
        self.is_downloading = False
        self.worker = None
        settings = QSettings('Konata', 'KonataSub')
        self.api_profiles, self.api_config = load_api_profiles(settings)
        self.update_dialog = None
        self.setup_dialog = None
        self.gpu_runtime = None
        self.update_pending_restart = False
        self.content_widget = None # 用於存放內容元件的引用
        
        self.setAcceptDrops(True)

        self.init_ui()
        self.find_executable()
        self.load_model_list()
        self.populate_backend_combo()
        self.load_settings() # 讀取上次的設定

    # [移除] 移除主視窗的 paintEvent，背景將由 content_widget 處理
    # def paintEvent(self, event):
    #     ...

    def mousePressEvent(self, event):
        # 判斷點擊位置是否在內容元件之外的標題區域
        if self.content_widget:
            content_rect = self.content_widget.geometry()
            if not content_rect.contains(event.pos()) or event.y() < content_rect.y() + 50:
                 if event.button() == Qt.LeftButton:
                    self._offset = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._offset is not None and event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.pos() - self._offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._offset = None
        super().mouseReleaseEvent(event)

    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.update_theme()

    def create_svg_files(self):
        new_icons = ["minimize.svg", "maximize.svg", "restore.svg", "close.svg", "globe.svg"]
        for name, content in SVG_ICONS.items():
            path = os.path.join(self.temp_dir, name)
            if "{SUCCESS_COLOR}" in content:
                with open(os.path.join(self.temp_dir, f"check_light.svg"), 'w') as f_light:
                    f_light.write(content.replace("{SUCCESS_COLOR}", THEME_COLORS["light"]["SUCCESS"]))
                with open(os.path.join(self.temp_dir, f"check_dark.svg"), 'w') as f_dark:
                    f_dark.write(content.replace("{SUCCESS_COLOR}", THEME_COLORS["dark"]["SUCCESS"]))
            elif "{ICON_COLOR}" in content or name in new_icons:
                base_name = name.replace('.svg', '')
                with open(os.path.join(self.temp_dir, f"{base_name}_light.svg"), 'w') as f_light:
                    f_light.write(content.replace("{ICON_COLOR}", THEME_COLORS["light"]["TEXT_SECONDARY"]))
                with open(os.path.join(self.temp_dir, f"{base_name}_dark.svg"), 'w') as f_dark:
                    f_dark.write(content.replace("{ICON_COLOR}", THEME_COLORS["dark"]["TEXT_SECONDARY"]))
            else: 
                with open(path, 'w') as f:
                    f.write(content)

    def get_icon_path(self, name):
        if name in ["info.svg", "question.svg", "error.svg", "check.svg", "minimize.svg", "maximize.svg", "restore.svg", "close.svg", "globe.svg", "settings.svg"]:
            theme = "dark" if self.property("theme") == "dark" else "light"
            name = f"{name.replace('.svg', '')}_{theme}.svg"
        path = os.path.join(self.temp_dir, name)
        return path.replace("\\", "/")

    def init_ui(self):
        self.titleLabel = QLabel("TJKSub", objectName="TitleLabel")
        self.subtitleLabel = QLabel(VERSION_TEXT, objectName="SubtitleLabel")
        
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(0)
        title_vbox.addWidget(self.titleLabel)
        title_vbox.addWidget(self.subtitleLabel)

        # --- 語言切換：精緻下拉選單 (按鈕顯示目前語言簡稱，選單打勾目前語言) ---
        self.langButton = QPushButton(objectName="LangButton")
        self.langButton.setFixedHeight(32)
        self.langButton.setIconSize(QSize(18, 18))
        self.langButton.setCursor(Qt.PointingHandCursor)

        self.langMenu = QMenu(self)
        # 讓選單背景透明，才能呈現 QSS 的圓角卡片外觀
        self.langMenu.setAttribute(Qt.WA_TranslucentBackground)
        self.langMenu.setWindowFlags(self.langMenu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)

        self.lang_short_names = {'en': 'EN', 'ja': '日', 'zh_TW': '繁', 'zh_CN': '简'}
        self.lang_actions = {}
        for code, label in [('en', 'English'), ('ja', '日本語'), ('zh_TW', '繁體中文'), ('zh_CN', '简体中文')]:
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _, c=code: self.change_language(c))
            self.langMenu.addAction(action)
            self.lang_actions[code] = action
        self.langButton.setMenu(self.langMenu)

        self.themeButton = QPushButton()
        self.themeButton.setFixedSize(32, 32)
        self.themeButton.setIconSize(QSize(20, 20))
        self.themeButton.clicked.connect(self.cycle_theme)

        self.settingsButton = QPushButton(objectName='SettingsButton')
        self.settingsButton.setFixedSize(32, 32)
        self.settingsButton.setIconSize(QSize(20, 20))
        self.settingsMenu = QMenu(self)
        self.apiSettingsAction = self.settingsMenu.addAction('')
        self.apiSettingsAction.triggered.connect(self.open_api_settings)
        self.gpuSetupAction = self.settingsMenu.addAction('顯卡與引擎設定…')
        self.gpuSetupAction.triggered.connect(self.open_gpu_setup)
        self.checkUpdateAction = self.settingsMenu.addAction('')
        self.checkUpdateAction.triggered.connect(self.open_update_dialog)
        self.settingsButton.setMenu(self.settingsMenu)
        
        self.minimizeButton = QPushButton()
        self.minimizeButton.setFixedSize(32, 32)
        self.minimizeButton.setIconSize(QSize(16, 16))
        self.minimizeButton.clicked.connect(self.showMinimized)

        self.maximizeButton = QPushButton()
        self.maximizeButton.setFixedSize(32, 32)
        self.maximizeButton.setIconSize(QSize(16, 16))
        self.maximizeButton.clicked.connect(self.toggle_maximize_restore)

        self.closeButton = QPushButton(objectName="CloseButton")
        self.closeButton.setFixedSize(32, 32)
        self.closeButton.setIconSize(QSize(16, 16))
        self.closeButton.clicked.connect(self.close)

        top_layout = QHBoxLayout()
        top_layout.addLayout(title_vbox)
        top_layout.addStretch()
        top_layout.addWidget(self.langButton)
        top_layout.addSpacing(4)
        top_layout.addWidget(self.themeButton)
        top_layout.addWidget(self.settingsButton)
        top_layout.addWidget(self.minimizeButton)
        top_layout.addWidget(self.maximizeButton)
        top_layout.addWidget(self.closeButton)

        self.fileList = QListWidget(objectName="FileList")
        self.fileList.setSelectionMode(QListWidget.ExtendedSelection)
        self.fileList.itemSelectionChanged.connect(self.update_file_count)
        self.fileList.installEventFilter(self)

        self.btnAdd = QPushButton()
        self.btnRemove = QPushButton()
        self.fileCountLabel = QLabel(objectName="FileCountLabel")
        
        file_btn_layout = QHBoxLayout()
        file_btn_layout.addWidget(self.btnAdd)
        file_btn_layout.addWidget(self.btnRemove)
        file_btn_layout.addStretch()

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        
        self.savePathLabel = QLabel()
        self.savePathEdit = QLineEdit()
        self.btnSave = QPushButton()
        grid.addWidget(self.savePathLabel, 0, 0, 1, 2)
        grid.addWidget(self.savePathEdit, 1, 0)
        grid.addWidget(self.btnSave, 1, 1)
        
        self.modelLabel = QLabel()
        self.modelCombo = QComboBox()
        self.modelCombo.activated[int].connect(self.on_model_selected)
        self.combo_delegate = CustomComboBoxDelegate(self)
        self.modelCombo.setItemDelegate(self.combo_delegate)
        grid.addWidget(self.modelLabel, 2, 0, 1, 2)
        grid.addWidget(self.modelCombo, 3, 0, 1, 2)
        
        self.langLabel = QLabel()
        self.langCombo = QComboBox()
        self.langCombo.setItemDelegate(self.combo_delegate)
        grid.addWidget(self.langLabel, 4, 0, 1, 2)
        grid.addWidget(self.langCombo, 5, 0, 1, 2)

        self.backendLabel = QLabel()
        self.backendCombo = QComboBox()
        self.backendCombo.setItemDelegate(self.combo_delegate)
        grid.addWidget(self.backendLabel, 6, 0, 1, 2)
        grid.addWidget(self.backendCombo, 7, 0, 1, 2)

        output_options_layout = QVBoxLayout()
        output_options_layout.setSpacing(8)
        self.outputFormatLabel = QLabel()
        
        self.outputSrtCheck = QCheckBox()
        self.outputSrtCheck.setChecked(True)
        self.outputTxtCheck = QCheckBox()
        
        output_options_layout.addWidget(self.outputFormatLabel)
        output_options_layout.addWidget(self.outputSrtCheck)
        output_options_layout.addWidget(self.outputTxtCheck)
        output_options_layout.addStretch()

        grid.addLayout(output_options_layout, 8, 0, 1, 2)

        self.promptLabel = QLabel()
        grid.addWidget(self.promptLabel, 9, 0, 1, 2)

        self.promptEdit = QLineEdit()
        grid.addWidget(self.promptEdit, 10, 0, 1, 2)

        # 本次使用範圍常駐顯示；Prompt 寫法保留在輸入框工具提示。
        self.promptHintLabel = QLabel(objectName="PromptHintLabel")
        self.promptHintLabel.setWordWrap(True)
        self.promptHintLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        grid.addWidget(self.promptHintLabel, 11, 0, 1, 2)

        self.btnStart = QPushButton(objectName="PrimaryButton")

        # --- 低彩度奶茶色陰影 ---
        self.start_glow = QGraphicsDropShadowEffect(self.btnStart)
        self.start_glow.setBlurRadius(16)
        self.start_glow.setXOffset(0)
        self.start_glow.setYOffset(3)
        self.start_glow.setColor(QColor(181, 163, 148, 55))  # Morandi taupe
        self.btnStart.setGraphicsEffect(self.start_glow)
        self.btnStart.installEventFilter(self)

        # 左側檔案、右側設定。放大視窗時將多出的高度留給檔案清單。
        self.fileList.setMinimumHeight(260)
        self.files_widget = QWidget()
        files_vbox = QVBoxLayout(self.files_widget)
        files_vbox.setContentsMargins(0, 0, 0, 0)
        files_vbox.setSpacing(10)
        files_vbox.addLayout(file_btn_layout)
        files_vbox.addWidget(self.fileCountLabel, alignment=Qt.AlignLeft)
        files_vbox.addWidget(self.fileList, stretch=1)

        self.settings_widget = QWidget()
        self.settings_widget.setMinimumWidth(330)
        self.settings_widget.setMaximumWidth(420)
        settings_vbox = QVBoxLayout(self.settings_widget)
        settings_vbox.setContentsMargins(0, 0, 0, 0)
        settings_vbox.addLayout(grid)
        settings_vbox.addStretch()

        body_layout = QHBoxLayout()
        body_layout.setSpacing(24)
        body_layout.addWidget(self.files_widget, stretch=1)
        body_layout.addWidget(self.settings_widget, stretch=1)

        content_inner_layout = QVBoxLayout()
        content_inner_layout.setContentsMargins(28, 24, 28, 24)
        content_inner_layout.addLayout(top_layout)
        content_inner_layout.addSpacing(24)
        content_inner_layout.addLayout(body_layout, stretch=1)
        content_inner_layout.addSpacing(16)
        content_inner_layout.addWidget(self.btnStart)
        
        # 內容面板使用霧面實色，避免與主按鈕的圖形效果互相干擾。
        self.content_widget = QWidget()
        self.content_widget.setObjectName("ContentWidget")
        self.content_widget.setLayout(content_inner_layout)

        # 外側邊距保留給視窗圓角與右下方縮放把手。
        main_layout = QGridLayout()
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.addWidget(self.content_widget, 0, 0)
        main_layout.addWidget(QSizeGrip(self), 0, 0, Qt.AlignBottom | Qt.AlignRight)
        self.setLayout(main_layout)

        self.btnAdd.clicked.connect(self.add_files)
        self.btnRemove.clicked.connect(self.remove_selected)
        self.btnSave.clicked.connect(self.select_save_path)
        self.btnStart.clicked.connect(self.start_task)

    def eventFilter(self, obj, event):
        # Scope removal to the focused file list; text fields keep normal editing.
        if (obj is getattr(self, 'fileList', None) and event.type() == QEvent.KeyPress
                and event.key() in (Qt.Key_Delete, Qt.Key_Backspace)
                and event.modifiers() == Qt.NoModifier):
            if self.fileList.isEnabled() and self.btnRemove.isEnabled():
                self.remove_selected()
            return True
        # 「開始轉錄」按鈕的奶茶色光暈 hover 效果
        if obj is getattr(self, 'btnStart', None) and hasattr(self, 'start_glow'):
            if event.type() == QEvent.Enter:
                self.start_glow.setBlurRadius(34)
                self.start_glow.setColor(QColor(181, 163, 148, 100))
            elif event.type() == QEvent.Leave:
                self.start_glow.setBlurRadius(16)
                self.start_glow.setColor(QColor(181, 163, 148, 55))
        return super().eventFilter(obj, event)

    def save_settings(self):
        settings = QSettings("Konata", "KonataSub")
        settings.setValue("model", self.modelCombo.currentText())
        settings.setValue("language", self.langCombo.currentData())
        settings.setValue("backend", self.backendCombo.currentText())
        settings.setValue("output_srt", self.outputSrtCheck.isChecked())
        settings.setValue("output_txt", self.outputTxtCheck.isChecked())
        settings.setValue("save_path", self.savePathEdit.text())
        settings.setValue("theme_index", self.current_theme_index)
        settings.setValue("ui_language", self.current_lang)
        settings.sync()

    def load_settings(self):
        settings = QSettings("Konata", "KonataSub")
        self.current_theme_index = settings.value("theme_index", 0, type=int)
        self.update_theme()
        
        ui_language = settings.value("ui_language", "zh_TW", type=str)
        self.change_language(ui_language)

        model_name = settings.value("model", "base", type=str)
        if self.modelCombo.findText(model_name) != -1:
            self.modelCombo.setCurrentText(model_name)

        lang_code = settings.value("language", "auto", type=str)
        lang_index = self.langCombo.findData(lang_code)
        if lang_index != -1:
            self.langCombo.setCurrentIndex(lang_index)

        backend_name = settings.value("backend", "", type=str)
        if backend_name and self.backendCombo.findText(backend_name) != -1:
            self.backendCombo.setCurrentText(backend_name)
        
        self.outputSrtCheck.setChecked(settings.value("output_srt", True, type=bool))
        self.outputTxtCheck.setChecked(settings.value("output_txt", False, type=bool))
        self.savePathEdit.setText(settings.value("save_path", "", type=str))

    def change_language(self, lang_code):
        self.current_lang = lang_code
        self.translations = TRANSLATIONS[lang_code]
        # 同步下拉選單勾選狀態與按鈕上的語言簡稱
        for code, action in getattr(self, 'lang_actions', {}).items():
            action.setChecked(code == lang_code)
        if hasattr(self, 'langButton'):
            self.langButton.setText(self.lang_short_names.get(lang_code, ''))
        self.retranslate_ui()

    def retranslate_ui(self):
        trans = self.translations
        
        self.subtitleLabel.setText(VERSION_TEXT)
        updates = update_strings(self.current_lang)
        self.settingsButton.setToolTip(updates['settings'])
        self.settingsButton.setAccessibleName(updates['settings'])
        self.checkUpdateAction.setText(updates['menu'])
        self.apiSettingsAction.setText(ai_strings(self.current_lang)['settings'])
        self.btnAdd.setText(trans['import_button'])
        self.btnRemove.setText(trans['remove_button'])
        self.update_file_count() 
        
        self.savePathLabel.setText(trans['save_path_label'])
        self.savePathEdit.setPlaceholderText(trans['save_path_placeholder'])
        self.btnSave.setText(trans['select_location_button'])
        self.modelLabel.setText(trans['model_label'])
        self.langLabel.setText(trans['language_label'])
        self.backendLabel.setText(trans['compute_mode_label'])
        
        self.outputFormatLabel.setText(trans['output_format_label'])
        self.outputSrtCheck.setText(trans['srt_checkbox'])
        self.outputTxtCheck.setText(trans['txt_checkbox'])
        
        self.promptLabel.setText(trans['prompt_label'])
        self.promptEdit.setPlaceholderText(trans['prompt_placeholder'])
        self.promptHintLabel.setText(trans['prompt_hint'])
        self.promptEdit.setToolTip(trans['prompt_usage_hint'])
        self.btnStart.setText(trans['start_button'])

        self.populate_languages()
        self.populate_backend_combo()
        
    def show_message(self, icon_type, title, text, buttons=QDialogButtonBox.Ok):
        dialog = CustomMessageBox(self, icon_type, title, text, buttons)
        dialog.setStyleSheet(self.styleSheet())
        dialog.setThemeColors(self.current_colors)
        
        ok_button = dialog.button_box.button(QDialogButtonBox.Ok)
        if ok_button: ok_button.setText(self.translations['ok_button'])
        yes_button = dialog.button_box.button(QDialogButtonBox.Yes)
        if yes_button: yes_button.setText("Yes")
        no_button = dialog.button_box.button(QDialogButtonBox.No)
        if no_button: no_button.setText("No")
        cancel_button = dialog.button_box.button(QDialogButtonBox.Cancel)
        if cancel_button: cancel_button.setText(self.translations['cancel_button'])

        return dialog.exec_()

    def find_executable(self):
        self.base_dir = str(PROJECT_ROOT / 'whisper.cpp')
        self.gpu_runtime = load_runtime(PROJECT_ROOT)
        self.exe_path = self.gpu_runtime['path'] if self.gpu_runtime else None

    def load_model_list(self):
        current_model_text = self.modelCombo.currentText()
        model = QStandardItemModel()
        self.modelCombo.setModel(model)
        models_dir = os.path.join(self.base_dir, 'models')
        os.makedirs(models_dir, exist_ok=True)
        choices = ['tiny', 'base', 'small', 'medium', 'large-v1', 'large-v2', 'large-v3', 'large-v3-turbo']
        for name in choices:
            item = QStandardItem(name)
            path = os.path.join(models_dir, f'ggml-{name}.bin')
            item.setData(os.path.exists(path), Qt.UserRole)
            model.appendRow(item)
        if current_model_text in choices:
            self.modelCombo.setCurrentText(current_model_text)
        self.update_theme()

    def on_model_selected(self, index):
        if self.is_downloading: return
        item = self.modelCombo.model().item(index)
        is_available = item.data(Qt.UserRole)
        if not is_available:
            model_name = self.modelCombo.itemText(index)
            title = self.translations['download_model_title']
            prompt = self.translations['download_model_prompt'].format(model_name=model_name)
            reply = self.show_message("question", title, prompt, QDialogButtonBox.Yes | QDialogButtonBox.No)
            if reply == QDialog.Accepted:
                self.download_model(model_name)

    def download_model(self, model_name):
        self.is_downloading = True
        title = self.translations['download_model_title'] + f" {model_name}..."
        self.progress_dialog = ProgressDialog(self, title=title)
        self.progress_dialog.progressBar.setRange(0, 100)
        self.progress_dialog.cancelButton.clicked.connect(self.cancel_task)
        self.progress_dialog.setStyleSheet(self.styleSheet())
        self.progress_dialog.setThemeColors(self.current_colors)
        self.progress_dialog.retranslate_ui(self.translations)
        self.progress_dialog.show()
        
        self.worker = WorkerThread(download_task, main_window=self, model_name=model_name, base_dir=self.base_dir)
        self.worker.progress_update.connect(self.progress_dialog.update_progress)
        self.worker.download_finished.connect(self.on_download_finished)
        self.worker.start()

    def on_download_finished(self, success):
        self.is_downloading = False
        # [修復閃退] 與 on_task_finished 相同：等執行緒結束後再安全釋放
        if self.worker:
            self.worker.wait(5000)
            self.worker.deleteLater()
            self.worker = None
        self.progress_dialog.close()
        trans = self.translations
        if success:
            self.show_message("info", trans['download_success_title'], trans['download_success_body'])
        else:
            self.show_message("error", trans['download_failed_title'], trans['download_failed_body'])
        self.load_model_list()

    def populate_languages(self):
        current_data = self.langCombo.currentData()
        self.langCombo.clear()
        trans = self.translations
        langs = [
            (trans['lang_auto'], 'auto'), (trans['lang_zh'], 'zh'), (trans['lang_en'], 'en'), 
            (trans['lang_ja'], 'ja'), (trans['lang_ko'], 'ko'), (trans['lang_es'], 'es'), 
            (trans['lang_fr'], 'fr'), (trans['lang_de'], 'de'), (trans['lang_ru'], 'ru')
        ]
        for name, code in langs:
            self.langCombo.addItem(name, code)
        
        index = self.langCombo.findData(current_data)
        if index != -1:
            self.langCombo.setCurrentIndex(index)
        else:
            self.langCombo.setCurrentIndex(0)

    def populate_backend_combo(self):
        self.backendCombo.clear()
        runtime = getattr(self, 'gpu_runtime', None)
        if runtime:
            self.backendCombo.addItem(runtime['backend'].upper() + ' · ' + runtime['gpu']['name'], runtime['backend'])
        else:
            self.backendCombo.addItem('尚未設定顯卡 · 請開啟齒輪設定', None)
        self.backendCombo.setToolTip('依已完成編譯的顯卡啟用；不會自動切換 CPU。')

    def open_gpu_setup(self):
        if self.is_downloading or (self.worker and self.worker.isRunning()):
            self.show_message('info', '顯卡設定', '請先等待目前的轉錄／下載完成。')
            return
        if self.update_pending_restart or (self.update_dialog and self.update_dialog.is_busy()):
            self.show_message('info', '顯卡設定', '請先完成更新並重新啟動程式。')
            return
        if self.setup_dialog:
            self.setup_dialog.raise_()
            return
        from .gpu_dialog import GPUSetupDialog
        self.setup_dialog = GPUSetupDialog(self)
        self.setup_dialog.exec_()
        self.setup_dialog.deleteLater()
        self.setup_dialog = None

    def cycle_theme(self):
        self.current_theme_index = (self.current_theme_index + 1) % len(self.themes)
        self.update_theme()

    def update_theme(self):
        theme = self.themes[self.current_theme_index]
        self.setProperty("theme", theme)
        self.langButton.setIcon(QIcon(self.get_icon_path("globe.svg")))
        self.settingsButton.setIcon(QIcon(self.get_icon_path('settings.svg')))
        self.themeButton.setIcon(QIcon(self.get_icon_path(f"{'moon' if theme == 'dark' else 'sun'}.svg")))

        self.minimizeButton.setIcon(QIcon(self.get_icon_path("minimize.svg")))
        self.maximizeButton.setIcon(QIcon(self.get_icon_path("restore.svg" if self.isMaximized() else "maximize.svg")))
        self.closeButton.setIcon(QIcon(self.get_icon_path("close.svg")))

        self.current_colors = THEME_COLORS[theme].copy()
        arrow_icon_path = self.get_icon_path(f"down_arrow_{theme}.svg")
        self.current_colors["DOWN_ARROW_URL"] = arrow_icon_path
        sheet = STYLESHEET
        for key, value in self.current_colors.items(): sheet = sheet.replace(f"{{{key}}}", value)
        self.setStyleSheet(sheet)
        
        # [修改] 為 content_widget 動態設定背景和圓角
        if self.content_widget:
            bg_color = self.current_colors.get("BG_PRIMARY", "#f4f0eb")
            border_color = self.current_colors.get("BORDER_PRIMARY", "#e1d8ce")
            self.content_widget.setStyleSheet(f"""
                #ContentWidget {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 20px;
                }}
            """)

        self.style().unpolish(self); self.style().polish(self)
        self.combo_delegate.setThemeColors(self.current_colors)
        self.modelCombo.view().repaint()
        self.langCombo.view().repaint()
        self.backendCombo.view().repaint()
        self.update()

    def add_files(self, paths=None):
        formats = ['.wav', '.mp3', '.m4a', '.mp4', '.mov', '.mkv', '.ogg', '.flac']
        if not paths:
            files, _ = QFileDialog.getOpenFileNames(self, "選擇檔案", "", f"媒體檔案 ({' '.join(['*' + f for f in formats])})")
            paths = files
        for f in paths:
            if os.path.splitext(f)[1].lower() in formats:
                existing_paths = {self.fileList.item(i).data(Qt.UserRole) for i in range(self.fileList.count())}
                if f not in existing_paths:
                    item = QListWidgetItem(os.path.basename(f))
                    item.setData(Qt.UserRole, f)
                    item.setToolTip(f)
                    self.fileList.addItem(item)
        self.update_file_count()

    def remove_selected(self):
        for item in self.fileList.selectedItems(): self.fileList.takeItem(self.fileList.row(item))
        self.update_file_count()

    def update_file_count(self):
        count = self.fileList.count()
        self.fileCountLabel.setText(self.translations['total_files'].format(count=count))

    def select_save_path(self):
        d = QFileDialog.getExistingDirectory(self, "選擇儲存資料夾")
        if d: self.savePathEdit.setText(d)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.fileList.setProperty("dragging", True)
            self.style().unpolish(self.fileList); self.style().polish(self.fileList)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.fileList.setProperty("dragging", False)
        self.style().unpolish(self.fileList); self.style().polish(self.fileList)

    def dropEvent(self, event):
        self.fileList.setProperty("dragging", False)
        self.style().unpolish(self.fileList); self.style().polish(self.fileList)
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.add_files(paths)

    def _handle_log_message(self, message):
        self.current_run_logs.append(message)
        if hasattr(self, 'progress_dialog') and self.progress_dialog.isVisible():
            self.progress_dialog.add_log_message(message)

    def start_task(self):
        trans = self.translations
        if self.update_dialog and self.update_dialog.is_busy():
            return
        if self.setup_dialog and self.setup_dialog.is_busy(): return
        if not self.exe_path:
            self.show_message('info', '尚未設定顯卡', '請從齒輪開啟「顯卡與引擎設定」，先完成 GPU 編譯。')
            return

        files_to_process = [self.fileList.item(i).data(Qt.UserRole) for i in range(self.fileList.count())]
        
        if not files_to_process:
            self.show_message("error", trans['error_title'], trans['no_files_error']); return
            
        save_dir = self.savePathEdit.text().strip()
        if save_dir and not os.path.isdir(save_dir):
            self.show_message("error", trans['error_title'], trans['invalid_save_path_error']); return
        if not self.outputSrtCheck.isChecked() and not self.outputTxtCheck.isChecked():
            self.show_message("error", trans['error_title'], trans['no_output_format_error']); return

        model_name = self.modelCombo.currentText()
        model_path = os.path.join(self.base_dir, 'models', f'ggml-{model_name}.bin')
        if not os.path.exists(model_path):
            self.show_message("error", trans['model_missing_error_title'], 
                              trans['model_missing_error_body'].format(path=model_path))
            return

        params = {
            "main_window": self, 
            "files": files_to_process,
            "save_dir": save_dir,
            "model": self.modelCombo.currentText(),
            "lang": self.langCombo.currentData(),
            "backend_str": self.backendCombo.currentText(),
            "prompt": self.promptEdit.text().strip(),
            "out_srt": self.outputSrtCheck.isChecked(),
            "out_txt": self.outputTxtCheck.isChecked(),
            "exe_path": self.exe_path,
            "base_dir": self.base_dir,
            "temp_dir": self.temp_dir,
            "gpu_runtime": self.gpu_runtime,
        }
        
        self.progress_dialog = ProgressDialog(self, title=trans['transcribing_progress_title'])
        
        self.progress_dialog.set_indeterminate(True)
            
        self.progress_dialog.cancelButton.clicked.connect(self.cancel_task)
        self.progress_dialog.setStyleSheet(self.styleSheet())
        self.progress_dialog.setThemeColors(self.current_colors)
        self.progress_dialog.retranslate_ui(trans)
        
        self.file_times = []
        self.file_results = []
        self.current_run_logs = []
        self.worker = WorkerThread(transcription_task, **params)

        self.worker.progress_update.connect(self.progress_dialog.update_progress)
        self.worker.log_message_received.connect(self._handle_log_message)
        self.worker.subtitle_line_received.connect(self.progress_dialog.add_subtitle_message)
        self.worker.file_finished.connect(lambda f, t: self.file_times.append((f, t)))
        self.worker.file_result.connect(self.file_results.append)
        self.worker.all_finished.connect(self.on_task_finished)
        
        self.progress_dialog.show()
        self.worker.start()
        # 參數已複製到這次的 WorkerThread；下次轉錄不自動沿用。
        # 僅在通過檢查且成功啟動後清空，驗證失敗時保留輸入供修正。
        self.promptEdit.clear()

    def cancel_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

    def on_task_finished(self, total_time, backend_str):
        # [修復閃退] all_finished 訊號發出時，執行緒的 run() 可能尚未真正結束。
        # 若立刻把 self.worker 設為 None，WorkerThread 物件會在執行緒還在跑時被
        # Python 垃圾回收，導致 "QThread: Destroyed while thread is still running"
        # 而使程式直接退出。因此先等執行緒完全結束，再用 deleteLater 安全釋放。
        if self.worker:
            self.worker.wait(5000)
            self.worker.deleteLater()
        self.worker = None
        full_log_text = "\n".join(self.current_run_logs)
        trans = self.translations

        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()
        
        result_dialog = ResultDialog(self)
        result_dialog.setStyleSheet(self.styleSheet())
        result_dialog.setThemeColors(self.current_colors)
        
        success = bool(self.file_times)

        if success:
            icon_path = self.get_icon_path("check.svg")
            title = trans['task_complete_title']
        else:
            icon_path = self.get_icon_path("error.svg")
            title = trans['task_failed_title']

        result_dialog.iconLabel.setPixmap(QIcon(icon_path).pixmap(32, 32))
        result_dialog.retranslate_ui(trans, title)
        result_dialog.set_results(self.file_times, total_time, backend_str, full_log_text, success)
        result_dialog.set_file_details(self.file_results, trans)
        result_dialog.exec_()

    def save_api_settings(self):
        settings = QSettings('Konata', 'KonataSub')
        self.api_profiles[self.api_config.protocol] = self.api_config
        save_api_profiles(settings, self.api_profiles, self.api_config)

    def open_api_settings(self):
        from .ai_dialog import APISettingsDialog
        dialog = APISettingsDialog(self)
        dialog.exec_()
        dialog.deleteLater()

    def open_update_dialog(self):
        if self.setup_dialog and self.setup_dialog.is_busy(): return
        if self.is_downloading or (self.worker and self.worker.isRunning()):
            strings = update_strings(self.current_lang)
            self.show_message('info', strings['title'], strings['busy'])
            return
        if self.update_dialog and self.update_dialog.isVisible():
            self.update_dialog.raise_()
            self.update_dialog.activateWindow()
            return
        if self.update_dialog:
            self.update_dialog.deleteLater()
        self.update_dialog = UpdateDialog(self)
        self.update_dialog.show()
        if not self.update_pending_restart:
            self.update_dialog.check()

    def restart_application(self):
        if self.setup_dialog and self.setup_dialog.is_busy(): return
        if (self.worker and self.worker.isRunning()) or self.is_downloading:
            return
        if self.update_dialog and self.update_dialog.is_busy():
            return
        self.save_settings()
        result = QProcess.startDetached(sys.executable,
                                        [str(PROJECT_ROOT / 'WhisperGUI' / 'main.py'), '--restarted'],
                                        str(PROJECT_ROOT))
        started = result[0] if isinstance(result, tuple) else result
        if not started:
            texts = update_strings(self.current_lang)
            self.show_message('error', texts['title'], texts['restart_failed'])
            return
        self.close()
        QApplication.instance().quit()

    def closeEvent(self, event):
        if self.setup_dialog and self.setup_dialog.is_busy():
            event.ignore()
            return
        if self.update_dialog and self.update_dialog.is_busy():
            event.ignore()
            return
        self.save_settings()
        if self.worker and self.worker.isRunning():
            self.cancel_task()
            self.worker.wait()
        
        shutil.rmtree(self.temp_dir)
        self.api_profiles.clear()
        self.api_config = APIConfig(self.api_config.base_url, self.api_config.model,
                                    protocol=self.api_config.protocol, workspace_id=self.api_config.workspace_id)
        event.accept()

