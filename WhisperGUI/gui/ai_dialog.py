"""API preferences and an explicit review-before-export subtitle workflow."""
import os
from urllib.parse import urlsplit
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                            QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
                            QProgressBar, QCheckBox)
from .widgets import CustomDialog
from core.subtitle_ai import APIConfig, PROTOCOLS, AIError, ChatClient, parse_srt, render_srt, optimize, export_optimized
from core.ai_translations import ai_strings


def theme(dialog, owner):
    dialog.setStyleSheet(owner.styleSheet())
    dialog.setThemeColors(owner.current_colors)


def label(text):
    widget = QLabel(text)
    widget.setWordWrap(True)
    return widget


class APISettingsDialog(CustomDialog):
    def __init__(self, owner, parent=None):
        super().__init__(parent or owner)
        self.owner = owner
        self.t = ai_strings(owner.current_lang)
        self.setWindowTitle(self.t['settings_title'])
        self.setMinimumWidth(580)
        self.profiles = dict(owner.api_profiles)
        self.profiles[owner.api_config.protocol] = owner.api_config
        self.protocol = owner.api_config.protocol
        self.loading = False
        theme(self, owner)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(label(self.t['settings_title']))
        layout.addWidget(label(self.t['protocol_hint']))
        form = QFormLayout()
        self.protocolCombo = QComboBox()
        for protocol, (name, _) in PROTOCOLS.items():
            self.protocolCombo.addItem(name, protocol)
        self.protocolCombo.setCurrentIndex(self.protocolCombo.findData(self.protocol))
        self.urlEdit = QLineEdit(owner.api_config.base_url)
        self.modelEdit = QLineEdit(owner.api_config.model)
        self.modelEdit.setPlaceholderText(self.t['model_hint'])
        self.keyEdit = QLineEdit(owner.api_config.api_key)
        self.keyEdit.setEchoMode(QLineEdit.Password)
        self.workspaceLabel = QLabel(self.t['workspace_label'])
        self.workspaceEdit = QLineEdit(owner.api_config.workspace_id)
        self.workspaceEdit.setPlaceholderText(self.t['workspace_hint'])
        form.addRow(self.t['protocol'], self.protocolCombo)
        form.addRow(self.t['url_label'], self.urlEdit)
        form.addRow(self.t['model_label'], self.modelEdit)
        form.addRow(self.t['key_label'], self.keyEdit)
        form.addRow(self.workspaceLabel, self.workspaceEdit)
        self.workspaceLabel.setVisible(self.protocol == 'anthropic')
        self.workspaceEdit.setVisible(self.protocol == 'anthropic')
        layout.addLayout(form)
        layout.addWidget(label(self.t['key_hint']))
        self.status = label('')
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        actions.addStretch()
        close = QPushButton(self.t['cancel'])
        close.clicked.connect(self.reject)
        self.saveButton = QPushButton(self.t['save'], objectName='PrimaryButton')
        self.saveButton.clicked.connect(self.save)
        actions.addWidget(close)
        actions.addWidget(self.saveButton)
        layout.addLayout(actions)
        self.protocolCombo.currentIndexChanged.connect(self.switch_protocol)
        self.urlEdit.textChanged.connect(self.url_changed)

    def current_config(self):
        return APIConfig(self.urlEdit.text().strip(), self.modelEdit.text().strip(),
                         self.keyEdit.text().strip(), self.protocol,
                         self.workspaceEdit.text().strip() if self.protocol == 'anthropic' else '')

    def switch_protocol(self):
        self.profiles[self.protocol] = self.current_config()
        self.protocol = self.protocolCombo.currentData()
        config = self.profiles[self.protocol]
        self.loading = True
        self.urlEdit.setText(config.base_url)
        self.modelEdit.setText(config.model)
        self.keyEdit.setText(config.api_key)
        self.workspaceEdit.setText(config.workspace_id)
        self.loading = False
        self.workspaceLabel.setVisible(self.protocol == 'anthropic')
        self.workspaceEdit.setVisible(self.protocol == 'anthropic')
        self.status.clear()

    def url_changed(self):
        if not self.loading:
            self.keyEdit.clear()
            self.status.setText(self.t['url_changed'])

    def save(self):
        config = self.current_config()
        try:
            # Allow storing URL/model before a key is available. A real request validates the key.
            config.validate(require_key=False)
        except AIError as error:
            self.status.setText(self.t.get(str(error), self.t['unexpected']))
            return
        self.profiles[self.protocol] = config
        self.owner.api_profiles = dict(self.profiles)
        self.owner.api_config = config
        self.owner.save_api_settings()
        self.accept()

    def done(self, result):
        self.keyEdit.clear()
        self.profiles.clear()
        super().done(result)


