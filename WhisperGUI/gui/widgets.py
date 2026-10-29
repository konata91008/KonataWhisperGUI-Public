import os
import sys
from PyQt5.QtWidgets import (
    QWidget, QDialog, QProgressBar, QListWidget, QListWidgetItem, 
    QStyledItemDelegate, QStyle, QDialogButtonBox, QLabel, QHBoxLayout, QVBoxLayout,
    QPushButton, QGridLayout, QTextEdit, QTabWidget, QSizeGrip, QComboBox, QCheckBox,
    QLineEdit, QPlainTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QBrush, QIcon, QPen

#
# 這個檔案包含了所有自訂的 UI 元件。
# 將它們獨立出來，可以讓主視窗的程式碼更乾淨，也方便未來在其他地方重複使用這些元件。
#

# --- 自訂渲染代理 (Delegate for ComboBox) ---
class CustomComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_colors = {}

    def setThemeColors(self, colors):
        self.theme_colors = colors

    def paint(self, painter, option, index):
        text = index.data(Qt.DisplayRole)
        is_available = index.data(Qt.UserRole)
        is_enabled = index.flags() & Qt.ItemIsEnabled

        bg_color = QColor(self.theme_colors.get("BG_PRIMARY"))
        if option.state & QStyle.State_Selected:
            bg_color = QColor(self.theme_colors["ACCENT"])
        elif option.state & QStyle.State_MouseOver:
            bg_color = QColor(self.theme_colors.get("BG_SECONDARY"))
        
        painter.fillRect(option.rect, bg_color)

        if not is_enabled or (isinstance(is_available, bool) and not is_available):
            text_color = QColor(self.theme_colors.get("TEXT_DISABLED"))
        elif option.state & QStyle.State_Selected:
            text_color = QColor(self.theme_colors["ON_ACCENT"])
        else:
            text_color = QColor(self.theme_colors.get("TEXT_PRIMARY"))
            
        painter.setPen(text_color)
        text_rect = option.rect.adjusted(5, 0, 0, 0)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)

# --- 自訂對話框基底類別 (已更新) ---
class CustomDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CustomDialog")
        self.setModal(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.bg_color = QColor("#ffffff")
        self.border_color = QColor("#e2e8f0")
        
        self.dragging = False
        self.offset = None

    def setThemeColors(self, colors):
        self.bg_color = QColor(colors.get("BG_PRIMARY", "#ffffff"))
        self.border_color = QColor(colors.get("BORDER_PRIMARY", "#e2e8f0"))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(self.bg_color))
        pen = QPen(self.border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            interactive_widgets = (QPushButton, QTextEdit, QPlainTextEdit, QLineEdit, QListWidget, QComboBox, QCheckBox, QSizeGrip)
            is_interactive = False
            widget = child
            while widget is not None:
                if isinstance(widget, interactive_widgets):
                    is_interactive = True
                    break
                widget = widget.parent()
            
            if not is_interactive:
                 self.dragging = True
                 self.offset = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(self.mapToParent(event.pos() - self.offset))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            self.offset = None
        super().mouseReleaseEvent(event)

# --- 自訂訊息框 (已更新) ---
class CustomMessageBox(CustomDialog):
    def __init__(self, parent, icon_type, title, text, buttons):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        self.icon_label = QLabel()
        pixmap_size = 32 if icon_type == "question" else 48
        self.icon_label.setPixmap(QIcon(parent.get_icon_path(f"{icon_type}.svg")).pixmap(pixmap_size, pixmap_size))

        self.title_label = QLabel(title, objectName="DialogTitleLabel")
        self.text_label = QLabel(text, objectName="MessageBoxText")
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignTop)

        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        text_layout = QVBoxLayout()
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.text_label)
        text_layout.addStretch()

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 10)
        main_layout.setSpacing(15)
        main_layout.addWidget(self.icon_label, alignment=Qt.AlignTop)
        main_layout.addLayout(text_layout)
        
        content_layout = QVBoxLayout()
        content_layout.addLayout(main_layout)
        content_layout.addWidget(self.button_box, alignment=Qt.AlignRight)
        
        final_layout = QGridLayout(self)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addLayout(content_layout, 0, 0)
        final_layout.addWidget(QSizeGrip(self), 0, 0, Qt.AlignBottom | Qt.AlignRight)

