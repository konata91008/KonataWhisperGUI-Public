"""Offline executable smoke test; never reads or changes real user settings."""
import json
import os
import tempfile
import time
import traceback
from pathlib import Path


def run(report_path):
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checks = []
    gui = None
    try:
        with tempfile.TemporaryDirectory(prefix='tjksub-smoke-') as temporary:
            os.environ['TJKSUB_DATA_DIR'] = str(Path(temporary) / 'data')
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import QSettings
            from PyQt5.QtTest import QTest
            from core.paths import resource_root, data_root, is_packaged, bundled_runtime
            from core.version import VERSION_INFO
            from core.network import ssl_context
            from core.subtitle_diagnostics import repair_srt
            from gui import main_window
            app = QApplication.instance() or QApplication([])
            main_window.QSettings = lambda *args: QSettings(str(Path(temporary) / 'settings.ini'), QSettings.IniFormat)
            gui = main_window.WhisperGUI()
            gui.show()
            app.processEvents()
            assert gui.mainTabs.count() == 3
            assert gui.brandMark.renderer.isValid()
            assert data_root().is_relative_to(Path(temporary).resolve())
            checks.extend(['three-tabs', 'svg-logo', 'isolated-user-data'])
            tab = gui.conversionTab
            gui.mainTabs.setCurrentIndex(1)
            tab.sourceEdit.setPlainText('繁體中文：頭髮與發展。')
            tab.start_conversion()
            deadline = time.monotonic() + 20
            while tab.is_busy() and time.monotonic() < deadline:
                QTest.qWait(10)
            assert not tab.is_busy()
            assert tab.resultEdit.toPlainText() == '繁体中文：头发与发展。'
            checks.append('bundled-opencc-conversion')
            subtitle = '1\n00:00:01,000 --> 00:00:04,000\nFirst\n\n2\n00:00:03,000 --> 00:00:05,000\nSecond\n\n'
            fixed = repair_srt(subtitle, trim_overlaps=True)
            assert '00:00:02,999' in fixed.text and not fixed.checked.issues
            checks.append('subtitle-repair')
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
                    for page in range(3):
                        gui.mainTabs.setCurrentIndex(page)
                        app.processEvents()
                        assert gui.mainTabs.currentWidget().isVisible()
            checks.append('four-locales-two-themes-three-tabs')
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
