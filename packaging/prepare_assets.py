import json
import os
import shutil
import sys
import sysconfig
from importlib.metadata import distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtSvg import QSvgRenderer
    from PyQt5.QtCore import Qt, QRectF
    from PyQt5.QtGui import QImage, QPainter
    from PIL import Image
    app = QApplication.instance() or QApplication([])
    generated = ROOT / 'packaging/generated'
    generated.mkdir(parents=True, exist_ok=True)
    renderer = QSvgRenderer(str(ROOT / 'WhisperGUI/gui/resources/autumn-logo.svg'))
    assert renderer.isValid()
    image = QImage(1024, 1024, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, 1024, 1024))
    painter.end()
    image.save(str(generated / 'TJKSub.png'))
    logo = Image.open(generated / 'TJKSub.png')
    logo.save(generated / 'TJKSub.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    logo.save(generated / 'TJKSub.icns')
    licenses = ROOT / 'build/licenses'
    licenses.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'LICENSE', licenses / 'TJKSub-GPL-3.0.txt')
    shutil.copy2(ROOT / 'LICENSE', licenses / 'PyQt5-GPL-3.0.txt')
    shutil.copy2(ROOT / 'packaging/THIRD_PARTY_NOTICES.md', licenses)
    if sys.platform == 'win32':
        shutil.copy2(ROOT / 'packaging/licenses/Vulkan-Loader-LICENSE.txt', licenses)
    for name in ('PyQt5-Qt5', 'PyQt5-sip', 'opencc-python-reimplemented', 'certifi', 'charset-normalizer', 'pyinstaller'):
        package = distribution(name)
        for entry in package.files or ():
            if entry.name.lower().startswith(('license', 'copying', 'copyright')):
                source = Path(package.locate_file(entry))
                if source.is_file():
                    destination = licenses / name / entry.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
    if not python_license.exists():
        python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise RuntimeError('CPython license file is missing from this build environment')
    shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    ffmpeg = ROOT / 'build/ffmpeg-9.0.2'
    for source in ffmpeg.glob('COPYING*'):
        shutil.copy2(source, licenses / ('FFmpeg-' + source.name))
    for source in (ROOT / 'whisper.cpp').rglob('*'):
        if source.is_file() and source.name.lower().startswith(('license', 'copying')):
            destination = licenses / 'whisper.cpp' / source.relative_to(ROOT / 'whisper.cpp')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    version = json.loads((ROOT / 'WhisperGUI/version.json').read_text())['version']
    digits = tuple(int(part) for part in version.split('.')) + (0,)
    (generated / 'windows-version.txt').write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={digits!r}, prodvers={digits!r}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'konata91008'), StringStruct('FileDescription', 'TJKSub'),
    StringStruct('FileVersion', '{version}'), StringStruct('ProductName', 'TJKSub'),
    StringStruct('ProductVersion', '{version}'), StringStruct('OriginalFilename', 'TJKSub.exe'),
    StringStruct('LegalCopyright', 'GPL-3.0-or-later')])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
''', encoding='utf-8')


if __name__ == '__main__':
    prepare()
