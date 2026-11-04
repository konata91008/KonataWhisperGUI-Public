"""Real encoded fixtures, non-lossy export, and user confirmation safeguards."""
import codecs
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from core.subtitle_encoding import (EncodingError, MAX_FILE_BYTES, PREVIEW_CHARS,
                                    decode_subtitle, read_subtitle)
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from gui.main_window import WhisperGUI

SAMPLES = {
    'cp950': '這是一段繁體中文字幕，我們正在測試字幕的編碼，讓電腦能夠正常顯示所有文字。',
    'gb18030': '这是一段简体中文字幕，我们正在测试字幕的编码，让电脑能够正常显示所有文字。',
    'cp932': 'これは日本語の字幕です。文字コードを変換して正しく表示できるか確認しています。',
    'cp949': '이것은 한국어 자막입니다. 컴퓨터에서 문자가 올바르게 표시되는지 확인합니다.',
    'cp1252': 'Café déjà vu — voilà, François! It’s a beautiful day in München.',
}


def subtitle(text):
    return '1\r\n00:00:01,000 --> 00:00:03,000\r\n' + text + '\r\n\r\n'


class SubtitleEncodingTests(unittest.TestCase):
    def test_unicode_boms_and_bomless_utf8_preserve_all_content(self):
        text = subtitle('繁體 简体 日本語 한글 😊 <i>text</i>') + 'spaces  \r\n\nlast line'
        for codec, bom in [('utf-8', b''), ('utf-8', codecs.BOM_UTF8),
                           ('utf-16-le', codecs.BOM_UTF16_LE), ('utf-16-be', codecs.BOM_UTF16_BE),
                           ('utf-32-le', codecs.BOM_UTF32_LE), ('utf-32-be', codecs.BOM_UTF32_BE)]:
            with self.subTest(codec=codec, bom=bom):
                result = decode_subtitle(bom + text.encode(codec))
                self.assertEqual(result.text, text)
                self.assertEqual(result.utf8(), text.encode('utf-8'))
                self.assertEqual(result.utf8(True), codecs.BOM_UTF8 + text.encode('utf-8'))
                self.assertIn(result.method, ('bom', 'utf8'))

    def test_only_one_signature_removed_leading_content_mark_preserved(self):
        text = '\ufeff' + subtitle('中文')
        raw = codecs.BOM_UTF8 + text.encode('utf-8')
        for encoding in ('auto', 'utf-8-sig'):
            self.assertEqual(decode_subtitle(raw, encoding).text, text)

    def test_ascii_is_already_valid_utf8(self):
        raw = b'1\r\n00:00:01,000 --> 00:00:03,000\r\nASCII\r\n'
        result = decode_subtitle(raw)
        self.assertEqual(result.method, 'utf8')
        self.assertEqual(result.utf8(), raw)

    def test_legacy_detection_is_explicitly_a_guess(self):
        for codec, content in SAMPLES.items():
            with self.subTest(codec=codec):
                text = subtitle(content)
                result = decode_subtitle(text.encode(codec))
                self.assertEqual(result.text, text)
                self.assertEqual(result.method, 'guess')

    def test_manual_legacy_decoding_and_non_bmp_gb18030(self):
        samples = dict(SAMPLES, cp1251='Привет, мир! Это русские субтитры.',
                       big5hkscs='香港字幕：𨋢', gb18030='简体字幕与四字节字符：𠮷😊',
                       iso8859_1='Été à Montréal')
        for codec, content in samples.items():
            with self.subTest(codec=codec):
                text = subtitle(content)
                result = decode_subtitle(text.encode(codec), codec)
                self.assertEqual(result.utf8().decode('utf-8'), text)
                self.assertEqual(result.method, 'manual')

    def test_bomless_utf16_and_utf32_are_guesses(self):
        text = subtitle('繁體中文と日本語')
        for codec in ('utf-16-le', 'utf-16-be', 'utf-32-le', 'utf-32-be'):
            with self.subTest(codec=codec):
                result = decode_subtitle(text.encode(codec))
                self.assertEqual(result.text, text)
                self.assertEqual(result.method, 'guess')

    def test_incomplete_sequences_never_silently_replace_or_drop_bytes(self):
        for raw, codec in [(b'\xe4\xb8', 'utf-8-sig'), (b'\x81', 'cp932'),
                           (b'\xa4', 'cp950'), (b'A', 'utf-16-le'),
                           (codecs.BOM_UTF8 + b'\xe4\xb8', 'auto'),
                           (codecs.BOM_UTF16_LE + b'A', 'auto')]:
            with self.subTest(codec=codec):
                with self.assertRaisesRegex(EncodingError, 'decode_error'):
                    decode_subtitle(raw, codec)

    def test_binary_empty_unknown_codec_and_size_limits(self):
        for raw, codec, message in [(b'', 'auto', 'empty'), (b'a\x00b', 'auto', 'binary'),
                                    (b'a\x00b', 'cp1252', 'binary'), (b'abc', 'unicode_escape', 'unsupported_encoding')]:
            with self.subTest(message=message):
                with self.assertRaisesRegex(EncodingError, message):
                    decode_subtitle(raw, codec)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'oversize.srt'
            with path.open('wb') as stream:
                stream.truncate(MAX_FILE_BYTES + 1)
            with self.assertRaisesRegex(EncodingError, 'too_large'):
                read_subtitle(path)

    def test_subtitle_formats_and_mixed_newlines_are_not_rewritten(self):
        sources = ['[Script Info]\r\nTitle: 繁體字幕\n[V4+ Styles]\r\nFormat: Name, Fontname\n',
                   'WEBVTT\n\n00:01.000 --> 00:02.000\n<c.red>字幕</c>\n',
                   '<SAMI>\r\n<SYNC Start=1000><P>字幕</SAMI>\r',
                   '{25}{50}第一行|第二行']
        for text in sources:
            self.assertEqual(decode_subtitle(text.encode('cp950'), 'cp950').utf8(), text.encode('utf-8'))


class EncodingGUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name)
        self.settings = patch('gui.main_window.QSettings', side_effect=lambda *args:
                              QSettings(str(self.folder / 'settings.ini'), QSettings.IniFormat))
        self.runtime = patch('gui.main_window.load_runtime', return_value=None)
        self.data = patch.dict(os.environ, {'TJKSUB_DATA_DIR': str(self.folder / 'data')})
        for context in (self.settings, self.runtime, self.data):
            context.start()
        self.window = WhisperGUI()
        self.tab = self.window.encodingTab
        self.window.mainTabs.setCurrentIndex(3)

    def tearDown(self):
        self.wait()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        for context in (self.data, self.runtime, self.settings):
            context.stop()
        self.directory.cleanup()

    def wait(self):
        deadline = time.monotonic() + 15
        while self.tab.is_busy() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.tab.is_busy())

    def load(self, content=None, codec='cp950', suffix='.srt'):
        text = subtitle(SAMPLES['cp950']) if content is None else content
        self.source = self.folder / ('字幕' + suffix)
        self.source.write_bytes(text.encode(codec))
        self.tab.load_path(self.source)
        self.wait()
        return text

    def save(self, path):
        with patch('gui.encoding_tab.QFileDialog.getSaveFileName', return_value=(str(path), '')):
            self.tab.save_utf8()

    def test_fourth_tab_confirm_export_and_locale_theme_switch(self):
        self.assertEqual(self.window.mainTabs.tabText(3), '字幕轉碼')
        text = self.load()
        self.assertFalse(self.tab.saveButton.isEnabled())
        self.assertEqual(self.tab.status_key, 'guessed')
        self.assertEqual(self.tab.result.text, text)
        for language in ('en', 'ja', 'zh_CN', 'zh_TW'):
            self.window.change_language(language)
            self.window.cycle_theme()
            self.assertEqual(self.tab.result.text, text)
        self.tab.confirmCheck.setChecked(True)
        self.assertTrue(self.tab.saveButton.isEnabled())
        output = self.folder / '字幕_utf8.srt'
        self.save(output)
        self.assertEqual(output.read_bytes(), text.encode('utf-8'))
        self.assertEqual(self.source.read_bytes(), text.encode('cp950'))

    def test_cannot_export_until_confirmed_and_reset_after_encoding_change(self):
        self.load()
        output = self.folder / 'new.srt'
        self.save(output)
        self.assertFalse(output.exists())
        self.tab.confirmCheck.setChecked(True)
        self.tab.encodingCombo.setCurrentIndex(self.tab.encodingCombo.findData('cp950'))
        self.assertFalse(self.tab.saveButton.isEnabled())
        self.wait()
        self.assertFalse(self.tab.confirmCheck.isChecked())
        self.assertEqual(self.tab.result.method, 'manual')

    def test_wrong_encoding_clears_stale_preview_and_can_recover(self):
        text = self.load()
        self.tab.confirmCheck.setChecked(True)
        self.tab.encodingCombo.setCurrentIndex(self.tab.encodingCombo.findData('utf-8-sig'))
        self.wait()
        self.assertIsNone(self.tab.result)
        self.assertEqual(self.tab.previewEdit.toPlainText(), '')
        self.assertFalse(self.tab.saveButton.isEnabled())
        self.assertEqual(self.tab.status_key, 'decode_error')
        self.tab.encodingCombo.setCurrentIndex(self.tab.encodingCombo.findData('cp950'))
        self.wait()
        self.assertEqual(self.tab.result.text, text)

    def test_original_alias_and_format_are_protected(self):
        text = self.load()
        self.tab.confirmCheck.setChecked(True)
        alias = self.folder / 'alias.srt'
        os.link(self.source, alias)
        for path in (self.source, alias):
            self.save(path)
            self.assertEqual(self.tab.status_key, 'source_protected')
            self.assertEqual(self.source.read_bytes(), text.encode('cp950'))
        self.save(self.folder / 'wrong.ass')
        self.assertEqual(self.tab.status_key, 'same_format')
        self.assertFalse((self.folder / 'wrong.ass').exists())

    def test_full_export_preserves_crlf_and_bom_beyond_preview_limit(self):
        text = '[Script Info]\r\n' + ('Title: 字幕\r\n' * (PREVIEW_CHARS // 5))
        self.load(text, codec='utf-16', suffix='.ass')
        self.assertLess(len(self.tab.previewEdit.toPlainText()), len(text))
        self.tab.confirmCheck.setChecked(True)
        self.tab.outputCombo.setCurrentIndex(1)
        destination = self.folder / 'full.ass'
        self.save(destination)
        self.assertEqual(destination.read_bytes(), codecs.BOM_UTF8 + text.encode('utf-8'))

    def test_failed_new_import_and_clear_do_not_keep_previous_result(self):
        self.load()
        self.tab.confirmCheck.setChecked(True)
        self.tab.load_path(self.folder / 'missing.srt')
        self.wait()
        self.assertEqual(self.tab.status_key, 'read_error')
        self.assertIsNone(self.tab.result)
        self.assertFalse(self.tab.saveButton.isEnabled())
        self.load()
        self.tab.clear()
        self.assertIsNone(self.tab.raw)
        self.assertIsNone(self.tab.source_path)
        self.assertEqual(self.tab.previewEdit.toPlainText(), '')

    def test_failed_atomic_write_preserves_existing_destination(self):
        self.load()
        self.tab.confirmCheck.setChecked(True)
        destination = self.folder / 'existing.srt'
        destination.write_bytes(b'KEEP')
        with patch('gui.encoding_tab.QSaveFile') as save_file:
            save_file.return_value.open.return_value = True
            save_file.return_value.write.return_value = -1
            self.save(destination)
            save_file.return_value.cancelWriting.assert_called_once()
            save_file.return_value.commit.assert_not_called()
        self.assertEqual(self.tab.status_key, 'write_error')
        self.assertEqual(destination.read_bytes(), b'KEEP')

    def test_active_worker_blocks_close_and_restart(self):
        original = decode_subtitle
        def slow(*args):
            time.sleep(.1)
            return original(*args)
        source = self.folder / 'slow.srt'
        source.write_bytes(subtitle('字幕').encode('utf-8'))
        with patch('gui.encoding_tab.decode_subtitle', side_effect=slow):
            self.tab.load_path(source)
            event = QCloseEvent()
            self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            with patch('gui.main_window.QProcess.startDetached') as restart:
                self.window.restart_application()
                restart.assert_not_called()
            self.wait()


if __name__ == '__main__':
    unittest.main()
