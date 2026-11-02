"""Render actual Qt navigation at desktop scaling factors for visual review."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def render(output, scale):
    sys.path.insert(0, str(ROOT / 'WhisperGUI'))
    from PyQt5.QtCore import QSettings, QRect, QPoint
    from PyQt5.QtGui import QImage, QPainter, QColor
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
        for theme in (0, 1):
            window.current_theme_index = theme
            window.update_theme()
            for language in ('zh_TW', 'zh_CN', 'en', 'ja'):
                window.change_language(language)
                images = []
                for selected in range(3):
                    window.mainTabs.setCurrentIndex(selected)
                    QTest.qWait(30)
                    bar = window.mainTabs.tabBar()
                    captured = window.grab(QRect(bar.mapTo(window, QPoint()), bar.size())).toImage()
                    captured.setDevicePixelRatio(1)
                    images.append(captured)
                rows.append((f'{language} / {"dark" if theme else "light"}', images))
        window.close()
    gap, label_height = 12, 22
    width = max(sum(image.width() for image in images) + gap * 4 for _, images in rows)
    height = sum(max(image.height() for image in images) + label_height + gap for _, images in rows)
    sheet = QImage(width, height, QImage.Format_RGB32)
    sheet.fill(QColor('#e5e5e5'))
    painter = QPainter(sheet)
    y = 0
    for label, images in rows:
        painter.setPen(QColor('#202020'))
        painter.drawText(gap, y + 16, f'{label} — scale {scale} — selected: 1 / 2 / 3')
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
