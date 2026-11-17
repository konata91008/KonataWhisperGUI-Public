import threading
import urllib.error

from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QApplication, QLabel, QPushButton, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QDialogButtonBox, QProgressBar)

from core.release_updater import ReleaseUpdater, RELEASES_URL, launch_installer
from core.release_translations import release_strings
from core.updater import UpdateError
from core.version import VERSION_TEXT
from .widgets import CustomDialog, CustomMessageBox


def app_busy(window):
    return (any(page.is_busy() for page in (window.conversionTab, window.diagnosticsTab, window.encodingTab))
            or bool(window.setup_dialog and window.setup_dialog.is_busy())
            or window.is_downloading or bool(window.worker and window.worker.isRunning()))


class ReleaseWorker(QThread):
    progress = pyqtSignal(int, int)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.operation(self.progress.emit)
        except UpdateError as error:
            self.error = error.code
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            self.error = 'network_error'
        except Exception:
            self.error = 'operation_failed'


class ReleaseUpdateDialog(CustomDialog):
    def __init__(self, parent, updater=None):
        super().__init__(parent)
        self.main_window = parent
        self.texts = release_strings(parent.current_lang)
        self.worker = None
        self.operation = ''
        self.info = None
        self.downloaded = None
        self.cancel_event = threading.Event()
        try:
            self.updater = updater or ReleaseUpdater()
        except UpdateError:
            self.updater = None
        self.setWindowTitle(self.texts['title'])
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumWidth(580)
        self.setStyleSheet(parent.styleSheet())
        self.setThemeColors(parent.current_colors)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(QLabel(self.texts['title'], objectName='DialogTitleLabel'))
        layout.addWidget(QLabel(self.texts['current'].format(version=VERSION_TEXT)))
        layout.addWidget(QLabel(self.texts['source']))
        self.status = QLabel(self.texts['check'] if self.updater else self.texts['unsupported_platform'])
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.details = QTextEdit(objectName='UpdateDetails')
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(160)
        layout.addWidget(self.details)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.check_button = QPushButton(self.texts['check'])
        self.download_button = QPushButton(self.texts['download'], objectName='PrimaryButton')
        kind = self.updater.kind if self.updater else ''
        self.apply_button = QPushButton(self.texts['install' if kind == 'windows-setup' else
            'open_zip' if kind == 'windows-portable' else 'open_dmg'], objectName='PrimaryButton')
        self.cancel_button = QPushButton(self.texts['cancel'])
        self.page_button = QPushButton(self.texts['release_page'])
        self.close_button = QPushButton(self.texts['close'])
        # Two rows keep long English/Japanese labels readable at Windows DPI scaling.
        for buttons in ((self.check_button, self.download_button, self.apply_button, self.cancel_button),
                        (self.page_button, self.close_button)):
            row = QHBoxLayout()
            for button in buttons:
                row.addWidget(button)
            layout.addLayout(row)
        self.check_button.clicked.connect(self.check)
        self.download_button.clicked.connect(self.download)
        self.apply_button.clicked.connect(self.confirm_apply)
        self.cancel_button.clicked.connect(self.cancel)
        self.page_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(RELEASES_URL + '/latest')))
        self.close_button.clicked.connect(self.reject)
        self.refresh_buttons()

    def is_busy(self):
        return self.worker is not None

    def refresh_buttons(self):
        busy = self.is_busy()
        self.check_button.setEnabled(not busy and self.updater is not None)
        self.download_button.setVisible(self.downloaded is None)
        self.download_button.setEnabled(not busy and self.info is not None and self.info.available)
        self.apply_button.setVisible(self.downloaded is not None)
        self.apply_button.setEnabled(not busy)
        self.cancel_button.setVisible(busy and self.operation == 'download')
        self.cancel_button.setEnabled(not self.cancel_event.is_set())
        self.page_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)

    def start(self, name, operation, callback):
        if self.is_busy():
            return
        self.operation = name
        self.callback = callback
        self.worker = ReleaseWorker(operation, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.finished_operation)
        self.refresh_buttons()
        self.worker.start()

    def finished_operation(self):
        worker = self.worker
        self.worker = None
        self.progress.hide()
        error = worker.error
        if self.operation == 'download' and self.cancel_event.is_set():
            error = 'cancelled'
        if error:
            if self.operation == 'verify':
                self.downloaded = None
            self.status.setText(self.texts.get(error, self.texts['operation_failed']))
        else:
            self.callback(worker.result)
        worker.deleteLater()
        self.refresh_buttons()

    def check(self):
        if self.is_busy() or self.updater is None:
            return
        self.info = None
        self.downloaded = None
        self.details.clear()
        self.status.setText(self.texts['checking'])
        self.start('check', lambda progress: self.updater.check(), self.on_checked)

    def on_checked(self, info):
        self.info = info
        self.status.setText(self.texts['available'].format(version=info.version, date=info.date)
                            if info.available else self.texts['latest'])
        self.details.setPlainText(info.notes)

    def download(self):
        if self.is_busy() or not self.info or not self.info.available:
            return
        self.cancel_event.clear()
        self.status.setText(self.texts['preparing'])
        self.progress.setValue(0)
        self.progress.show()
        info = self.info
        self.start('download', lambda progress: self.updater.download(info, self.cancel_event, progress), self.on_downloaded)

    def on_progress(self, done, total):
        self.progress.setValue(int(done * 100 / total))
        self.status.setText(self.texts['downloading'].format(done=done / 1048576, total=total / 1048576))

    def on_downloaded(self, downloaded):
        self.downloaded = downloaded
        self.status.setText(self.texts['verified'])
        kind = downloaded.info.kind
        self.details.setPlainText(self.texts['macos' if kind.startswith('macos-') else kind]
                                  + '\n\n' + str(downloaded.path))

    def cancel(self):
        if self.operation == 'download' and self.is_busy():
            self.cancel_event.set()
            self.cancel_button.setEnabled(False)

    def confirm_apply(self):
        if self.is_busy() or self.downloaded is None:
            return
        if app_busy(self.main_window):
            self.status.setText(self.texts['busy'])
            return
        kind = self.downloaded.info.kind
        message = self.texts['confirm'] + '\n\n' + self.texts['macos' if kind.startswith('macos-') else kind]
        dialog = CustomMessageBox(self.main_window, 'question', self.texts['confirm_title'], message,
                                  QDialogButtonBox.Yes | QDialogButtonBox.No)
        dialog.setStyleSheet(self.styleSheet())
        dialog.setThemeColors(self.main_window.current_colors)
        dialog.button_box.button(QDialogButtonBox.Yes).setText(self.texts['continue'])
        no_button = dialog.button_box.button(QDialogButtonBox.No)
        no_button.setText(self.texts['later'])
        no_button.setDefault(True)
        accepted = dialog.exec_() == dialog.Accepted
        dialog.deleteLater()
        if accepted:
            self.status.setText(self.texts['verifying'])
            self.start('verify', lambda progress: self.updater.verify(self.downloaded), self.launch)

    def launch(self, downloaded):
        if app_busy(self.main_window):
            self.status.setText(self.texts['busy'])
            return
        try:
            # Save preferences before handing off. Never close the app on launch failure.
            self.main_window.save_settings()
            kind = downloaded.info.kind
            if kind == 'windows-setup':
                launch_installer(downloaded)
            else:
                path = downloaded.path.parent if kind == 'windows-portable' else downloaded.path
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                    raise UpdateError('launch_failed')
        except (OSError, UpdateError) as error:
            self.status.setText(self.texts.get(getattr(error, 'code', ''), self.texts['launch_failed']))
            return
        self.accept()
        self.main_window.close()
        QApplication.instance().quit()

    def reject(self):
        if not self.is_busy():
            super().reject()

    def closeEvent(self, event):
        if self.is_busy():
            event.ignore()
        else:
            super().closeEvent(event)
