# Build with: python -m PyInstaller --noconfirm --clean packaging/TJKSub.spec
import json
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
version = json.loads((root / 'WhisperGUI/version.json').read_text())['version']
windows = sys.platform == 'win32'
icon = str(root / 'packaging/generated' / ('TJKSub.ico' if windows else 'TJKSub.icns'))
native = root / 'build/native'
suffix = '.exe' if windows else ''
required = [native / ('whisper-cli' + suffix), native / ('ffmpeg' + suffix), native / 'runtime.json']
assert all(path.is_file() for path in required), 'Build native tools first'
binaries = [(str(path), 'native') for path in native.iterdir() if path.suffix.lower() != '.json']
datas = [(str(root / 'WhisperGUI/version.json'), 'WhisperGUI'),
         (str(root / 'WhisperGUI/gui/resources'), 'WhisperGUI/gui/resources'),
         (str(root / 'WhisperGUI/gui/resources'), 'gui/resources'),
         (str(native / 'runtime.json'), 'native'), (str(root / 'build/licenses'), 'licenses')]
datas += collect_data_files('opencc') + collect_data_files('certifi')
a = Analysis([str(root / 'WhisperGUI/main.py')], pathex=[str(root / 'WhisperGUI')],
    binaries=binaries, datas=datas, hiddenimports=['PyQt5.QtSvg', 'PyQt5.QtTest'],
    excludes=['tkinter', 'matplotlib', 'numpy', 'PIL'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='TJKSub',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=icon, disable_windowed_traceback=False,
          version=str(root / 'packaging/generated/windows-version.txt') if windows else None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='TJKSub')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='TJKSub.app', icon=icon, bundle_identifier='com.konata.tjksub',
                 version=version, info_plist={'CFBundleShortVersionString': version,
                    'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '12.0',
                    'NSHumanReadableCopyright': 'GNU GPL v3 or later · konata91008'})
