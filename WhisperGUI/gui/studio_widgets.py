"""Small painted elements that follow the application's light and dark palettes."""
from pathlib import Path
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QListWidget, QWidget


def draw_wave(painter, center_x, center_y, color, scale=1):
    painter.setPen(QPen(QColor(color), 2.6 * scale, Qt.SolidLine, Qt.RoundCap))
    for offset, height in zip((-12, -6, 0, 6, 12), (9, 20, 28, 16, 8)):
        x = center_x + offset * scale
        half = height * scale / 2
        painter.drawLine(int(x), int(center_y - half), int(x), int(center_y + half))


class BrandMark(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self.renderer = QSvgRenderer(str(Path(__file__).parent / 'resources' / 'autumn-logo.svg'), self)

    def setThemeColors(self, colors):
        self.colors = colors
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.renderer.render(painter, QRectF(0, 0, 48, 48))


class MediaFileList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('FileList')
        self.colors = {}
        self.empty_title, self.empty_hint = '', ''

    def set_empty_text(self, title, hint):
        self.empty_title, self.empty_hint = title, hint
        self.viewport().update()

    def setThemeColors(self, colors):
        self.colors = colors
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count():
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        width, height = self.viewport().width(), self.viewport().height()
        center_y = max(48, height / 2 - 48)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.colors.get('BG_SECONDARY', '#ede6dc')))
        painter.drawRoundedRect(QRectF(width / 2 - 30, center_y - 30, 60, 60), 20, 20)
        draw_wave(painter, width / 2, center_y, self.colors.get('ACCENT', '#805e46'), 1.1)
        font = QFont(self.font())
        font.setPixelSize(16)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(self.colors.get('TEXT_PRIMARY', '#302b27')))
        painter.drawText(QRectF(12, center_y + 48, width - 24, 28), Qt.AlignCenter, self.empty_title)
        font.setPixelSize(12)
        font.setWeight(QFont.Normal)
        painter.setFont(font)
        painter.setPen(QColor(self.colors.get('TEXT_TERTIARY', '#7e7368')))
        painter.drawText(QRectF(12, center_y + 86, width - 24, 70), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.empty_hint)
