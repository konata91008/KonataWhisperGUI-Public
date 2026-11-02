from pathlib import Path
from urllib.parse import urlsplit

from PyQt5.QtCore import QIODevice, QSaveFile, QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QVBoxLayout, QWidget, QFrame, QSizePolicy,
)

from core.chinese_conversion import ConversionError, convert_text, read_text_file
from core.conversion_translations import conversion_strings
from core.interface_translations import interface_strings
from core.ai_translations import ai_strings
from core.language_translation import LANGUAGES, prepare_translation, translation_prompt, translate_text
from core.subtitle_ai import AIError, Cancelled


class ConversionWorker(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, text, direction, parent, *, config=None, source='auto', target='en', format_hint=None):
        super().__init__(parent)
        self.text, self.direction = text, direction
        self.config, self.source, self.target = config, source, target
        self.format_hint = format_hint

    def run(self):
        try:
            if self.direction == 'translate':
                result = translate_text(self.text, self.source, self.target, self.config,
                                        format_hint=self.format_hint, cancelled=self.isInterruptionRequested,
                                        progress=self.progress.emit)
                if self.isInterruptionRequested():
                    raise Cancelled()
            else:
                result = convert_text(self.text, self.direction)
            self.succeeded.emit(result)
        except ConversionError as error:
            self.failed.emit(str(error))
        except Cancelled:
            self.failed.emit('cancelled')
        except AIError as error:
            self.failed.emit('api:' + str(error))
        except Exception:
            self.failed.emit('unexpected')
        finally:
            self.text = ''
            self.config = None