# --- 進度對話框 (已更新) ---
class ProgressDialog(CustomDialog):
    def __init__(self, parent=None, title="轉錄進行中..."):
        super().__init__(parent)
        self.setWindowTitle("處理中")
        self.setMinimumWidth(680)
        self.original_height = 180

        self.title = QLabel(title, objectName="DialogTitleLabel")
        self.info = QLabel("準備開始...", objectName="DialogInfoLabel")
        self.progressBar = QProgressBar()

        self.tabWidget = QTabWidget()
        self.tabWidget.setVisible(False)

        self.subtitleView = QTextEdit(objectName="LogView")
        self.subtitleView.setReadOnly(True)
        self.subtitleTab = self.tabWidget.addTab(self.subtitleView, "轉錄進度")

        self.logView = QTextEdit(objectName="LogView")
        self.logView.setReadOnly(True)
        self.logTab = self.tabWidget.addTab(self.logView, "詳細日誌")

        self.toggleLogButton = QPushButton("顯示詳細資訊 ▼")
        self.toggleLogButton.clicked.connect(self.toggle_log_view)
        
        self.cancelButton = QPushButton("取消")
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.toggleLogButton)
        button_layout.addStretch()
        button_layout.addWidget(self.cancelButton)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.addWidget(self.title, alignment=Qt.AlignCenter)
        content_layout.addSpacing(10)
        content_layout.addWidget(self.info)
        content_layout.addWidget(self.progressBar)
        content_layout.addWidget(self.tabWidget)
        content_layout.addSpacing(10)
        content_layout.addLayout(button_layout)
        
        final_layout = QGridLayout(self)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addLayout(content_layout, 0, 0)
        final_layout.addWidget(QSizeGrip(self), 0, 0, Qt.AlignBottom | Qt.AlignRight)

    def retranslate_ui(self, translations):
        """套用翻譯"""
        self.info.setText(translations['preparing_start'])
        self.toggleLogButton.setText(translations['show_details_button'])
        self.cancelButton.setText(translations['cancel_button'])
        self.tabWidget.setTabText(self.subtitleTab, "轉錄進度") # 暫不翻譯
        self.tabWidget.setTabText(self.logTab, translations['detailed_log_tab'])

    def set_indeterminate(self, is_indeterminate):
        """將進度條設置為確定或不確定模式。"""
        if is_indeterminate:
            self.progressBar.setRange(0, 0)
            self.progressBar.setTextVisible(False)
        else:
            self.progressBar.setRange(0, 100)
            self.progressBar.setTextVisible(True)

    def toggle_log_view(self):
        is_visible = self.tabWidget.isVisible()
        self.tabWidget.setVisible(not is_visible)
        # 這裡的文字需要從主視窗傳入
        parent_trans = self.parent().translations
        self.toggleLogButton.setText(parent_trans['hide_details_button'] if not is_visible else parent_trans['show_details_button'])
        self.adjustSize()

    def update_progress(self, value, text):
        if self.progressBar.maximum() != 0: # 檢查是否為不確定模式
            self.progressBar.setValue(value)
        self.info.setText(text)

    def add_log_message(self, message):
        self.logView.append(message)
        self.logView.ensureCursorVisible()

    def add_subtitle_message(self, message):
        self.subtitleView.append(message)
        self.subtitleView.ensureCursorVisible()

    def clear_logs(self):
        self.logView.clear()
        self.subtitleView.clear()

