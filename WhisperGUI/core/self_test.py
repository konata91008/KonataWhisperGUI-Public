"""Offline executable smoke test; never reads or changes real user settings."""
import json
import os
import tempfile
import time
import traceback
from pathlib import Path
from unittest.mock import patch


def run(report_path):
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checks = []
    gui = None
    try:
        with tempfile.TemporaryDirectory(prefix='tjksub-smoke-') as temporary:
            os.environ['TJKSUB_DATA_DIR'] = str(Path(temporary) / 'data')
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import QSettings, Qt, QMimeData, QUrl, QPoint, QPointF
            from PyQt5.QtGui import QFontDatabase, QDragEnterEvent, QDropEvent
            from PyQt5.QtTest import QTest
            from core.paths import resource_root, data_root, is_packaged, bundled_runtime
            from core.version import VERSION_INFO
            from core.network import ssl_context
            from core.subtitle_diagnostics import repair_srt
            from gui import main_window
            app = QApplication.instance() or QApplication([])
            assert QFontDatabase().families(), 'The Qt platform has no fonts; text cannot render'
            checks.append('available-ui-fonts')
            main_window.QSettings = lambda *args: QSettings(str(Path(temporary) / 'settings.ini'), QSettings.IniFormat)
            gui = main_window.WhisperGUI()
            gui.show()
            app.processEvents()
            assert gui.mainTabs.count() == 4
            assert gui.brandMark.renderer.isValid()
            assert data_root().is_relative_to(Path(temporary).resolve())
            checks.extend(['four-tabs', 'svg-logo', 'isolated-user-data'])
            def drop_file(page, filename, target):
                gui.mainTabs.setCurrentWidget(page)
                mime = QMimeData()
                mime.setUrls([QUrl.fromLocalFile(str(filename))])
                enter = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
                app.sendEvent(target, enter)
                assert enter.isAccepted()
                drop = QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
                app.sendEvent(target, drop)
                assert drop.isAccepted() and drop.dropAction() == Qt.CopyAction

            tab = gui.conversionTab
            conversion_source = Path(temporary) / '拖曳 文字.txt'
            conversion_source.write_text('繁體中文：頭髮與發展。', encoding='utf-8')
            drop_file(tab, conversion_source, tab.sourceEdit.viewport())
            assert tab.sourceEdit.toPlainText() == '繁體中文：頭髮與發展。'
            tab.start_conversion()
            deadline = time.monotonic() + 20
            while tab.is_busy() and time.monotonic() < deadline:
                QTest.qWait(10)
            assert not tab.is_busy()
            assert tab.resultEdit.toPlainText() == '繁体中文：头发与发展。'
            checks.append('bundled-opencc-conversion')
            subtitle = '1\n00:00:01,000 --> 00:00:04,000\nFirst\n\n2\n00:00:03,000 --> 00:00:05,000\nSecond\n\n'
            diagnostics_source = Path(temporary) / '拖曳 排錯.srt'
            diagnostics_source.write_text(subtitle, encoding='utf-8')
            drop_file(gui.diagnosticsTab, diagnostics_source, gui.diagnosticsTab.dropZone)
            assert gui.diagnosticsTab.sourceEdit.toPlainText() == subtitle
            fixed = repair_srt(subtitle, trim_overlaps=True)
            assert '00:00:02,999' in fixed.text and not fixed.checked.issues
            checks.append('subtitle-repair')
            encoding_tab = gui.encodingTab
            encoding_source = Path(temporary) / '繁體字幕.srt'
            encoding_text = '1\r\n00:00:01,000 --> 00:00:03,000\r\n這是一段繁體中文字幕，讓電腦能夠正常顯示所有文字。\r\n\r\n'
            encoding_source.write_bytes(encoding_text.encode('cp950'))
            drop_file(encoding_tab, encoding_source, encoding_tab.previewEdit.viewport())
            deadline = time.monotonic() + 20
            while encoding_tab.is_busy() and time.monotonic() < deadline:
                QTest.qWait(10)
            assert not encoding_tab.is_busy() and encoding_tab.result is not None
            assert encoding_tab.result.text == encoding_text
            assert not encoding_tab.saveButton.isEnabled()
            encoding_tab.confirmCheck.setChecked(True)
            encoding_output = Path(temporary) / '繁體字幕_utf8.srt'
            with patch('gui.encoding_tab.QFileDialog.getSaveFileName', return_value=(str(encoding_output), '')):
                encoding_tab.save_utf8()
            assert encoding_output.read_bytes() == encoding_text.encode('utf-8')
            assert encoding_source.read_bytes() == encoding_text.encode('cp950')
            from core.subtitle_encoding import ENCODINGS, decode_subtitle
            for codec in ENCODINGS:
                # Exercise dynamic Python codecs inside the frozen application too.
                assert decode_subtitle('Subtitle\r\n'.encode(codec), codec).text == 'Subtitle\r\n'
            checks.append('subtitle-encoding-detection-and-utf8-export')
            checks.append('subtitle-file-drag-and-drop')
            assert len(ssl_context().get_ca_certs()) > 0
            checks.append('https-trust-store')
            if is_packaged():
                runtime = bundled_runtime()
                assert runtime and Path(runtime['ffmpeg']).is_file()
                assert (resource_root() / 'licenses/THIRD_PARTY_NOTICES.md').is_file()
                checks.extend(['bundled-native-tools', 'license-notices'])
            for language in ('zh_TW', 'zh_CN', 'en', 'ja'):
                gui.change_language(language)
                for theme in (0, 1):
                    gui.current_theme_index = theme
                    gui.update_theme()
                    gui.resize(860, 695)
                    app.processEvents()
                    for page in range(gui.mainTabs.count()):
                        gui.mainTabs.setCurrentIndex(page)
                        app.processEvents()
                        assert gui.mainTabs.currentWidget().isVisible()
            checks.append('four-locales-two-themes-four-tabs')
            gui.change_language('zh_TW')
            gui.resize(1040, 800)
            gui.grab().save(str(report_path.with_suffix('.png')))
            gui.close()
            gui = None
            report = {'ok': True, 'version': VERSION_INFO['version'], 'packaged': is_packaged(), 'checks': checks}
    except Exception:
        report = {'ok': False, 'checks': checks, 'error': traceback.format_exc()}
    finally:
        if gui is not None:
            gui.close()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1
