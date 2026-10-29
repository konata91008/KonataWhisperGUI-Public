from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QTextEdit, QDialogButtonBox
from .widgets import CustomDialog, CustomMessageBox
from core.updater import GitUpdater, UpdateError
from core.version import PROJECT_ROOT, VERSION_TEXT
from core.update_translations import update_strings


class UpdateWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            self.succeeded.emit(self.operation())
        except UpdateError as error:
            self.failed.emit(error.code)
        except Exception:
            self.failed.emit('git_failed')


class UpdateDialog(CustomDialog):
    def __init__(self, parent, updater=None):
        super().__init__(parent)
        self.main_window = parent
        self.texts = update_strings(parent.current_lang)
        self.updater = updater or GitUpdater(PROJECT_ROOT)
        self.worker = None
        self.info = None
        self.installed = parent.update_pending_restart
        self.setWindowTitle(self.texts['title'])
        self.setMinimumWidth(520)
        self.setStyleSheet(parent.styleSheet())
        self.setThemeColors(parent.current_colors)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        title = QLabel(self.texts['title'], objectName='DialogTitleLabel')
        layout.addWidget(title)
        layout.addWidget(QLabel(self.texts['current'].format(version=VERSION_TEXT)))
        layout.addWidget(QLabel(self.texts['source']))
        self.status = QLabel(self.texts['success'] if self.installed else self.texts['check'])
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.details = QTextEdit(objectName='UpdateDetails')
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(135)
        layout.addWidget(self.details)
        row = QHBoxLayout()
        self.check_button = QPushButton(self.texts['check'])
        self.apply_button = QPushButton(self.texts['update'], objectName='PrimaryButton')
        self.restart_button = QPushButton(self.texts['restart'], objectName='PrimaryButton')
        self.close_button = QPushButton(self.texts['close'])
        for button in (self.check_button, self.apply_button, self.restart_button, self.close_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.check_button.clicked.connect(self.check)
        self.apply_button.clicked.connect(self.confirm_update)
        self.restart_button.clicked.connect(parent.restart_application)
        self.close_button.clicked.connect(self.reject)
        self.refresh_buttons()

    def is_busy(self):
        return self.worker is not None

    def refresh_buttons(self):
        busy = self.is_busy()
        self.check_button.setVisible(not self.installed)
        self.apply_button.setVisible(not self.installed)
        self.restart_button.setVisible(self.installed)
        self.check_button.setEnabled(not busy)
        self.apply_button.setEnabled(not busy and self.info is not None and self.info.can_update)
        self.restart_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)
        self.close_button.setText(self.texts['later'] if self.installed else self.texts['close'])

    def run_operation(self, operation, callback):
        if self.is_busy():
            return
        self.worker = UpdateWorker(operation, self)
        self.worker.succeeded.connect(callback)
        self.worker.failed.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.refresh_buttons()
        self.worker.start()

    def on_finished(self):
        worker = self.worker
        self.worker = None
        worker.deleteLater()
        self.refresh_buttons()

    def check(self):
        if self.is_busy() or self.installed:
            return
        self.info = None
        self.status.setText(self.texts['checking'])
        self.details.clear()
        self.run_operation(self.updater.check, self.on_checked)

    def on_checked(self, info):
        self.info = info
        key = {'current': 'latest', 'available': 'available', 'ahead': 'ahead', 'diverged': 'diverged'}[info.status]
        self.status.setText(self.texts[key].format(version=info.version, date=info.date))
        paragraphs = []
        if info.blocker:
            paragraphs.append(self.texts[info.blocker])
        if info.runtime_changes and info.status == 'available':
            paragraphs.append(self.texts['runtime'])
        if info.summary:
            paragraphs.append(info.summary)
        self.details.setPlainText('\n\n'.join(paragraphs))

    def confirm_update(self):
        if self.is_busy() or not self.info or not self.info.can_update:
            return
        message = self.texts['confirm'].format(version=self.info.version)
        if self.info.runtime_changes:
            message += '\n\n' + self.texts['runtime']
        dialog = CustomMessageBox(self.main_window, 'question', self.texts['confirm_title'], message,
                                  QDialogButtonBox.Yes | QDialogButtonBox.No)
        dialog.setStyleSheet(self.styleSheet())
        dialog.setThemeColors(self.main_window.current_colors)
        dialog.button_box.button(QDialogButtonBox.Yes).setText(self.texts['yes'])
        no_button = dialog.button_box.button(QDialogButtonBox.No)
        no_button.setText(self.texts['no'])
        no_button.setDefault(True)
        if dialog.exec_() == dialog.Accepted:
            info = self.info
            self.status.setText(self.texts['updating'])
            self.run_operation(lambda: self.updater.apply(info), self.on_applied)

    def on_applied(self, info):
        self.installed = True
        self.main_window.update_pending_restart = True
        self.status.setText(self.texts['success'])
        self.details.setPlainText(self.texts['available'].format(version=info.version, date=info.date))
        if info.runtime_changes:
            self.details.append(self.texts['runtime'])

    def on_error(self, code):
        self.info = None
        self.status.setText(self.texts.get(code, self.texts['git_failed']))

    def reject(self):
        if not self.is_busy():
            super().reject()

    def closeEvent(self, event):
        if self.is_busy():
            event.ignore()
        else:
            super().closeEvent(event)
