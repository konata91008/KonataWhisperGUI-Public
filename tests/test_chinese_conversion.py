"""Run with: QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from core.chinese_conversion import ConversionError, MAX_FILE_BYTES, MAX_TEXT_CHARS, convert_text, read_text_file
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from gui.main_window import WhisperGUI


class ConversionTests(unittest.TestCase):
    def test_both_directions_and_context(self):
        traditional = '漢字轉換：頭髮與發展。'
        simplified = '汉字转换：头发与发展。'
        self.assertEqual(convert_text(traditional, 't2s'), simplified)
        self.assertEqual(convert_text(simplified, 's2t'), traditional)

    def test_srt_structure_and_mixed_text(self):
        source = '1\r\n00:00:01,200 --> 00:00:03,400\r\n歡迎使用！ OpenAI 123 😊\r\n\r\n2\r\n00:00:04,000 --> 00:00:05,000\r\n繁體\t中文\r\n'
        expected = source.replace('歡迎', '欢迎').replace('繁體', '繁体')
        self.assertEqual(convert_text(source, 't2s'), expected)
        self.assertEqual(convert_text('  \n\t', 's2t'), '  \n\t')

    def test_invalid_direction_and_size(self):
        for text, direction in [('文字', '../config'), ('字' * (MAX_TEXT_CHARS + 1), 't2s')]:
            with self.assertRaises(ConversionError):
                convert_text(text, direction)

    def test_import_encoding_and_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '字幕.srt'
            for encoding in ('utf-8', 'utf-8-sig', 'utf-16'):
                path.write_bytes('繁體\r\n中文'.encode(encoding))
                self.assertEqual(read_text_file(path), '繁體\r\n中文')
            for raw in (b'\x81\x82', b'a\x00b', b'x' * (MAX_FILE_BYTES + 1)):
                path.write_bytes(raw)
                with self.assertRaises(ConversionError):
                    read_text_file(path)


class ConversionGUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.settings_dir = tempfile.TemporaryDirectory()
        cls.settings_file = str(Path(cls.settings_dir.name) / 'test.ini')
        cls.settings_patch = patch('gui.main_window.QSettings',
                                   side_effect=lambda *args: QSettings(cls.settings_file, QSettings.IniFormat))
        cls.settings_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.settings_patch.stop()
        cls.settings_dir.cleanup()

    def setUp(self):
        QSettings(self.settings_file, QSettings.IniFormat).clear()
        with patch('gui.main_window.load_runtime', return_value=None):
            self.window = WhisperGUI()
        self.window.show()
        self.tab = self.window.conversionTab
        self.window.mainTabs.setCurrentIndex(1)
        self.directory = tempfile.TemporaryDirectory()
        QTest.qWait(10)

    def tearDown(self):
        self.wait_for_conversion()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def wait_for_conversion(self):
        deadline = time.monotonic() + 10
        while self.tab.is_busy() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.tab.is_busy(), 'Conversion did not complete')

    def convert(self, text, direction='t2s'):
        self.tab.sourceEdit.setPlainText(text)
        self.tab.directionCombo.setCurrentIndex(self.tab.directionCombo.findData(direction))
        self.tab.start_conversion()
        self.wait_for_conversion()
        return self.tab.resultEdit.toPlainText()

    def test_tabs_work_without_gpu_and_existing_controls_remain(self):
        self.assertEqual(self.window.mainTabs.count(), 4)
        self.assertIsNone(self.window.gpu_runtime)
        self.assertTrue(self.tab.isVisible())
        self.assertFalse(self.window.btnStart.isVisible())
        self.assertEqual(self.convert('歡迎使用繁體中文'), '欢迎使用繁体中文')
        self.window.mainTabs.setCurrentIndex(0)
        self.assertTrue(self.window.btnStart.isVisible())
        self.assertTrue(self.window.fileList.isVisible())

    def test_direction_changes_and_edits_invalidate_result(self):
        self.assertEqual(self.convert('软件开发', 's2t'), '軟件開發')
        self.assertTrue(self.tab.copyButton.isEnabled())
        self.tab.directionCombo.setCurrentIndex(0)
        self.assertEqual(self.tab.resultEdit.toPlainText(), '')
        self.assertFalse(self.tab.saveButton.isEnabled())
        self.convert('繁體')
        self.tab.sourceEdit.insertPlainText('更新')
        self.assertFalse(self.tab.copyButton.isEnabled())

    def test_localization_and_themes_preserve_text(self):
        self.convert('繁體中文')
        for language in ('zh_TW', 'zh_CN', 'en', 'ja'):
            self.window.change_language(language)
            self.window.cycle_theme()
            self.assertTrue(self.window.mainTabs.tabText(1))
            self.assertEqual(self.tab.resultEdit.toPlainText(), '繁体中文')
            self.assertEqual(self.tab.sourceEdit.toPlainText(), '繁體中文')

    def test_import_export_copy_and_source_protection(self):
        source = Path(self.directory.name) / '中文 字幕.srt'
        content = '1\n00:00:00,000 --> 00:00:01,000\n繁體中文\n'
        source.write_text(content, encoding='utf-8-sig')
        original_bytes = source.read_bytes()
        with patch('gui.conversion_tab.QFileDialog.getOpenFileName', return_value=(str(source), '')):
            self.tab.import_text()
        self.tab.start_conversion()
        self.wait_for_conversion()
        self.tab.copy_result()
        self.assertEqual(self.app.clipboard().text(), content.replace('體', '体'))
        with patch('gui.conversion_tab.QFileDialog.getSaveFileName', return_value=(str(source), '')):
            self.tab.save_result()
        self.assertEqual(self.tab.status_key, 'source_protected')
        self.assertEqual(source.read_bytes(), original_bytes)
        destination = source.with_name('converted.srt')
        with patch('gui.conversion_tab.QFileDialog.getSaveFileName', return_value=(str(destination), '')):
            self.tab.save_result()
        self.assertEqual(destination.read_text(), content.replace('體', '体'))
        self.assertEqual(source.read_bytes(), original_bytes)

    def test_errors_preserve_input_and_clear_stale_output(self):
        self.convert('繁體')
        with patch('gui.conversion_tab.convert_text', side_effect=ConversionError('missing_dependency')):
            self.tab.start_conversion()
            self.wait_for_conversion()
        self.assertEqual(self.tab.sourceEdit.toPlainText(), '繁體')
        self.assertEqual(self.tab.resultEdit.toPlainText(), '')
        self.assertEqual(self.tab.status_key, 'missing_dependency')
        self.assertFalse(self.tab.copyButton.isEnabled())
        self.assertTrue(self.tab.convertButton.isEnabled())

    def test_running_worker_cannot_be_destroyed_by_close(self):
        def slow_conversion(text, direction):
            time.sleep(0.1)
            return '繁体'
        with patch('gui.conversion_tab.convert_text', side_effect=slow_conversion):
            self.tab.sourceEdit.setPlainText('繁體')
            self.tab.start_conversion()
            self.assertTrue(self.tab.sourceEdit.isReadOnly())
            event = QCloseEvent()
            self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.wait_for_conversion()
        self.assertFalse(self.tab.sourceEdit.isReadOnly())
        self.assertEqual(self.tab.resultEdit.toPlainText(), '繁体')


if __name__ == '__main__':
    unittest.main()
