"""Offline SRT diagnostics and conservative repair regression tests."""
import os
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from core.subtitle_diagnostics import DiagnosticError, analyze_srt, repair_srt, timestamp
from core.chinese_conversion import MAX_TEXT_CHARS
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from gui.main_window import WhisperGUI


def cue(number, start, end, text='字幕'):
    return f'{number}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n\n'


OVERLAP = cue(1, 1000, 4000, '第一段') + cue(2, 3000, 6000, '第二段') + cue(3, 8000, 9000, '第三段')


class DiagnosticTests(unittest.TestCase):
    def test_valid_unicode_multiline_and_numeric_dialogue(self):
        text = cue(1, 1000, 2000, '<i>繁體 & 日本語 😊</i>\n2026') + cue(2, 2000, 3000, ' second line  ')
        report = analyze_srt('\ufeff' + text.replace('\n', '\r\n'))
        self.assertEqual(report.issues, ())
        self.assertEqual(repair_srt(text).text, text)

    def test_nested_overlaps_are_not_missed(self):
        report = analyze_srt(cue(1, 0, 10000) + cue(2, 1000, 2000) + cue(3, 5000, 6000))
        overlaps = [issue for issue in report.issues if issue.code == 'overlap']
        self.assertEqual([(i.cue, i.other, i.value) for i in overlaps], [(2, 1, 1000), (3, 1, 1000)])

    def test_touching_boundaries_are_not_overlap(self):
        self.assertFalse(analyze_srt(cue(1, 0, 1000) + cue(2, 1000, 2000)).issues)

    def test_bad_timestamp_does_not_hide_later_captions(self):
        for timing in ['00:60:00,000 --> 00:61:00,000', '00:00:65,000 --> 00:01:10,000',
                       '-00:00:01,000 --> 00:00:02,000', '00:00:01 --> 00:00:02',
                       '00:00:01,1234 --> 00:00:02,000', '00:00:01,000 --> 00:00:02,000 unknown',
                       'broken --> time']:
            with self.subTest(timing=timing):
                source = '1\n' + timing + '\n保留這段\n\n' + cue(2, 5000, 6000)
                report = analyze_srt(source)
                self.assertEqual(len(report.captions), 2)
                self.assertIn('invalid_time', [issue.code for issue in report.issues])
                with self.assertRaisesRegex(DiagnosticError, 'manual_required'):
                    repair_srt(source)

    def test_reverse_and_zero_duration_require_human_review(self):
        for start, end in [(2000, 1000), (1000, 1000)]:
            report = analyze_srt(cue(1, start, end))
            self.assertIn('duration', [issue.code for issue in report.issues])
            with self.assertRaises(DiagnosticError):
                repair_srt(cue(1, start, end), trim_overlaps=True)

    def test_numbering_missing_separator_and_decimal_normalization(self):
        source = '9\n0:0:1.2 -> 0:0:2.50\n第一段\n9\n00:00:03,000 --> 00:00:04,000\n第二段\n'
        report = analyze_srt(source)
        self.assertEqual({issue.code for issue in report.issues}, {'numbering', 'separator', 'time_format'})
        fixed = repair_srt(source)
        self.assertEqual(fixed.text, cue(1, 1200, 2500, '第一段') + cue(2, 3000, 4000, '第二段'))
        self.assertEqual(fixed.checked.issues, ())

    def test_missing_number_at_block_start_can_be_restored(self):
        source = '00:00:01,000 --> 00:00:02,000\n原文\n\n'
        fixed = repair_srt(source)
        self.assertEqual(fixed.text, cue(1, 1000, 2000, '原文'))

    def test_sort_is_explicit_and_moves_text_with_its_timing(self):
        source = cue(1, 5000, 6000, 'Later') + cue(2, 1000, 2000, 'Earlier')
        self.assertIn('order', [i.code for i in analyze_srt(source).issues])
        self.assertEqual(repair_srt(source).text, source)
        with self.assertRaisesRegex(DiagnosticError, 'sort_required'):
            repair_srt(source, trim_overlaps=True)
        self.assertEqual(repair_srt(source, sort_by_time=True).text,
                         cue(1, 1000, 2000, 'Earlier') + cue(2, 5000, 6000, 'Later'))

    def test_overlap_repair_is_opt_in_and_never_shifts_later_captions(self):
        self.assertEqual(repair_srt(OVERLAP).text, OVERLAP)
        result = repair_srt(OVERLAP, trim_overlaps=True)
        before, after = result.original.captions, result.checked.captions
        self.assertEqual(after[0].end, 2999)
        self.assertEqual([c.start for c in before], [c.start for c in after])
        self.assertEqual([c.text for c in before], [c.text for c in after])
        self.assertEqual([(c.start, c.end) for c in before[1:]], [(c.start, c.end) for c in after[1:]])
        self.assertFalse(result.checked.issues)

    def test_equal_or_near_equal_starts_do_not_create_empty_captions(self):
        for start in (1000, 1001):
            source = cue(1, 1000, 3000) + cue(2, start, 5000)
            with self.assertRaisesRegex(DiagnosticError, 'cannot_trim'):
                repair_srt(source, trim_overlaps=True)
            self.assertEqual(repair_srt(source).text, source)

    def test_blank_line_inside_text_and_empty_captions_are_not_discarded(self):
        source = cue(1, 0, 1000, '第一行\n\n不可丟掉的第二行') + cue(2, 2000, 3000)
        report = analyze_srt(source)
        self.assertEqual(len(report.captions), 2)
        self.assertTrue(any(i.code == 'unrecognized' and i.line == 5 for i in report.issues))
        with self.assertRaisesRegex(DiagnosticError, 'manual_required'):
            repair_srt(source)
        self.assertIn('empty_caption', [i.code for i in analyze_srt(cue(1, 0, 1000, '')).issues])

    def test_malformed_header_without_separator_is_reported(self):
        source = cue(1, 0, 1000).rstrip() + '\n2\nbroken --> time\nbad\n\n' + cue(3, 5000, 6000)
        report = analyze_srt(source)
        self.assertEqual(len(report.captions), 3)
        self.assertTrue(report.errors)

    def test_new_short_duration_warning_after_trimming(self):
        result = repair_srt(cue(1, 1000, 3000) + cue(2, 1050, 4000), trim_overlaps=True)
        self.assertEqual([(i.code, i.value) for i in result.checked.issues], [('short', 49)])

    def test_controls_and_input_limits(self):
        self.assertTrue(analyze_srt(cue(1, 0, 1000, 'bad\x00text')).errors)
        for source, code in [(' \n', 'empty'), ('x' * (MAX_TEXT_CHARS + 1), 'too_large')]:
            with self.assertRaisesRegex(DiagnosticError, code):
                analyze_srt(source)

    def test_ambiguous_timestamp_in_dialogue_is_not_silently_restructured(self):
        source = cue(1, 1000, 2000, 'Timestamp example:\n00:00:03,000 --> 00:00:04,000\nSample text')
        self.assertIn('ambiguous', [i.code for i in analyze_srt(source).issues])
        with self.assertRaisesRegex(DiagnosticError, 'manual_required'):
            repair_srt(source)

    def test_known_position_extension_is_preserved(self):
        source = '1\n00:00:01,000 --> 00:00:02,000 X1:10 X2:20 Y1:30 Y2:40\nhello\n\n'
        self.assertEqual(repair_srt(source).text, source)

    def test_many_shuffled_nested_overlaps_preserve_all_content(self):
        rng = random.Random(22)
        items = [(index * 1000, index * 1000 + rng.randrange(100, 9000), f'Unique caption {index}')
                 for index in range(200)]
        rng.shuffle(items)
        source = ''.join(cue(index, start, end, text) for index, (start, end, text) in enumerate(items, 1))
        result = repair_srt(source, sort_by_time=True, trim_overlaps=True)
        self.assertEqual(len(result.checked.captions), 200)
        self.assertEqual({c.text for c in result.original.captions}, {c.text for c in result.checked.captions})
        self.assertEqual([c.start for c in result.checked.captions], sorted(item[0] for item in items))
        self.assertFalse(result.checked.issues)
        self.assertEqual(repair_srt(result.text, sort_by_time=True, trim_overlaps=True).text, result.text)


class DiagnosticGUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings_patch = patch('gui.main_window.QSettings', side_effect=lambda *args:
            QSettings(str(Path(self.directory.name) / 'test.ini'), QSettings.IniFormat))
        self.settings_patch.start()
        self.network_patch = patch('core.subtitle_ai.ChatClient.complete', side_effect=AssertionError('No API allowed'))
        self.network_patch.start()
        self.window = WhisperGUI()
        self.window.show()
        self.window.mainTabs.setCurrentIndex(2)
        self.tab = self.window.diagnosticsTab
        QTest.qWait(10)

    def tearDown(self):
        self.wait()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.network_patch.stop()
        self.settings_patch.stop()
        self.directory.cleanup()

    def wait(self):
        deadline = time.monotonic() + 10
        while self.tab.is_busy() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.tab.is_busy())

    def inspect(self, text):
        self.tab.sourceEdit.setPlainText(text)
        self.tab.start(False)
        self.wait()

    def preview(self):
        self.tab.start(True)
        self.wait()

    def test_third_tab_offline_issue_navigation_and_localization(self):
        self.assertEqual(self.window.mainTabs.tabText(2), '字幕排錯')
        self.assertIsNone(self.window.gpu_runtime)
        self.inspect(OVERLAP)
        self.assertEqual(self.tab.issueModel.rowCount(), 1)
        self.tab.issueTable.selectRow(0)
        self.app.processEvents()
        self.assertEqual(self.tab.sourceEdit.textCursor().blockNumber() + 1, 6)
        for language in ('en', 'ja', 'zh_CN', 'zh_TW'):
            self.window.change_language(language)
            self.window.cycle_theme()
            self.assertEqual(self.tab.sourceEdit.toPlainText(), OVERLAP)
            self.assertTrue(self.tab.issueModel.data(self.tab.issueModel.index(0, 2)))

    def test_preview_recheck_and_stale_results_cleared(self):
        self.inspect(OVERLAP)
        self.assertFalse(self.tab.trimCheck.isChecked())
        self.preview()
        self.assertEqual(self.tab.preview_text, OVERLAP)
        self.assertEqual(self.tab.preview_report.warnings, 1)
        self.tab.trimCheck.setChecked(True)
        self.assertEqual(self.tab.preview_text, '')
        self.assertFalse(self.tab.saveButton.isEnabled())
        self.preview()
        self.assertEqual(self.tab.preview_report.warnings, 0)
        self.assertTrue(self.tab.saveButton.isEnabled())
        self.assertIn('00:00:02,999', self.tab.preview_text)
        self.assertEqual(self.tab.sourceEdit.toPlainText(), OVERLAP)
        self.tab.copy_preview()
        self.assertEqual(self.app.clipboard().text(), self.tab.preview_text)
        self.tab.sourceEdit.insertPlainText('edit')
        self.assertFalse(self.tab.saveButton.isEnabled())
        self.assertIsNone(self.tab.original_report)

    def test_manual_errors_never_enable_export_or_drop_bad_block(self):
        bad = cue(1, 2000, 1000) + cue(2, 5000, 6000)
        self.inspect(bad)
        self.assertFalse(self.tab.repairButton.isEnabled())
        self.preview()
        self.assertEqual(self.tab.status_key, 'manual_required')
        self.assertEqual(self.tab.preview_text, '')
        self.assertEqual(self.tab.sourceEdit.toPlainText(), bad)
        self.assertFalse(self.tab.saveButton.isEnabled())

    def test_import_and_atomic_export_protect_original_and_alias(self):
        source = Path(self.directory.name) / '字幕.srt'
        source.write_text(OVERLAP, encoding='utf-16')
        raw = source.read_bytes()
        with patch('gui.diagnostics_tab.QFileDialog.getOpenFileName', return_value=(str(source), '')):
            self.tab.import_srt()
        self.tab.start(False); self.wait()
        self.tab.trimCheck.setChecked(True)
        self.preview()
        alias = Path(self.directory.name) / 'alias.srt'
        alias.symlink_to(source)
        for destination in (source, alias):
            with patch('gui.diagnostics_tab.QFileDialog.getSaveFileName', return_value=(str(destination), '')):
                self.tab.save_preview()
            self.assertEqual(self.tab.status_key, 'source_protected')
            self.assertEqual(source.read_bytes(), raw)
        destination = source.with_name('字幕.fixed.srt')
        with patch('gui.diagnostics_tab.QFileDialog.getSaveFileName', return_value=(str(destination), '')):
            self.tab.save_preview()
        self.assertEqual(destination.read_text(encoding='utf-8'), self.tab.preview_text)
        self.assertEqual(source.read_bytes(), raw)
        self.assertFalse(analyze_srt(destination.read_text()).issues)

    def test_running_worker_blocks_close_and_restart(self):
        original = analyze_srt
        def slow(text):
            time.sleep(.08)
            return original(text)
        self.tab.sourceEdit.setPlainText(OVERLAP)
        with patch('gui.diagnostics_tab.analyze_srt', side_effect=slow):
            self.tab.start(False)
            self.assertTrue(self.tab.sourceEdit.isReadOnly())
            event = QCloseEvent()
            self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            with patch('gui.main_window.QProcess.startDetached') as restart:
                self.window.restart_application()
                self.assertFalse(restart.called)
            self.wait()
        self.assertFalse(self.tab.sourceEdit.isReadOnly())


if __name__ == '__main__':
    unittest.main()