# --- 結果對話框 (已修改) ---
class ResultDialog(CustomDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 460)

        self.iconLabel = QLabel(objectName="SuccessIcon")
        self.titleLabel = QLabel(objectName="DialogTitleLabel")
        
        header_layout = QVBoxLayout()
        header_layout.addWidget(self.iconLabel, alignment=Qt.AlignCenter)
        header_layout.addWidget(self.titleLabel, alignment=Qt.AlignCenter)

        self.tabWidget = QTabWidget()
        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        self.timeList = QListWidget(objectName="ResultList")
        self.summaryFileCountLabel = QLabel()
        self.summaryFileCount = QLabel()
        self.summaryTotalTimeLabel = QLabel()
        self.summaryTotalTime = QLabel()
        self.summaryBackendLabel = QLabel()
        self.summaryBackend = QLabel()
        
        summary_grid_layout = QGridLayout()
        summary_grid_layout.addWidget(self.summaryFileCountLabel, 0, 0)
        summary_grid_layout.addWidget(self.summaryFileCount, 0, 1, alignment=Qt.AlignRight)
        summary_grid_layout.addWidget(self.summaryTotalTimeLabel, 1, 0)
        summary_grid_layout.addWidget(self.summaryTotalTime, 1, 1, alignment=Qt.AlignRight)
        summary_grid_layout.addWidget(self.summaryBackendLabel, 2, 0)
        summary_grid_layout.addWidget(self.summaryBackend, 2, 1, alignment=Qt.AlignRight)

        summary_layout.addWidget(self.timeList)
        summary_layout.addLayout(summary_grid_layout)
        self.summaryTabIndex = self.tabWidget.addTab(summary_widget, "結果摘要")

        self.logView = QTextEdit()
        self.logView.setReadOnly(True)
        self.logTabIndex = self.tabWidget.addTab(self.logView, "詳細日誌")
        self.tabWidget.setTabVisible(self.logTabIndex, False)

        self.okButton = QPushButton()
        self.okButton.clicked.connect(self.accept)
        from core.ai_translations import ai_strings
        self.aiButton = QPushButton(ai_strings(getattr(parent, 'current_lang', 'zh_TW'))['optimize'])
        self.aiButton.setEnabled(False)
        self.aiButton.clicked.connect(self.open_optimization)
        self.file_results = []
        self.ai_dialog = None

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.addLayout(header_layout)
        content_layout.addWidget(self.tabWidget)
        actions = QHBoxLayout()
        actions.addWidget(self.aiButton)
        actions.addStretch()
        actions.addWidget(self.okButton)
        content_layout.addLayout(actions)
        
        final_layout = QGridLayout(self)
        final_layout.setContentsMargins(0, 0, 0, 0)
        final_layout.addLayout(content_layout, 0, 0)
        final_layout.addWidget(QSizeGrip(self), 0, 0, Qt.AlignBottom | Qt.AlignRight)
    
    def retranslate_ui(self, translations, title):
        """套用翻譯"""
        self.setWindowTitle(title)
        self.titleLabel.setText(title)
        self.tabWidget.setTabText(self.summaryTabIndex, translations['result_summary_tab'])
        self.tabWidget.setTabText(self.logTabIndex, translations['detailed_log_tab'])
        self.summaryFileCountLabel.setText(translations['total_files_processed_label'])
        self.summaryTotalTimeLabel.setText(translations['total_time_label'])
        self.summaryBackendLabel.setText(translations['compute_mode_result_label'])
        self.okButton.setText(translations['ok_button'])

    def set_results(self, file_times, total_time, backend, detailed_log="", success=True):
        def format_time(s):
            h = int(s / 3600); m = int((s % 3600) / 60); s = int(s % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"

        if success and len(file_times) > 1:
            self.timeList.setVisible(True)
            for filename, t in file_times:
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(5, 5, 5, 5)
                item_layout.addWidget(QLabel(os.path.basename(filename)))
                item_layout.addStretch()
                time_label = QLabel(format_time(t))
                item_layout.addWidget(time_label)
                
                list_item = QListWidgetItem(self.timeList)
                list_item.setSizeHint(item_widget.sizeHint())
                self.timeList.addItem(list_item)
                self.timeList.setItemWidget(list_item, item_widget)
        else:
            self.timeList.setVisible(False)

        self.summaryFileCount.setText(f"{len(file_times)}")
        self.summaryTotalTime.setText(format_time(total_time))
        self.summaryBackend.setText(backend)

        if detailed_log:
            self.logView.setText(detailed_log)
            self.tabWidget.setTabVisible(self.logTabIndex, True)
            if not success:
                self.tabWidget.setCurrentIndex(self.logTabIndex)

    def set_file_details(self, file_results, translations):
        """為每個處理過的檔案各加一個分頁，保留字幕內容與處理細節。"""
        self.file_results = list(file_results)
        self.aiButton.setEnabled(any(item.get('success') and item.get('srt') for item in file_results))
        def format_time(s):
            h = int(s / 3600); m = int((s % 3600) / 60); s = int(s % 60)
            return f"{h:02d}:{m:02d}:{s:02d}"

        for res in file_results:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(6)

            if res.get("success"):
                info_parts = [f"{translations['file_time_label']}: {format_time(res.get('time', 0))}"]
                outputs = res.get("outputs") or []
                if outputs:
                    names = ", ".join(os.path.basename(p) for p in outputs)
                    info_parts.append(f"{translations['output_files_label']}: {names}")
                info_text = "　".join(info_parts)
            else:
                info_text = translations['file_detail_failed']

            info_label = QLabel(info_text, objectName="DialogInfoLabel")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)

            text_view = QTextEdit(objectName="LogView")
            text_view.setReadOnly(True)
            if res.get("success") and res.get("subtitles"):
                content = "\n".join(res["subtitles"])
            else:
                content = "\n".join(res.get("log") or [])
            text_view.setText(content or translations['no_subtitles_captured'])
            layout.addWidget(text_view)

            base_name = os.path.splitext(os.path.basename(res.get("file", "")))[0]
            tab_title = base_name if len(base_name) <= 14 else base_name[:13] + "…"
            if not res.get("success"):
                tab_title = "⚠ " + tab_title
            # 插在「詳細日誌」分頁之前，順序為：摘要、各檔案、詳細日誌
            index = self.tabWidget.insertTab(self.tabWidget.count() - 1, page, tab_title)
            self.tabWidget.setTabToolTip(index, os.path.basename(res.get("file", "")))

    def open_optimization(self):
        from .ai_dialog import OptimizeDialog
        if self.ai_dialog is None:
            self.ai_dialog = OptimizeDialog(self.parent(), self.file_results, self)
        self.ai_dialog.refresh_destination()
        self.ai_dialog.exec_()
