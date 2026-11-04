"""Preview a strictly decoded subtitle and save a separate UTF-8 copy."""
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QIODevice, QSaveFile
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QPlainTextEdit, QCheckBox, QFrame, QSizePolicy, QFileDialog)

from core.encoding_translations import encoding_strings, ENCODING_LABELS
from core.interface_translations import interface_strings
from core.subtitle_encoding import (EncodingError, ENCODINGS, PREVIEW_CHARS, SUBTITLE_SUFFIXES,
                                    decode_subtitle, read_subtitle, is_source_destination)


class EncodingWorker(QThread):
    succeeded = pyqtSignal(object, object)
    failed = pyqtSignal(object, str)

    def __init__(self, path, raw, encoding, parent):
        super().__init__(parent)
        self.path, self.raw, self.encoding = path, raw, encoding

    def run(self):
        raw = self.raw
        try:
            if raw is None:
                raw = read_subtitle(self.path)
            result = decode_subtitle(raw, self.encoding)
            self.succeeded.emit(raw, result)
        except EncodingError as error:
            self.failed.emit(raw, str(error))
        except OSError:
            self.failed.emit(raw, 'read_error')
        except Exception:
            self.failed.emit(raw, 'unexpected')
        finally:
            self.raw = None


class EncodingTab(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner, self.worker = owner, None
        self.source_path = self.raw = self.result = None
        self.status_key, self.status_values = 'ready', {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        heading = QHBoxLayout()
        self.headingLabel = QLabel(objectName='PageHeading')
        self.headingLabel.setWordWrap(True)
        self.offlineBadge = QLabel(objectName='OfflineBadge')
        heading.addWidget(self.headingLabel, 1)
        heading.addWidget(self.offlineBadge)
        layout.addLayout(heading)
        self.hintLabel = self.wrapped_label('SubtleLabel')
        layout.addWidget(self.hintLabel)

        toolbar = QFrame(objectName='ToolbarCard')
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        self.importButton, self.clearButton = QPushButton(), QPushButton()
        toolbar_layout.addWidget(self.importButton)
        toolbar_layout.addWidget(self.clearButton)
        self.fileLabel = self.wrapped_label('SubtleLabel')
        toolbar_layout.addWidget(self.fileLabel, 1)
        layout.addWidget(toolbar)

        options = QGridLayout()
        options.setHorizontalSpacing(16)
        self.sourceLabel, self.outputLabel = QLabel(), QLabel()
        self.encodingCombo, self.outputCombo = QComboBox(), QComboBox()
        self.encodingCombo.addItem('', 'auto')
        for codec in ENCODINGS:
            self.encodingCombo.addItem(ENCODING_LABELS[codec], codec)
        self.outputCombo.addItem('', False)
        self.outputCombo.addItem('', True)
        for combo in (self.encodingCombo, self.outputCombo):
            combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.sourceLabel.setBuddy(self.encodingCombo)
        self.outputLabel.setBuddy(self.outputCombo)
        options.addWidget(self.sourceLabel, 0, 0)
        options.addWidget(self.outputLabel, 0, 1)
        options.addWidget(self.encodingCombo, 1, 0)
        options.addWidget(self.outputCombo, 1, 1)
        options.setColumnStretch(0, 1)
        options.setColumnStretch(1, 1)
        layout.addLayout(options)

        card = QFrame(objectName='EditorCard')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        preview_heading = QHBoxLayout()
        self.previewLabel = QLabel(objectName='SectionLabel')
        self.detectedLabel = self.wrapped_label('SubtleLabel')
        preview_heading.addWidget(self.previewLabel)
        preview_heading.addWidget(self.detectedLabel, 1)
        card_layout.addLayout(preview_heading)
        self.previewEdit = QPlainTextEdit(objectName='ConversionResult')
        self.previewEdit.setReadOnly(True)
        self.previewEdit.setAcceptDrops(False)
        self.previewEdit.setMinimumHeight(100)
        self.previewEdit.document().setDocumentMargin(6)
        card_layout.addWidget(self.previewEdit, 1)
        self.previewNote = self.wrapped_label('SubtleLabel')
        card_layout.addWidget(self.previewNote)
        layout.addWidget(card, 1)

        self.ansiHint = self.wrapped_label('SubtleLabel')
        layout.addWidget(self.ansiHint)
        self.statusLabel = self.wrapped_label('ConversionStatus')
        layout.addWidget(self.statusLabel)
        actions = QHBoxLayout()
        self.confirmCheck = QCheckBox()
        self.saveButton = QPushButton(objectName='PrimaryButton')
        actions.addWidget(self.confirmCheck)
        actions.addStretch()
        actions.addWidget(self.saveButton)
        layout.addLayout(actions)

        self.importButton.clicked.connect(self.import_subtitle)
        self.clearButton.clicked.connect(self.clear)
        self.encodingCombo.currentIndexChanged.connect(self.start_decode)
        self.confirmCheck.toggled.connect(self.refresh_controls)
        self.saveButton.clicked.connect(self.save_utf8)
        self.retranslate_ui(owner.current_lang)

    @staticmethod
    def wrapped_label(name):
        label = QLabel(objectName=name)
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        return label

    def retranslate_ui(self, language):
        self.t = encoding_strings(language)
        for widget, key in ((self.headingLabel, 'title'), (self.hintLabel, 'hint'),
                            (self.importButton, 'import'), (self.clearButton, 'clear'),
                            (self.sourceLabel, 'source_encoding'), (self.outputLabel, 'output_encoding'),
                            (self.previewLabel, 'preview'), (self.ansiHint, 'ansi_hint'),
                            (self.confirmCheck, 'confirm'), (self.saveButton, 'save')):
            widget.setText(self.t[key])
        self.offlineBadge.setText('●  ' + interface_strings(language)['offline'])
        self.encodingCombo.setItemText(0, self.t['auto'])
        self.encodingCombo.setAccessibleName(self.t['source_encoding'])
        self.outputCombo.setAccessibleName(self.t['output_encoding'])
        self.outputCombo.setItemText(0, self.t['utf8'])
        self.outputCombo.setItemText(1, self.t['utf8_bom'])
        self.outputCombo.setToolTip(self.t['bom_tip'])
        self.previewEdit.setAccessibleName(self.t['preview'])
        self.previewEdit.setPlaceholderText(self.t['preview_hint'])
        self.fileLabel.setText(self.source_path.name if self.source_path else self.t['no_file'])
        self.fileLabel.setToolTip(str(self.source_path) if self.source_path else '')
        self.show_details()
        self.set_status(self.status_key, **self.status_values)
        self.refresh_controls()

    def is_busy(self):
        return self.worker is not None

    def refresh_controls(self, *_):
        busy = self.is_busy()
        self.importButton.setEnabled(not busy)
        self.clearButton.setEnabled(not busy)
        self.encodingCombo.setEnabled(not busy and self.raw is not None)
        self.outputCombo.setEnabled(not busy)
        self.confirmCheck.setEnabled(not busy and self.result is not None)
        self.saveButton.setEnabled(not busy and self.result is not None and self.confirmCheck.isChecked())

    def set_status(self, key, **values):
        self.status_key, self.status_values = key, values
        self.statusLabel.setText(self.t[key].format(**values))
        state = 'success' if key == 'saved' else 'neutral' if key in ('ready', 'working', 'loaded', 'guessed') else 'error'
        self.statusLabel.setProperty('state', state)
        self.statusLabel.style().unpolish(self.statusLabel)
        self.statusLabel.style().polish(self.statusLabel)

    def show_details(self):
        result = self.result
        method = 'utf8_method' if result and result.method == 'utf8' else result.method if result else ''
        self.detectedLabel.setText(self.t['detected'].format(encoding=ENCODING_LABELS[result.encoding],
                                  method=self.t[method]) if result else '')
        notes = []
        if result and len(result.text) > PREVIEW_CHARS:
            notes.append(self.t['truncated'])
        if result and '\ufffd' in result.text:
            notes.append(self.t['damaged'])
        self.previewNote.setText('\n'.join(notes))
        self.previewNote.setVisible(bool(notes))

    def clear_result(self):
        self.result = None
        self.previewEdit.clear()
        self.confirmCheck.setChecked(False)
        self.show_details()
        self.refresh_controls()

    def clear(self):
        if self.is_busy():
            return
        self.source_path = self.raw = None
        self.clear_result()
        self.encodingCombo.blockSignals(True)
        self.encodingCombo.setCurrentIndex(0)
        self.encodingCombo.blockSignals(False)
        self.retranslate_ui(self.owner.current_lang)
        self.set_status('ready')

    def import_subtitle(self):
        if self.is_busy():
            return
        file_filter = 'Subtitles (' + ' '.join('*' + ext for ext in SUBTITLE_SUFFIXES) + ')'
        filename, _ = QFileDialog.getOpenFileName(self, self.t['import'], '', file_filter)
        if filename:
            self.load_path(filename)

    def load_path(self, filename):
        if self.is_busy():
            return
        self.clear()
        self.source_path = Path(filename).resolve()
        self.retranslate_ui(self.owner.current_lang)
        if self.source_path.suffix.lower() not in SUBTITLE_SUFFIXES:
            self.set_status('unsupported_file')
            return
        self.start_decode()

    def start_decode(self, *_):
        if self.is_busy() or self.source_path is None:
            return
        self.clear_result()
        self.worker = EncodingWorker(self.source_path, self.raw, self.encodingCombo.currentData(), self)
        self.worker.succeeded.connect(self.completed)
        self.worker.failed.connect(self.failed)
        self.worker.finished.connect(self.finished)
        self.set_status('working')
        self.refresh_controls()
        self.worker.start()

    def completed(self, raw, result):
        self.raw, self.result = raw, result
        self.previewEdit.setPlainText(result.text[:PREVIEW_CHARS])
        self.show_details()
        self.set_status('guessed' if result.method == 'guess' else 'loaded')

    def failed(self, raw, code):
        self.raw = raw
        self.set_status(code)

    def finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.refresh_controls()

    def save_utf8(self):
        if self.is_busy() or self.result is None or not self.confirmCheck.isChecked():
            return
        source = self.source_path
        suggested = source.with_name(source.stem + '_utf8' + source.suffix)
        filename, _ = QFileDialog.getSaveFileName(self, self.t['save'], str(suggested),
                                                 'Subtitles (*' + source.suffix + ')')
        if not filename:
            return
        destination = Path(filename)
        if destination.suffix.lower() != source.suffix.lower():
            self.set_status('same_format', suffix=source.suffix)
            return
        try:
            if is_source_destination(source, destination):
                self.set_status('source_protected')
                return
            raw = self.result.utf8(with_bom=self.outputCombo.currentData())
            output = QSaveFile(str(destination))
            if not output.open(QIODevice.WriteOnly):
                self.set_status('write_error')
                return
            if output.write(raw) != len(raw):
                output.cancelWriting()
                self.set_status('write_error')
                return
            if not output.commit():
                self.set_status('write_error')
                return
        except (OSError, UnicodeError):
            self.set_status('write_error')
            return
        self.set_status('saved', name=destination.name)
