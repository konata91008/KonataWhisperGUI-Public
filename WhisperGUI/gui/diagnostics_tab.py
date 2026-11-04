"""Inspect and preview SRT repairs locally, without modifying source files."""
from pathlib import Path

from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, pyqtSignal, QIODevice, QSaveFile
from PyQt5.QtGui import QColor, QTextCursor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QCheckBox, QComboBox, QFrame, QSplitter, QTabWidget, QTableView,
    QHeaderView, QAbstractItemView, QSizePolicy, QFileDialog, QApplication)

from .file_drop import FileDropZone

from core.chinese_conversion import ConversionError, read_text_file
from core.conversion_translations import conversion_strings
from core.diagnostic_translations import diagnostic_strings
from core.interface_translations import interface_strings
from core.subtitle_diagnostics import DiagnosticError, RepairResult, analyze_srt, repair_srt


class IssueModel(QAbstractTableModel):
    def __init__(self, owner, parent):
        super().__init__(parent)
        self.owner, self.issues, self.t = owner, (), diagnostic_strings(owner.current_lang)

    def reset(self, issues, strings):
        self.beginResetModel()
        self.issues, self.t = issues, strings
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.issues)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 3

    def description(self, issue):
        return self.t['issue_' + issue.code].format(cue=issue.cue, other=issue.other, value=issue.value)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        issue = self.issues[index.row()]
        if role == Qt.ToolTipRole:
            return self.description(issue)
        if role == Qt.ForegroundRole and index.column() == 0:
            return QColor(self.owner.current_colors.get('DANGER' if issue.severity == 'error' else 'TEXT_SECONDARY', '#625950'))
        if role == Qt.DisplayRole:
            return (self.t[issue.severity], self.t['location'].format(line=issue.line, cue=issue.cue),
                    self.description(issue))[index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.t['headers'][section]
        return None


class DiagnosticWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, text, repair, sort, trim, parent):
        super().__init__(parent)
        self.text, self.repair, self.sort, self.trim = text, repair, sort, trim

    def run(self):
        try:
            result = (repair_srt(self.text, sort_by_time=self.sort, trim_overlaps=self.trim)
                      if self.repair else analyze_srt(self.text))
            self.succeeded.emit(result)
        except DiagnosticError as error:
            self.failed.emit(str(error))
        except Exception:
            self.failed.emit('unexpected')
        finally:
            self.text = ''


