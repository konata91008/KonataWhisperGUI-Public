"""Render actual Qt navigation at desktop scaling factors for visual review."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def render(output, scale):
    output.parent.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'WhisperGUI'))
    from PyQt5.QtCore import QSettings, QRect, QPoint, Qt, QMimeData, QUrl
    from PyQt5.QtGui import QImage, QPainter, QColor, QDragEnterEvent, QDragLeaveEvent
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtTest import QTest
    from gui.main_window import WhisperGUI
    app = QApplication([])
    rows = []
    with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'TJKSUB_DATA_DIR': temp}), \
            patch('gui.main_window.QSettings', side_effect=lambda *args: QSettings(str(Path(temp) / 'settings.ini'), QSettings.IniFormat)), \
            patch('gui.main_window.load_runtime', return_value=None):
        window = WhisperGUI()
        window.show()
        window.resize(860, 695)
        sample = Path(temp) / '範例字幕.srt'
        sample.write_bytes(('1\r\n00:00:01,000 --> 00:00:03,500\r\n'
                            '這是一段繁體中文字幕，我們正在測試字幕的編碼，讓電腦能夠正常顯示所有文字。\r\n\r\n'
                            '2\r\n00:00:04,000 --> 00:00:06,000\r\n保留時間碼、格式及換行。\r\n').encode('cp950'))
        window.encodingTab.load_path(sample)
        deadline = time.monotonic() + 20
        while window.encodingTab.is_busy() and time.monotonic() < deadline:
            QTest.qWait(10)
        assert not window.encodingTab.is_busy() and window.encodingTab.result is not None
        for theme in (0, 1):
            window.current_theme_index = theme
            window.update_theme()
            for language in ('zh_TW', 'zh_CN', 'en', 'ja'):
                window.change_language(language)
                images = []
                for selected in range(window.mainTabs.count()):
                    window.mainTabs.setCurrentIndex(selected)
                    QTest.qWait(30)
                    bar = window.mainTabs.tabBar()
                    captured = window.grab(QRect(bar.mapTo(window, QPoint()), bar.size())).toImage()
                    captured.setDevicePixelRatio(1)
                    images.append(captured)
                    if selected > 0:
                        page = window.mainTabs.currentWidget()
                        window.grab().save(str(output.parent / f'page-{selected}-{language}-{theme}-{scale}.png'))
                        mime = QMimeData()
                        mime.setUrls([QUrl.fromLocalFile(str(sample))])
                        enter = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
                        app.sendEvent(page.dropZone, enter)
                        assert enter.isAccepted()
                        app.processEvents()
                        window.grab().save(str(output.parent / f'drop-{selected}-{language}-{theme}-{scale}.png'))
                        app.sendEvent(page.dropZone, QDragLeaveEvent())
                rows.append((f'{language} / {"dark" if theme else "light"}', images))
                window.grab().save(str(output.parent / f'encoding-{language}-{theme}-{scale}.png'))
        window.close()
    gap, label_height = 12, 22
    width = max(sum(image.width() for image in images) + gap * (len(images) + 1) for _, images in rows)
    height = sum(max(image.height() for image in images) + label_height + gap for _, images in rows)
    sheet = QImage(width, height, QImage.Format_RGB32)
    sheet.fill(QColor('#e5e5e5'))
    painter = QPainter(sheet)
    y = 0
    for label, images in rows:
        painter.setPen(QColor('#202020'))
        painter.drawText(gap, y + 16, f'{label} — scale {scale} — selected: 1 / 2 / 3 / 4')
        y += label_height
        x = gap
        for image in images:
            painter.drawImage(x, y, image)
            x += image.width() + gap
        y += max(image.height() for image in images) + gap
    painter.end()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not sheet.save(str(output)):
        raise RuntimeError('Unable to save tab preview')
    print(f'Saved {output} ({width} x {height})', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'build/tab-previews')
    parser.add_argument('--scale')
    args = parser.parse_args()
    if args.scale:
        render(args.output / f'tabs-{args.scale}.png', args.scale)
    else:
        for scale in ('1', '1.25', '1.5', '2'):
            subprocess.run([sys.executable, __file__, '--output', str(args.output), '--scale', scale],
                           env=dict(os.environ, QT_SCALE_FACTOR=scale), check=True, timeout=120)


if __name__ == '__main__':
    main()
