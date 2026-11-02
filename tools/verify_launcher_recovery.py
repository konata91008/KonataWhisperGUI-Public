"""Destructive fixtures are confined to a temporary copy, never the user's venv."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='tjksub-launcher-') as temp:
        root = Path(temp) / '啟動測試 with spaces'; root.mkdir()
        for name in ('WhisperGUI', 'tools'):
            shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('Start_Windows.bat', 'start_mac.command', 'requirements.txt', 'CHANGELOG.md'):
            shutil.copy2(ROOT / name, root / name)
        (root / 'venv').mkdir(); (root / 'venv/broken-marker').write_text('preserve me')
        (root / 'models').mkdir(); (root / 'models/user-model.bin').write_bytes(b'keep model')
        env = dict(os.environ, CI='true', PYTHONUTF8='1')
        if os.name == 'nt':
            command = ['cmd.exe', '/d', '/c', 'tools\\setup_windows.bat']
            python = root / 'venv/Scripts/python.exe'
        else:
            command = ['bash', 'tools/setup_mac.command']
            python = root / 'venv/bin/python'
        def launch(name):
            report = root / (name + '.json')
            subprocess.run(command + ['--self-test', str(report)], cwd=root, env=env, check=True, timeout=600)
            assert json.loads(report.read_text(encoding='utf-8'))['ok']
        launch('rebuilt-environment')
        backups = list(root.glob('venv.backup-*/broken-marker'))
        assert len(backups) == 1 and backups[0].read_text() == 'preserve me'
        # Keep pip metadata but remove a module, as with an interrupted install.
        subprocess.run([str(python), '-c', 'import opencc; from pathlib import Path; Path(opencc.__file__).unlink()'], check=True)
        launch('repaired-package')
        assert (root / 'models/user-model.bin').read_bytes() == b'keep model'
        report = {'ok': True, 'broken_venv_backed_up': True, 'corrupt_package_reinstalled': True,
                  'model_preserved': True, 'unicode_source_path': True, 'setup_launcher': True}
        (ROOT / 'build').mkdir(exist_ok=True)
        (ROOT / 'build/launcher-recovery.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))


if __name__ == '__main__': main()