class DiagnosticsTab(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner, self.worker, self.source_path = owner, None, None
        self.original_report = self.preview_report = None
        self.preview_text = ''
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
        self.hintLabel = QLabel(objectName='SubtleLabel')
        self.hintLabel.setWordWrap(True)
        self.hintLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.hintLabel)

        toolbar = QFrame(objectName='ToolbarCard')
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        self.importButton, self.clearButton = QPushButton(), QPushButton()
        self.sortCheck, self.trimCheck = QCheckBox(), QCheckBox()
        toolbar_layout.addWidget(self.importButton)
        toolbar_layout.addWidget(self.clearButton)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.sortCheck)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.trimCheck)
        layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        self.dropZone = FileDropZone(self, ('.srt',), 'SRT')
        editors = self.dropZone
        editors.setMinimumWidth(280)
        editor_layout = QVBoxLayout(editors)
        editor_layout.setContentsMargins(12, 10, 12, 10)
        self.editorTabs = QTabWidget(objectName='DiagnosticEditors')
        self.sourceEdit = QPlainTextEdit(objectName='ConversionSource')
        self.previewEdit = QPlainTextEdit(objectName='ConversionResult')
        self.previewEdit.setReadOnly(True)
        for editor in (self.sourceEdit, self.previewEdit):
            editor.setMinimumHeight(140)
            editor.document().setDocumentMargin(6)
        self.editorTabs.addTab(self.sourceEdit, '')
        self.editorTabs.addTab(self.previewEdit, '')
        editor_layout.addWidget(self.dropZone.hint)
        editor_layout.addWidget(self.editorTabs)
        for editor in (self.sourceEdit, self.previewEdit):
            self.dropZone.attach_editor(editor)
        splitter.addWidget(editors)

        results = QFrame(objectName='EditorCard')
        results.setMinimumWidth(340)
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(14, 12, 14, 12)
        results_layout.setSpacing(8)
        self.scopeCombo = QComboBox()
        self.scopeCombo.addItems(['', ''])
        self.summaryLabel = QLabel(objectName='SubtleLabel')
        self.summaryLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        results_layout.addWidget(self.scopeCombo)
        results_layout.addWidget(self.summaryLabel)
        self.issueTable = QTableView(objectName='DiagnosticTable')
        self.issueModel = IssueModel(owner, self)
        self.issueTable.setModel(self.issueModel)
        self.issueTable.setMinimumHeight(100)
        self.issueTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.issueTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.issueTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.issueTable.setShowGrid(False)
        self.issueTable.setWordWrap(False)
        self.issueTable.verticalHeader().hide()
        self.issueTable.verticalHeader().setDefaultSectionSize(30)
        header = self.issueTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        results_layout.addWidget(self.issueTable, 1)
        self.detailLabel = QLabel(objectName='SubtleLabel')
        self.detailLabel.setTextFormat(Qt.PlainText)
        self.detailLabel.setWordWrap(True)
        self.detailLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.detailLabel.setMinimumHeight(48)
        results_layout.addWidget(self.detailLabel)
        splitter.addWidget(results)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        layout.addWidget(splitter, 1)

        self.statusLabel = QLabel(objectName='ConversionStatus')
        self.statusLabel.setTextFormat(Qt.PlainText)
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.statusLabel)
        actions = QHBoxLayout()
        self.inspectButton = QPushButton(objectName='PrimaryButton')
        self.repairButton, self.copyButton, self.saveButton = QPushButton(), QPushButton(), QPushButton()
        actions.addWidget(self.inspectButton)
        actions.addWidget(self.repairButton)
        actions.addStretch()
        actions.addWidget(self.copyButton)
        actions.addWidget(self.saveButton)
        layout.addLayout(actions)

        self.sourceEdit.textChanged.connect(self.invalidate)
        self.sortCheck.toggled.connect(self.invalidate_preview)
        self.trimCheck.toggled.connect(self.invalidate_preview)
        self.importButton.clicked.connect(self.import_srt)
        self.clearButton.clicked.connect(self.clear)
        self.inspectButton.clicked.connect(lambda: self.start(False))
        self.repairButton.clicked.connect(lambda: self.start(True))
        self.copyButton.clicked.connect(self.copy_preview)
        self.saveButton.clicked.connect(self.save_preview)
        self.scopeCombo.currentIndexChanged.connect(self.show_report)
        self.issueTable.selectionModel().currentRowChanged.connect(self.locate_issue)
        self.retranslate_ui(owner.current_lang)

    def retranslate_ui(self, language):
        self.dropZone.retranslate_ui(language)
        self.t = diagnostic_strings(language)
        self.common = conversion_strings(language)
        self.headingLabel.setText(self.t['title'])
        self.hintLabel.setText(self.t['hint'])
        self.offlineBadge.setText('●  ' + interface_strings(language)['offline'])
        for widget, key in ((self.importButton, 'import'), (self.clearButton, 'clear'),
                            (self.inspectButton, 'inspect'), (self.repairButton, 'repair'),
                            (self.copyButton, 'copy'), (self.saveButton, 'save'),
                            (self.sortCheck, 'sort'), (self.trimCheck, 'trim')):
            widget.setText(self.t[key])
        self.sortCheck.setToolTip(self.t['sort_tip'])
        self.trimCheck.setToolTip(self.t['trim_tip'])
        for index, key, widget in ((0, 'source', self.sourceEdit), (1, 'preview', self.previewEdit)):
            self.editorTabs.setTabText(index, self.t[key].split(' · ')[0])
            self.editorTabs.setTabToolTip(index, self.t[key])
            widget.setAccessibleName(self.t[key])
            widget.setPlaceholderText(self.t[key + '_hint'])
        self.scopeCombo.setItemText(0, self.t['scope_source'])
        self.scopeCombo.setItemText(1, self.t['scope_preview'])
        self.scopeCombo.setAccessibleName(self.t['scope'])
        self.show_report()
        self.set_status(self.status_key, **self.status_values)
        self.refresh_controls()

    def is_busy(self):
        return self.worker is not None

    def set_status(self, key, **values):
        self.status_key, self.status_values = key, values
        self.statusLabel.setText(self.t.get(key, self.common.get(key, self.t['unexpected'])).format(**values))
        state = ('success' if key in ('clean', 'saved', 'copied') else 'neutral'
                 if key in ('ready', 'working', 'repairing', 'loaded', 'checked', 'preview_ready') else 'error')
        self.statusLabel.setProperty('state', state)
        self.statusLabel.style().unpolish(self.statusLabel)
        self.statusLabel.style().polish(self.statusLabel)

    def refresh_controls(self):
        self.dropZone.refresh()
        busy = self.is_busy()
        self.sourceEdit.setReadOnly(busy)
        for control in (self.importButton, self.clearButton, self.sortCheck, self.trimCheck):
            control.setEnabled(not busy)
        self.inspectButton.setEnabled(not busy and bool(self.sourceEdit.toPlainText().strip()))
        self.repairButton.setEnabled(not busy and self.original_report is not None and
                                     not self.original_report.errors and bool(self.original_report.captions))
        self.copyButton.setEnabled(not busy and bool(self.preview_text))
        self.saveButton.setEnabled(not busy and bool(self.preview_text))
        self.scopeCombo.model().item(1).setEnabled(self.preview_report is not None)

    def invalidate_preview(self, *_):
        self.preview_text, self.preview_report = '', None
        self.previewEdit.clear()
        self.scopeCombo.setCurrentIndex(0)
        self.show_report()
        self.set_status('ready')
        self.refresh_controls()

    def invalidate(self):
        self.original_report = None
        self.invalidate_preview()

    def clear(self):
        if self.is_busy():
            return
        self.source_path = None
        self.sourceEdit.clear()
        self.editorTabs.setCurrentIndex(0)
        self.invalidate()
        self.sourceEdit.setFocus()

    def import_srt(self):
        if self.is_busy():
            return
        filename, _ = QFileDialog.getOpenFileName(self, self.t['import'], '', 'SubRip (*.srt)')
        if filename:
            self.load_path(filename)

    def load_path(self, filename):
        if self.is_busy():
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
        self.editorTabs.setCurrentIndex(0)
        self.set_status('loaded', name=self.source_path.name)

    def start(self, repair=False):
        if self.is_busy():
            return
        text = self.sourceEdit.toPlainText()
        self.invalidate_preview()
        if not text.strip():
            self.set_status('empty')
            return
        if not repair:
            self.editorTabs.setCurrentIndex(0)
            self.original_report = None
            self.show_report()
        self.worker = DiagnosticWorker(text, repair, self.sortCheck.isChecked(), self.trimCheck.isChecked(), self)
        self.worker.succeeded.connect(self.completed)
        self.worker.failed.connect(self.set_status)
        self.worker.finished.connect(self.finished)
        self.set_status('repairing' if repair else 'working')
        self.refresh_controls()
        self.worker.start()

    def completed(self, result):
        if isinstance(result, RepairResult):
            self.original_report, self.preview_report = result.original, result.checked
            self.preview_text = result.text
            self.previewEdit.setPlainText(result.text)
            self.scopeCombo.setCurrentIndex(1)
            self.editorTabs.setCurrentIndex(1)
            self.set_status('preview_ready', errors=result.checked.errors, warnings=result.checked.warnings)
        else:
            self.original_report = result
            self.set_status('checked' if result.issues else 'clean')
        self.show_report()

    def finished(self):
        worker, self.worker = self.worker, None
        worker.deleteLater()
        self.refresh_controls()

    def show_report(self, *_):
        report = self.preview_report if self.scopeCombo.currentIndex() == 1 else self.original_report
        self.issueModel.reset(report.issues if report else (), self.t)
        self.summaryLabel.setText(self.t['summary'].format(count=len(report.captions), errors=report.errors,
                                                         warnings=report.warnings) if report else '—')
        self.detailLabel.setText(self.t['clean'] if report and not report.issues else self.t['hint'])

    def locate_issue(self, index, previous=QModelIndex()):
        if not index.isValid():
            return
        issue = self.issueModel.issues[index.row()]
        self.detailLabel.setText(self.issueModel.description(issue))
        preview = self.scopeCombo.currentIndex() == 1
        editor = self.previewEdit if preview else self.sourceEdit
        self.editorTabs.setCurrentIndex(1 if preview else 0)
        block = editor.document().findBlockByNumber(issue.line - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.LineUnderCursor)
            editor.setTextCursor(cursor)
            editor.centerCursor()

    def copy_preview(self):
        if self.is_busy() or not self.preview_text:
            return
        QApplication.clipboard().setText(self.preview_text)
        self.set_status('copied')

    def save_preview(self):
        if self.is_busy() or not self.preview_text:
            return
        source = self.source_path or Path('subtitles.srt')
        suggested = source.with_name(source.stem + '.fixed.srt')
        filename, _ = QFileDialog.getSaveFileName(self, self.t['save'], str(suggested), 'SubRip (*.srt)')
        if not filename:
            return
        destination = Path(filename)
        if destination.suffix.lower() != '.srt':
            self.set_status('srt_only')
            return
        try:
            if self.source_path and (destination.resolve() == self.source_path or
                    (destination.exists() and self.source_path.exists() and destination.samefile(self.source_path))):
                self.set_status('source_protected')
                return
            output = QSaveFile(str(destination))
            if not output.open(QIODevice.WriteOnly):
                self.set_status('write_error')
                return
            raw = self.preview_text.encode('utf-8')
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
