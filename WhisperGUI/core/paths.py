"""Separate immutable application resources from writable per-user data."""
import os
import platform
import sys
from pathlib import Path


def is_packaged():
    return bool(getattr(sys, 'frozen', False))


def resource_root():
    return Path(sys._MEIPASS) if is_packaged() else Path(__file__).resolve().parents[2]


def data_root():
    override = os.environ.get('TJKSUB_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if not is_packaged():
        return resource_root() / 'whisper.cpp'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'TJKSub'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/TJKSub'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'TJKSub'


def bundled_runtime():
    if not is_packaged():
        return None
    import json
    root = resource_root()
    try:
        manifest = json.loads((root / 'native/runtime.json').read_text(encoding='utf-8'))
        system, machine = platform.system(), platform.machine().lower()
        if manifest['system'] != system or manifest['machine'] != machine:
            return None
        if manifest['backend'] not in ('metal', 'vulkan'):
            return None
        suffix = '.exe' if sys.platform == 'win32' else ''
        engine, ffmpeg = root / ('native/whisper-cli' + suffix), root / ('native/ffmpeg' + suffix)
        if not engine.is_file() or not ffmpeg.is_file():
            return None
        return {'backend': manifest['backend'], 'path': str(engine), 'ffmpeg': str(ffmpeg),
                'gpu': {'name': 'Bundled ' + manifest['backend'].title()},
                'runtime_bins': [str(engine.parent)], 'device_env': {}, 'packaged': True}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def restart_command():
    if is_packaged():
        return sys.executable, ['--restarted'], str(Path(sys.executable).parent)
    return sys.executable, [str(resource_root() / 'WhisperGUI/main.py'), '--restarted'], str(resource_root())