class OptimizeWorker(QThread):
    progress = pyqtSignal(int, int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, cues, config, prompt, parent=None):
        super().__init__(parent)
        self.cues, self.config, self.prompt = cues, config, prompt

    def run(self):
        try:
            result = optimize(self.cues, ChatClient(self.config), self.prompt,
                              self.isInterruptionRequested, self.progress.emit)
            if self.isInterruptionRequested():
                self.failed.emit('cancelled')
            else:
                self.succeeded.emit(result)
        except AIError as error:
            self.failed.emit(str(error))
        except Exception:
            self.failed.emit('unexpected')
        finally:
            # Do not retain instructions or the copied key on a finished worker.
            self.prompt = ''
            self.config = None


class OptimizeDialog(CustomDialog):
    def __init__(self, owner, file_results, parent=None):
        super().__init__(parent or owner)
        self.owner, self.worker = owner, None
        self.t = ai_strings(owner.current_lang)
        self.files, self.originals, self.optimized = [], [], {}
        for result in file_results:
            if not result.get('success') or not result.get('srt'):
                continue
            try:
                cues = parse_srt(result['srt'])
            except AIError:
                continue
            self.files.append(result.copy())
            self.originals.append(cues)
        self.setWindowTitle(self.t['optimize'])
        self.resize(940, 740)
        self.setMinimumSize(760, 620)
        theme(self, owner)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(label(self.t['optimize']))
        header.addStretch()
        self.settingsButton = QPushButton(self.t['settings'])
        self.settingsButton.clicked.connect(self.open_settings)
        header.addWidget(self.settingsButton)
        layout.addLayout(header)
        self.destination = label('')
        layout.addWidget(self.destination)
        file_row = QHBoxLayout()
        file_row.addWidget(label(self.t['file']))
        self.fileCombo = QComboBox()
        for item in self.files:
            self.fileCombo.addItem(os.path.basename(item['file']))
        file_row.addWidget(self.fileCombo, 1)
        layout.addLayout(file_row)
        columns = QHBoxLayout()
        self.originalView, self.optimizedView = QPlainTextEdit(), QPlainTextEdit()
        for title, view in [(self.t['original'], self.originalView), (self.t['optimized'], self.optimizedView)]:
            column = QVBoxLayout()
            column.addWidget(label(title))
            view.setReadOnly(True)
            column.addWidget(view)
            columns.addLayout(column, 1)
        self.optimizedView.setPlaceholderText(self.t['no_result'])
        layout.addLayout(columns, 1)
        layout.addWidget(label(self.t['prompt']))
        self.promptEdit = QPlainTextEdit()
        self.promptEdit.setPlaceholderText(self.t['prompt_hint'])
        self.promptEdit.setMaximumHeight(64)
        layout.addWidget(self.promptEdit)
        layout.addWidget(label(self.t['prompt_scope']))
        self.status = label(self.t['ready'] if self.files else self.t['empty'])
        layout.addWidget(self.status)
        self.progressBar = QProgressBar()
        self.progressBar.hide()
        layout.addWidget(self.progressBar)
        actions = QHBoxLayout()
        self.srtCheck, self.txtCheck = QCheckBox('SRT'), QCheckBox('TXT')
        actions.addWidget(label(self.t['formats_label']))
        actions.addWidget(self.srtCheck)
        actions.addWidget(self.txtCheck)
        actions.addStretch()
        self.closeButton = QPushButton(self.t['close'])
        self.closeButton.clicked.connect(self.reject)
        self.startButton = QPushButton(self.t['start'], objectName='PrimaryButton')
        self.startButton.clicked.connect(self.start)
        self.exportButton = QPushButton(self.t['export'])
        self.exportButton.clicked.connect(self.export)
        for button in (self.closeButton, self.startButton, self.exportButton):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.fileCombo.currentIndexChanged.connect(self.select_file)
        self.refresh_destination()
        self.select_file()

    def refresh_destination(self):
        config = self.owner.api_config
        try:
            host = urlsplit(config.endpoint()).netloc
            text = self.t['destination'].format(host=host, model=config.model) if config.model else self.t['not_configured']
        except AIError:
            text = self.t['not_configured']
        self.destination.setText(text)

    def open_settings(self):
        dialog = APISettingsDialog(self.owner, self)
        dialog.exec_()
        dialog.deleteLater()
        self.refresh_destination()

    def select_file(self, *_):
        index = self.fileCombo.currentIndex()
        if index >= 0:
            self.originalView.setPlainText(render_srt(self.originals[index]))
            self.optimizedView.setPlainText(render_srt(self.optimized[index]) if index in self.optimized else '')
            formats = self.files[index].get('formats', ('srt',))
            self.srtCheck.setChecked('srt' in formats)
            self.txtCheck.setChecked('txt' in formats)
            self.status.setText(self.t['ready'])
        self.startButton.setEnabled(index >= 0)
        self.exportButton.setEnabled(index in self.optimized)

    def is_busy(self):
        return self.worker is not None

    def start(self):
        if self.is_busy() or self.fileCombo.currentIndex() < 0:
            return
        config = self.owner.api_config
        try:
            config.validate()
        except AIError as error:
            self.status.setText(self.t.get(str(error), self.t['unexpected']))
            return
        index = self.fileCombo.currentIndex()
        prompt = self.promptEdit.toPlainText().strip()
        worker = OptimizeWorker(self.originals[index], config, prompt, self)
        self.worker = worker
        self._run_index = index
        worker.progress.connect(self.on_progress)
        worker.succeeded.connect(self.on_success)
        worker.failed.connect(self.on_failure)
        worker.finished.connect(self.on_finished)
        self.optimized.pop(index, None)
        self.optimizedView.clear()
        for widget in (self.fileCombo, self.settingsButton, self.startButton, self.exportButton, self.promptEdit):
            widget.setEnabled(False)
        self.closeButton.setText(self.t['cancel'])
        self.progressBar.setRange(0, 0)
        self.progressBar.show()
        self.status.setText(self.t['waiting'])
        worker.start()
        self.promptEdit.clear()

    def on_progress(self, done, total):
        self.progressBar.setRange(0, total)
        self.progressBar.setValue(done)
        if not self.worker.isInterruptionRequested():
            self.status.setText(self.t['working'].format(done=done, total=total))

    def on_success(self, result):
        if self.worker.isInterruptionRequested():
            self.on_failure('cancelled')
            return
        self.optimized[self._run_index] = result
        self.optimizedView.setPlainText(render_srt(result))
        self.status.setText(self.t['done'].format(count=len(result)))

    def on_failure(self, code):
        self.status.setText(self.t.get(code, self.t['unexpected']))

    def on_finished(self):
        self.worker.deleteLater()
        self.worker = None
        for widget in (self.fileCombo, self.settingsButton, self.startButton, self.promptEdit, self.closeButton):
            widget.setEnabled(True)
        self.exportButton.setEnabled(self.fileCombo.currentIndex() in self.optimized)
        self.closeButton.setText(self.t['close'])
        self.progressBar.hide()

    def export(self):
        index = self.fileCombo.currentIndex()
        if self.is_busy() or index not in self.optimized:
            return
        formats = [ext for ext, checked in [('srt', self.srtCheck.isChecked()), ('txt', self.txtCheck.isChecked())] if checked]
        try:
            paths = export_optimized(self.files[index]['output_base'], self.originals[index], self.optimized[index], formats)
        except (AIError, KeyError) as error:
            self.status.setText(self.t.get(str(error), self.t['write']))
            return
        self.status.setText(self.t['exported'].format(paths='\n'.join(paths)))

    def reject(self):
        if self.is_busy():
            self.worker.requestInterruption()
            self.status.setText(self.t['stopping'])
            self.closeButton.setEnabled(False)
            return
        self.promptEdit.clear()
        super().reject()

    def closeEvent(self, event):
        if self.is_busy():
            self.reject()
            event.ignore()
        else:
            self.promptEdit.clear()
            event.accept()
