"""Translation validation and UI integration, with no external API requests."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from core.chinese_conversion import ConversionError
from core.language_translation import translate_text, translation_prompt
from core.subtitle_ai import APIConfig, AIError, Cancelled, ChatClient, SYSTEM_PROMPT, parse_srt
from PyQt5.QtCore import QSettings
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from gui.main_window import WhisperGUI


class FakeTranslator:
    def __init__(self, transform=lambda text: '譯文：' + text):
        self.transform, self.calls = transform, []

    def complete(self, entries, prompt):
        self.calls.append(entries)
        return json.dumps({'segments': [{'id': entry['id'], 'text': self.transform(entry['text'])}
                                        for entry in entries]})


class TranslationTests(unittest.TestCase):
    def test_plain_text_preserves_whitespace_and_empty_lines(self):
        result = translate_text('  Hello\t\r\n\r\nWorld  \n', 'en', 'ja', client=FakeTranslator())
        self.assertEqual(result, '  譯文：Hello\t\r\n\r\n譯文：World  \n')

    def test_srt_numbers_and_times_are_local(self):
        source = '004\r\n00:00:01,200 --> 00:00:04,300\r\nHello\r\n\r\n9\r\n00:00:06,000 --> 00:00:07,999\r\nWorld\r\n'
        before = parse_srt(source)
        client = FakeTranslator()
        after = parse_srt(translate_text(source, 'auto', 'ja', client=client))
        self.assertEqual([(cue.number, cue.timing) for cue in before], [(cue.number, cue.timing) for cue in after])
        self.assertEqual(after[1].text, '譯文：World')
        self.assertEqual(client.calls[0], [{'id': 0, 'text': 'Hello'}, {'id': 1, 'text': 'World'}])

    def test_chinese_target_normalizes_script(self):
        for target, returned, expected in [('zh-TW', '头发与发展', '頭髮與發展'),
                                            ('zh-CN', '頭髮與發展', '头发与发展')]:
            self.assertEqual(translate_text('Hair', 'en', target, client=FakeTranslator(lambda _: returned)), expected)

    def test_language_and_size_validation_before_network(self):
        client = FakeTranslator()
        for source, target in [('bogus', 'en'), ('ja', 'ja'), ('auto', 'auto')]:
            with self.assertRaises(ConversionError):
                translate_text('Hello', source, target, client=client)
        with self.assertRaisesRegex(AIError, 'too_long'):
            translate_text('Hello\n' + 'a' * 6001, 'en', 'ja', client=client)
        with self.assertRaisesRegex(AIError, 'srt'):
            translate_text('bad subtitle', 'en', 'ja', format_hint='srt', client=client)
        self.assertEqual(client.calls, [])

    def test_invalid_reply_rejected(self):
        for bad in ['not json', '{"segments":[]}', '{"segments":[{"id":9,"text":"oops"}]}',
                    '{"segments":[{"id":0,"text":"extra\\nline"}]}']:
            client = FakeTranslator()
            client.complete = lambda entries, prompt: bad
            with self.assertRaisesRegex(AIError, 'response'):
                translate_text('Hello', 'en', 'ja', client=client)

    def test_cancellation_discards_completed_batches(self):
        client = FakeTranslator()
        progress = []
        with self.assertRaises(Cancelled):
            translate_text('\n'.join(['Hello'] * 45), 'en', 'ja', client=client,
                           cancelled=lambda: len(client.calls) >= 1,
                           progress=lambda *values: progress.append(values))
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(progress, [])

    def test_batch_progress(self):
        progress = []
        result = translate_text('\n'.join(['Hello'] * 45), 'en', 'ja', client=FakeTranslator(),
                                progress=lambda *values: progress.append(values))
        self.assertEqual(len(result.splitlines()), 45)
        self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_provider_payloads_use_translation_prompt_and_keep_default(self):
        class Response:
            def __init__(self, value): self.raw = json.dumps(value).encode()
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return self.raw
        class Opener:
            def __init__(self, response): self.response = response
            def open(self, request, timeout):
                self.payload = json.loads(request.data)
                return Response(self.response)
        for protocol, envelope in [
            ('openai', {'choices': [{'finish_reason': 'stop', 'message': {'content': 'reply'}}]}),
            ('gemini', {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': 'reply'}]}}]}),
            ('anthropic', {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': 'reply'}]})]:
            config = APIConfig('https://api.example.invalid/v1', 'test-model', 'test-key', protocol)
            for prompt in [SYSTEM_PROMPT, translation_prompt('en', 'ja')]:
                opener = Opener(envelope)
                options = {} if prompt == SYSTEM_PROMPT else {'system_prompt': prompt}
                client = ChatClient(config, opener=opener, **options)
                self.assertEqual(client.complete([{'id': 0, 'text': 'Hello'}], ''), 'reply')
                payload = opener.payload
                actual = (payload['systemInstruction']['parts'][0]['text'] if protocol == 'gemini'
                          else payload['system'] if protocol == 'anthropic' else payload['messages'][0]['content'])
                self.assertEqual(actual, prompt)


class TranslationGUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings_file = str(Path(self.directory.name) / 'test.ini')
        self.settings_patch = patch('gui.main_window.QSettings',
                                   side_effect=lambda *args: QSettings(self.settings_file, QSettings.IniFormat))
        self.settings_patch.start()
        self.window = WhisperGUI()
        self.window.show()
        self.window.mainTabs.setCurrentIndex(1)
        self.tab = self.window.conversionTab
        self.tab.directionCombo.setCurrentIndex(self.tab.directionCombo.findData('translate'))
        QTest.qWait(10)

    def tearDown(self):
        self.wait_for_translation()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.settings_patch.stop()
        self.directory.cleanup()

    def wait_for_translation(self):
        deadline = time.monotonic() + 10
        while self.tab.is_busy() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.tab.is_busy())

    def configure(self):
        self.window.api_config = APIConfig('https://api.example.invalid/v1', 'test-model', 'test-key')
        self.window.save_api_settings()

    def test_mode_disclosure_and_missing_configuration_never_sends(self):
        with patch('gui.conversion_tab.translate_text') as request:
            self.assertEqual(self.window.mainTabs.tabText(1), '語言轉換')
            self.assertTrue(self.tab.translationPanel.isVisible())
            self.assertIn('API', self.tab.offlineBadge.text())
            self.tab.sourceEdit.setPlainText('Hello')
            self.tab.start_conversion()
            self.assertEqual(self.tab.status_key, 'api:model')
            self.assertFalse(self.tab.is_busy())
            self.assertFalse(request.called)
            self.configure()
            self.assertIn('api.example.invalid', self.tab.destinationLabel.text())
            self.assertNotIn('test-key', self.tab.destinationLabel.text())
            settings_text = Path(self.settings_file).read_text()
            self.assertNotIn('test-key', settings_text)
            self.tab.directionCombo.setCurrentIndex(0)
            self.assertFalse(self.tab.translationPanel.isVisible())
            self.assertIn('離線', self.tab.offlineBadge.text())

    def test_translation_result_progress_and_language_invalidation(self):
        self.configure()
        self.tab.sourceEdit.setPlainText('Hello')
        def translate(*args, **kwargs):
            kwargs['progress'](1, 1)
            return '你好'
        with patch('gui.conversion_tab.translate_text', side_effect=translate) as request:
            self.tab.start_conversion()
            self.assertTrue(self.tab.cancelButton.isVisible())
            self.assertFalse(self.tab.apiButton.isEnabled())
            self.wait_for_translation()
            self.assertEqual(request.call_args.args[1:3], ('auto', 'en'))
        self.assertEqual(self.tab.status_key, 'translation_done')
        self.assertEqual(self.tab.resultEdit.toPlainText(), '你好')
        self.assertTrue(self.tab.saveButton.isEnabled())
        self.tab.targetLanguageCombo.setCurrentIndex(self.tab.targetLanguageCombo.findData('ja'))
        self.assertEqual(self.tab.resultEdit.toPlainText(), '')
        self.assertFalse(self.tab.saveButton.isEnabled())

    def test_cancel_and_service_failure_preserve_input(self):
        self.configure()
        self.tab.sourceEdit.setPlainText('Hello')
        def slow_translate(*args, **kwargs):
            time.sleep(.06)
            return 'Discard this result'
        with patch('gui.conversion_tab.translate_text', side_effect=slow_translate):
            self.tab.start_conversion()
            self.tab.cancel_translation()
            self.wait_for_translation()
        self.assertEqual(self.tab.status_key, 'cancelled')
        self.assertEqual(self.tab.resultEdit.toPlainText(), '')
        with patch('gui.conversion_tab.translate_text', side_effect=AIError('response')):
            self.tab.start_conversion()
            self.wait_for_translation()
        self.assertEqual(self.tab.status_key, 'api:response')
        self.assertEqual(self.tab.sourceEdit.toPlainText(), 'Hello')
        self.assertEqual(self.tab.resultEdit.toPlainText(), '')
        self.assertFalse(self.tab.saveButton.isEnabled())


if __name__ == '__main__':
    unittest.main()
