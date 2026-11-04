"""Qt drag/drop routing, feedback and safeguards across all subtitle pages."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from PyQt5.QtCore import Qt, QSettings, QMimeData, QUrl, QPoint, QPointF
from PyQt5.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from gui.main_window import WhisperGUI


class FileDropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.settings = patch('gui.main_window.QSettings', side_effect=lambda *args:
            QSettings(str(self.folder / 'settings.ini'), QSettings.IniFormat))
        self.runtime = patch('gui.main_window.load_runtime', return_value=None)
        self.data = patch.dict(os.environ, {'TJKSUB_DATA_DIR': str(self.folder / 'data')})
        self.api = patch('core.subtitle_ai.ChatClient.complete', side_effect=AssertionError('Unexpected network call'))
        for context in (self.settings, self.runtime, self.data, self.api):
            context.start()
        self.window = WhisperGUI()
        self.window.show()
        self.pages = (self.window.conversionTab, self.window.diagnosticsTab, self.window.encodingTab)
        self.text = '1\r\n00:00:01,000 --> 00:00:02,000\r\n繁體字幕與檔案內容\r\n'
        self.source = self.folder / '拖曳 字幕 #1.SRT'
        self.source.write_bytes(self.text.encode('utf-8'))

    def tearDown(self):
        self.wait()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        for context in (self.api, self.data, self.runtime, self.settings):
            context.stop()
        self.temp.cleanup()

    def wait(self):
        deadline = time.monotonic() + 15
        while any(page.is_busy() for page in self.pages) and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(any(page.is_busy() for page in self.pages))

    def mime(self, urls=None):
        mime = QMimeData()
        mime.setUrls(urls if urls is not None else [QUrl.fromLocalFile(str(self.source))])
        mime.setText('file:///this-path-must-not-be-inserted.srt')
        return mime

    def enter(self, target, mime, actions=Qt.CopyAction | Qt.MoveAction):
        event = QDragEnterEvent(QPoint(10, 10), actions, mime, Qt.LeftButton, Qt.NoModifier)
        self.app.sendEvent(target, event)
        return event

    def drop(self, target, mime, actions=Qt.CopyAction | Qt.MoveAction):
        event = QDropEvent(QPointF(10, 10), actions, mime, Qt.LeftButton, Qt.NoModifier)
        self.app.sendEvent(target, event)
        self.wait()
        return event

    def assert_imported(self, page):
        self.assertEqual(page.source_path, self.source.resolve())
        if page is self.window.encodingTab:
            self.assertEqual(page.result.text, self.text)
            self.assertFalse(page.confirmCheck.isChecked())
        else:
            self.assertEqual(page.sourceEdit.toPlainText(), self.text.replace('\r\n', '\n'))
        self.assertEqual(self.window.fileList.count(), 0)
        self.assertEqual(self.source.read_bytes(), self.text.encode('utf-8'))

    def test_drop_zone_and_window_background_import_into_current_page(self):
        for page in self.pages:
            self.window.mainTabs.setCurrentWidget(page)
            for target in (page.dropZone, self.window):
                with self.subTest(page=type(page).__name__, target=type(target).__name__):
                    mime = self.mime()
                    self.assertTrue(self.enter(target, mime).isAccepted())
                    self.assertEqual(page.dropZone.property('dropState'), 'active')
                    event = self.drop(target, mime)
                    self.assertTrue(event.isAccepted())
                    self.assertEqual(event.dropAction(), Qt.CopyAction)
                    self.assert_imported(page)
                    self.assertEqual(page.dropZone.property('dropState'), 'idle')

    def test_editor_viewports_import_content_instead_of_inserting_file_urls(self):
        for page in self.pages:
            self.window.mainTabs.setCurrentWidget(page)
            editors = ((page.sourceEdit, page.resultEdit) if page is self.window.conversionTab else
                       (page.sourceEdit, page.previewEdit) if page is self.window.diagnosticsTab else
                       (page.previewEdit,))
            for editor in editors:
                with self.subTest(page=type(page).__name__, editor=editor.objectName()):
                    mime = self.mime()
                    self.assertTrue(self.enter(editor.viewport(), mime).isAccepted())
                    self.assertTrue(self.drop(editor.viewport(), mime).isAccepted())
                    self.assert_imported(page)
                    self.assertNotIn('file:///', editor.toPlainText())

    def test_reject_multiple_remote_directory_wrong_format_and_text_without_replacing(self):
        wrong = self.folder / 'wrong.mp4'; wrong.write_bytes(b'not subtitle')
        directory = self.folder / 'folder.srt'; directory.mkdir()
        text_only = QMimeData(); text_only.setText(str(self.source))
        invalid = [self.mime([QUrl.fromLocalFile(str(self.source))] * 2),
                   self.mime([QUrl('https://example.com/subtitle.srt')]),
                   self.mime([QUrl.fromLocalFile(str(directory))]),
                   self.mime([QUrl.fromLocalFile(str(wrong))]), text_only]
        for page in self.pages:
            self.window.mainTabs.setCurrentWidget(page)
            page.load_path(self.source); self.wait()
            for mime in invalid:
                self.assertFalse(self.enter(page.dropZone, mime).isAccepted())
                self.assert_imported(page)

    def test_supported_extensions_depend_on_active_tool(self):
        text_file = self.folder / 'text.TXT'; text_file.write_bytes(b'plain text')
        ass_file = self.folder / 'captions.ass'; ass_file.write_bytes(b'[Script Info]\nTitle: sample\n')
        for path, accepted in ((text_file, (True, False, True)), (ass_file, (False, False, True))):
            for page, expected in zip(self.pages, accepted):
                self.window.mainTabs.setCurrentWidget(page)
                mime = self.mime([QUrl.fromLocalFile(str(path))])
                self.assertEqual(self.enter(page.dropZone, mime).isAccepted(), expected)
                self.app.sendEvent(page.dropZone, QDragLeaveEvent())

    def test_busy_rechecked_on_drop_and_move_only_drags_are_refused(self):
        for page in self.pages:
            self.window.mainTabs.setCurrentWidget(page)
            mime = self.mime()
            self.assertFalse(self.enter(page.dropZone, mime, Qt.MoveAction).isAccepted())
            self.assertTrue(self.enter(page.dropZone, mime).isAccepted())
            with patch.object(page, 'is_busy', return_value=True), patch.object(page, 'load_path') as load:
                # Busy state can change after the OS accepted drag-enter.
                event = QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
                page.dropZone.dropEvent(event)
                self.assertFalse(event.isAccepted())
                load.assert_not_called()
                self.assertFalse(self.enter(page.dropZone, mime).isAccepted())
            page.dropZone.clear_feedback()

    def test_feedback_clears_on_leave_tab_switch_and_localizes(self):
        for page in self.pages:
            self.window.mainTabs.setCurrentWidget(page)
            mime = self.mime()
            self.enter(page.dropZone, mime)
            event = QDragMoveEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
            self.app.sendEvent(page.dropZone, event)
            self.assertTrue(event.isAccepted())
            self.app.sendEvent(page.dropZone, QDragLeaveEvent())
            self.assertEqual(page.dropZone.property('dropState'), 'idle')
            self.enter(self.window, mime)
            self.window.mainTabs.setCurrentIndex(0)
            self.assertEqual(page.dropZone.property('dropState'), 'idle')
        for language in ('en', 'ja', 'zh_CN', 'zh_TW'):
            self.window.change_language(language)
            for page in self.pages:
                self.assertIn(page.dropZone.formats, page.dropZone.hint.text())

    def test_drop_invalidates_old_results_without_starting_translation(self):
        conversion, diagnostics, encoding = self.pages
        conversion.directionCombo.setCurrentIndex(conversion.directionCombo.findData('translate'))
        conversion.resultEdit.setPlainText('old result')
        diagnostics.preview_text = 'old preview'
        diagnostics.previewEdit.setPlainText('old preview')
        encoding.confirmCheck.setChecked(True)
        for page in self.pages:
            self.window.mainTabs.setCurrentWidget(page)
            mime = self.mime()
            self.enter(page.dropZone, mime)
            self.drop(page.dropZone, mime)
        self.assertEqual(conversion.resultEdit.toPlainText(), '')
        self.assertEqual(diagnostics.preview_text, '')
        self.assertEqual(diagnostics.previewEdit.toPlainText(), '')
        self.assertFalse(encoding.confirmCheck.isChecked())

    def test_transcription_drop_still_routes_to_media_import(self):
        self.window.mainTabs.setCurrentIndex(0)
        mime = self.mime()
        with patch.object(self.window, 'add_files') as add:
            self.assertTrue(self.enter(self.window, mime).isAccepted())
            self.drop(self.window, mime)
            add.assert_called_once()
            self.assertEqual([Path(path).resolve() for path in add.call_args.args[0]], [self.source.resolve()])


if __name__ == '__main__':
    unittest.main()