class ConversionTab(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.worker = None
        self.source_path = None
        self.status_key, self.status_values = 'ready', {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        heading = QHBoxLayout()
        self.headingLabel = QLabel(objectName='PageHeading')
        self.offlineBadge = QLabel(objectName='OfflineBadge')
        heading.addWidget(self.headingLabel)
        heading.addStretch()
        heading.addWidget(self.offlineBadge)
        layout.addLayout(heading)
        self.hint = QLabel(objectName='SubtleLabel')
        self.hint.setWordWrap(True)
        self.hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.hint)

        toolbar_card = QFrame(objectName='ToolbarCard')
        toolbar = QHBoxLayout(toolbar_card)
        toolbar.setContentsMargins(14, 10, 14, 10)
        toolbar.setSpacing(10)
        self.directionLabel = QLabel()
        self.directionCombo = QComboBox()
        self.directionCombo.addItem('', 't2s')
        self.directionCombo.addItem('', 's2t')
        self.directionCombo.addItem('', 'translate')
        self.importButton = QPushButton()
        self.clearButton = QPushButton()
        toolbar.addWidget(self.directionLabel)
        toolbar.addWidget(self.directionCombo, 1)
        toolbar.addSpacing(18)
        toolbar.addWidget(self.importButton)
        toolbar.addWidget(self.clearButton)
        layout.addWidget(toolbar_card)

        self.translationPanel = QFrame(objectName='ToolbarCard')
        translation_layout = QVBoxLayout(self.translationPanel)
        translation_layout.setContentsMargins(14, 10, 14, 10)
        translation_layout.setSpacing(8)
        languages = QHBoxLayout()
        self.sourceLanguageLabel, self.targetLanguageLabel = QLabel(), QLabel()
        self.sourceLanguageCombo, self.targetLanguageCombo = QComboBox(), QComboBox()
        self.sourceLanguageCombo.addItem('', 'auto')
        for code, (name, _) in LANGUAGES.items():
            self.sourceLanguageCombo.addItem(name, code)
            self.targetLanguageCombo.addItem(name, code)
        self.targetLanguageCombo.setCurrentIndex(self.targetLanguageCombo.findData('en'))
        self.apiButton = QPushButton()
        languages.addWidget(self.sourceLanguageLabel)
        languages.addWidget(self.sourceLanguageCombo, 1)
        languages.addWidget(QLabel('→'))
        languages.addWidget(self.targetLanguageLabel)
        languages.addWidget(self.targetLanguageCombo, 1)
        languages.addWidget(self.apiButton)
        self.destinationLabel = QLabel(objectName='SubtleLabel')
        self.destinationLabel.setTextFormat(Qt.PlainText)
        self.destinationLabel.setWordWrap(True)
        self.destinationLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        translation_layout.addLayout(languages)
        translation_layout.addWidget(self.destinationLabel)
        layout.addWidget(self.translationPanel)

        editors = QHBoxLayout()
        editors.setSpacing(16)
        self.sourceLabel, self.resultLabel = QLabel(objectName="SectionTitle"), QLabel(objectName="SectionTitle")
        self.sourceEdit, self.resultEdit = QPlainTextEdit(objectName="ConversionSource"), QPlainTextEdit(objectName="ConversionResult")
        # File imports are explicit; dropping a URL must not insert its path.
        self.sourceEdit.setAcceptDrops(False)
        self.resultEdit.setReadOnly(True)
        for title, editor in ((self.sourceLabel, self.sourceEdit), (self.resultLabel, self.resultEdit)):
            card = QFrame(objectName='EditorCard')
            column = QVBoxLayout(card)
            column.setContentsMargins(18, 12, 18, 10)
            column.setSpacing(8)
            title.setBuddy(editor)
            editor.setMinimumHeight(100)
            editor.document().setDocumentMargin(6)
            column.addWidget(title)
            column.addWidget(editor, 1)
            editors.addWidget(card, 1)
        layout.addLayout(editors, 1)

        self.countLabel = QLabel(objectName='SubtleLabel')
        self.statusLabel = QLabel(objectName='ConversionStatus')
        self.statusLabel.setTextFormat(Qt.PlainText)
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        feedback = QHBoxLayout()
        feedback.setSpacing(16)
        feedback.addWidget(self.statusLabel, 1)
        feedback.addWidget(self.countLabel, 0, Qt.AlignRight)
        layout.addLayout(feedback)
        actions = QHBoxLayout()
        self.convertButton = QPushButton(objectName='PrimaryButton')
        self.convertButton.setMinimumWidth(170)
        self.cancelButton = QPushButton()
        self.copyButton, self.saveButton = QPushButton(), QPushButton()
        actions.addWidget(self.convertButton)
        actions.addWidget(self.cancelButton)
        actions.addStretch()
        actions.addWidget(self.copyButton)
        actions.addWidget(self.saveButton)
        layout.addLayout(actions)

        self.sourceEdit.textChanged.connect(self.invalidate_result)
        self.directionCombo.currentIndexChanged.connect(self.mode_changed)
        self.sourceLanguageCombo.currentIndexChanged.connect(self.invalidate_result)
        self.targetLanguageCombo.currentIndexChanged.connect(self.invalidate_result)
        self.apiButton.clicked.connect(owner.open_api_settings)
        self.cancelButton.clicked.connect(self.cancel_translation)
        self.importButton.clicked.connect(self.import_text)
        self.clearButton.clicked.connect(self.clear)
        self.convertButton.clicked.connect(self.start_conversion)
        self.copyButton.clicked.connect(self.copy_result)
        self.saveButton.clicked.connect(self.save_result)
        self.retranslate_ui(owner.current_lang)

    def retranslate_ui(self, language):
        self.t = conversion_strings(language)
        appearance = interface_strings(language)
        self.headingLabel.setText(appearance['conversion_title'])
        self.directionLabel.setText(self.t['direction'])
        self.directionCombo.setAccessibleName(self.t['direction'])
        for index in range(self.directionCombo.count()):
            self.directionCombo.setItemText(index, self.t[self.directionCombo.itemData(index)])
        self.sourceLanguageCombo.setItemText(0, self.t['auto_detect'])
        for widget, key in ((self.sourceLabel, 'source'), (self.resultLabel, 'result'),
                            (self.importButton, 'import'), (self.clearButton, 'clear'),
                            (self.copyButton, 'copy'), (self.saveButton, 'save'),
                            (self.apiButton, 'api_settings'), (self.cancelButton, 'cancel'),
                            (self.sourceLanguageLabel, 'source_language'), (self.targetLanguageLabel, 'target_language')):
            widget.setText(self.t[key])
        self.sourceLanguageLabel.setBuddy(self.sourceLanguageCombo)
        self.targetLanguageLabel.setBuddy(self.targetLanguageCombo)
        self.sourceLanguageCombo.setAccessibleName(self.t['source_language'])
        self.targetLanguageCombo.setAccessibleName(self.t['target_language'])
        self.sourceEdit.setAccessibleName(self.t['source'])
        self.resultEdit.setAccessibleName(self.t['result'])
        self.sourceEdit.setPlaceholderText(self.t['source_placeholder'])
        self.resultEdit.setPlaceholderText(self.t['result_placeholder'])
        self.set_status(self.status_key, **self.status_values)
        self.refresh_service()
        self.refresh_controls()

    def is_translation(self):
        return self.directionCombo.currentData() == 'translate'

    def mode_changed(self, *_):
        self.refresh_service()
        self.invalidate_result()

    def refresh_service(self):
        translating = self.is_translation()
        appearance = interface_strings(self.owner.current_lang)
        self.translationPanel.setVisible(translating)
        self.offlineBadge.setText('●  ' + (self.t['api_badge'] if translating else appearance['offline']))
        self.offlineBadge.setProperty('remote', translating)
        self.offlineBadge.style().unpolish(self.offlineBadge)
        self.offlineBadge.style().polish(self.offlineBadge)
        self.hint.setText(self.t['api_hint'] if translating else appearance['conversion_hint'])
        self.hint.setToolTip(self.t['api_hint'] if translating else self.t['hint'])
        try:
            config = self.owner.api_config
            endpoint = config.validate()
            self.destinationLabel.setText(self.t['api_destination'].format(host=urlsplit(endpoint).netloc, model=config.model))
        except AIError:
            self.destinationLabel.setText(self.t['api_missing'])

    def is_busy(self):
        return self.worker is not None

    def set_status(self, key, **values):
        self.status_key, self.status_values = key, values
        message = self.t.get('translation_ready' if key == 'ready' and self.is_translation() else key)
        if message is None and key.startswith('api:'):
            message = ai_strings(self.owner.current_lang).get(key[4:])
        self.statusLabel.setText((message or self.t['unexpected']).format(**values))
        state = 'success' if key in ('done', 'translation_done', 'copied', 'saved') else ('neutral' if key in (
            'ready', 'loaded', 'working', 'translation_working', 'translation_progress', 'cancelled', 'cancelling') else 'error')
        self.statusLabel.setProperty('state', state)
        self.statusLabel.style().unpolish(self.statusLabel)
        self.statusLabel.style().polish(self.statusLabel)

    def refresh_controls(self):
        busy = self.is_busy()
        source, result = self.sourceEdit.toPlainText(), self.resultEdit.toPlainText()
        self.sourceEdit.setReadOnly(busy)
        for widget in (self.directionCombo, self.importButton, self.clearButton,
                       self.sourceLanguageCombo, self.targetLanguageCombo, self.apiButton):
            widget.setEnabled(not busy)
        self.convertButton.setEnabled(not busy and bool(source.strip()))
        if self.is_translation():
            self.convertButton.setText(self.t['translation_working' if busy else 'start_translation'])
        else:
            self.convertButton.setText(self.t['working' if busy else 'convert'])
        self.cancelButton.setVisible(busy and self.is_translation())
        self.cancelButton.setEnabled(busy and not self.worker.isInterruptionRequested())
        self.copyButton.setEnabled(not busy and bool(result))
        self.saveButton.setEnabled(not busy and bool(result))
        self.countLabel.setText(self.t['counts'].format(source=len(source), result=len(result)))

    def invalidate_result(self, *_):
        self.resultEdit.clear()
        self.set_status('ready')
        self.refresh_controls()

    def clear(self):
        if self.is_busy():
            return
        self.source_path = None
        self.sourceEdit.clear()
        self.invalidate_result()
        self.sourceEdit.setFocus()

    def import_text(self):
        if self.is_busy():
            return
        filename, _ = QFileDialog.getOpenFileName(self, self.t['import'], '', self.t['file_filter'])
        if not filename:
            return
        try:
            content = read_text_file(filename)
        except ConversionError as error:
            self.set_status(str(error))
            return
        except OSError:
            self.set_status('read_error')
            return
        self.source_path = Path(filename).resolve()
        self.sourceEdit.setPlainText(content)
        self.set_status('loaded', name=self.source_path.name)

    def start_conversion(self):
        if self.is_busy():
            return
        text = self.sourceEdit.toPlainText()
        if not text.strip():
            self.set_status('empty')
            return
        self.resultEdit.clear()
        options = {}
        if self.is_translation():
            options = dict(config=self.owner.api_config, source=self.sourceLanguageCombo.currentData(),
                           target=self.targetLanguageCombo.currentData(),
                           format_hint='srt' if self.source_path and self.source_path.suffix.lower() == '.srt' else None)
            try:
                translation_prompt(options['source'], options['target'])
                prepare_translation(text, options['format_hint'])
                options['config'].validate()
            except ConversionError as error:
                self.set_status(str(error))
                self.refresh_controls()
                return
            except AIError as error:
                self.set_status('api:' + str(error))
                self.refresh_controls()
                return
        worker = ConversionWorker(text, self.directionCombo.currentData(), self, **options)
        self.worker = worker
        worker.succeeded.connect(self.conversion_succeeded)
        worker.failed.connect(self.set_status)
        worker.progress.connect(self.translation_progress)
        worker.finished.connect(self.conversion_finished)
        self.set_status('translation_working' if self.is_translation() else 'working')
        self.refresh_controls()
        worker.start()

    def conversion_succeeded(self, text):
        # A cancellation can arrive after the worker emitted its queued result.
        if self.worker and self.worker.isInterruptionRequested():
            self.set_status('cancelled')
            return
        self.resultEdit.setPlainText(text)
        self.set_status('translation_done' if self.is_translation() else 'done')

    def translation_progress(self, done, total):
        if self.worker and not self.worker.isInterruptionRequested():
            self.set_status('translation_progress', done=done, total=total)

    def cancel_translation(self):
        if self.worker and self.is_translation():
            self.worker.requestInterruption()
            self.cancelButton.setEnabled(False)
            self.set_status('cancelling')

    def conversion_finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.refresh_controls()

    def copy_result(self):
        if self.is_busy() or not self.resultEdit.toPlainText():
            return
        QApplication.clipboard().setText(self.resultEdit.toPlainText())
        self.set_status('copied')

    def save_result(self):
        text = self.resultEdit.toPlainText()
        if self.is_busy() or not text:
            return
        direction = ('to-' + self.targetLanguageCombo.currentData()) if self.is_translation() else self.directionCombo.currentData()
        source = self.source_path or Path('converted.txt')
        suggested = source.with_name(source.stem + '.' + direction + source.suffix)
        filename, _ = QFileDialog.getSaveFileName(self, self.t['save'], str(suggested), self.t['file_filter'])
        if not filename:
            return
        destination = Path(filename)
        try:
            if self.source_path and (destination.resolve() == self.source_path or
                    (destination.exists() and self.source_path.exists() and destination.samefile(self.source_path))):
                self.set_status('source_protected')
                return
            # QSaveFile commits atomically and preserves an existing output on
            # write failure. QFileDialog supplies the overwrite confirmation.
            output = QSaveFile(str(destination))
            if not output.open(QIODevice.WriteOnly):
                self.set_status('write_error')
                return
            raw = text.encode('utf-8')
            if output.write(raw) != len(raw):
                output.cancelWriting()
                self.set_status('write_error')
                return
            if not output.commit():
                self.set_status('write_error')
                return
        except OSError:
            self.set_status('write_error')
            return
        self.set_status('saved', name=destination.name)
