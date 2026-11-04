"""A shared, copy-only file drop surface for the subtitle tools."""
from pathlib import Path

from PyQt5.QtCore import Qt, QEvent, QTimer
from PyQt5.QtWidgets import QFrame, QLabel, QSizePolicy


STRINGS = {
    'zh_TW': {
        'ready': '↓ 拖曳一個 {formats} 檔案到這裡', 'active': '放開即可匯入檔案',
        'busy': '處理中，請稍候再拖入檔案', 'single': '一次請拖入一個檔案',
        'local': '請從電腦拖入檔案，不支援網頁連結', 'type': '支援格式：{formats}',
        'file': '請拖入可讀取的檔案，不支援資料夾', 'copy': '請以複製方式拖入，原始檔會保留',
    },
    'zh_CN': {
        'ready': '↓ 将一个 {formats} 文件拖到这里', 'active': '松开即可导入文件',
        'busy': '处理中，请稍后再拖入文件', 'single': '一次请拖入一个文件',
        'local': '请从电脑拖入文件，不支持网页链接', 'type': '支持格式：{formats}',
        'file': '请拖入可读取的文件，不支持文件夹', 'copy': '请以复制方式拖入，将保留原始文件',
    },
    'en': {
        'ready': '↓ Drop one {formats} file here', 'active': 'Release to import the file',
        'busy': 'Processing; drop a file when finished', 'single': 'Drop one file at a time',
        'local': 'Drop a file from your computer, not a web link', 'type': 'Supported: {formats}',
        'file': 'Drop a readable file, not a folder', 'copy': 'Use a copy drag to preserve the original file',
    },
    'ja': {
        'ready': '↓ {formats} ファイルを1つドロップ', 'active': '離すとファイルを読み込みます',
        'busy': '処理中です。完了後にドロップしてください', 'single': 'ファイルは1つずつドロップしてください',
        'local': 'Web リンクではなくローカルファイルを指定', 'type': '対応形式：{formats}',
        'file': 'フォルダーではなく読み取り可能なファイルを指定', 'copy': '元ファイルを保持するためコピーでドロップ',
    },
}


class FileDropZone(QFrame):
    def __init__(self, page, extensions, formats):
        super().__init__(page, objectName='SubtitleDropZone')
        self.page, self.extensions, self.formats = page, extensions, formats
        self.language, self.hint_key = page.owner.current_lang, 'ready'
        self.setAcceptDrops(True)
        self.hint = QLabel(self, objectName='DropHint')
        self.hint.setTextFormat(Qt.PlainText)
        self.hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.resetTimer = QTimer(self)
        self.resetTimer.setSingleShot(True)
        self.resetTimer.timeout.connect(self.clear_feedback)
        self.clear_feedback()

    def retranslate_ui(self, language):
        self.language = language
        self.refresh()

    def refresh(self):
        key = 'busy' if self.page.is_busy() else self.hint_key
        strings = STRINGS.get(self.language, STRINGS['en'])
        text = strings[key].format(formats=self.formats)
        self.hint.setText(text)
        self.hint.setToolTip(text)
        self.setAccessibleName(text)
        self.setToolTip(text)
        state = 'active' if key == 'active' else 'idle' if key in ('ready', 'busy') else 'error'
        if self.property('dropState') != state:
            self.setProperty('dropState', state)
            self.style().unpolish(self)
            self.style().polish(self)
            self.update()

    def clear_feedback(self):
        self.resetTimer.stop()
        self.hint_key = 'ready'
        self.refresh()

    def _candidate(self, event):
        if self.page.is_busy():
            return None, 'busy'
        mime = event.mimeData()
        if not mime.hasUrls():
            return None, 'local'
        urls = mime.urls()
        if len(urls) != 1:
            return None, 'single'
        if not urls[0].isLocalFile():
            return None, 'local'
        if not event.possibleActions() & Qt.CopyAction:
            return None, 'copy'
        path = Path(urls[0].toLocalFile())
        try:
            is_file = path.is_file()
        except (OSError, ValueError):
            is_file = False
        if not is_file:
            return None, 'file'
        if path.suffix.lower() not in self.extensions:
            return None, 'type'
        return path, None

    def _reject(self, event, key):
        self.hint_key = key
        self.refresh()
        self.resetTimer.start(1800)
        event.ignore()

    def dragEnterEvent(self, event):
        self.resetTimer.stop()
        _, error = self._candidate(event)
        if error:
            self._reject(event, error)
            return
        self.hint_key = 'active'
        self.refresh()
        event.setDropAction(Qt.CopyAction)
        event.accept()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        self.clear_feedback()
        event.accept()

    def dropEvent(self, event):
        path, error = self._candidate(event)
        self.clear_feedback()
        if error:
            self._reject(event, error)
            return
        event.setDropAction(Qt.CopyAction)
        event.accept()
        self.page.load_path(path)

    def attach_editor(self, editor):
        # Consume file URLs before QTextEdit can insert their paths as text.
        # Both editor and viewport matter for native Qt drag delivery.
        for widget in (editor, editor.viewport()):
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        handlers = {QEvent.DragEnter: self.dragEnterEvent, QEvent.DragMove: self.dragMoveEvent,
                    QEvent.DragLeave: self.dragLeaveEvent, QEvent.Drop: self.dropEvent}
        handler = handlers.get(event.type())
        if handler:
            handler(event)
            return True
        return super().eventFilter(watched, event)
