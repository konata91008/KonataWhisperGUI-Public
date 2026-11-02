"""Launch installed/relocated packages, with isolated settings and data."""
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(executable, report_name):
    report = ROOT / 'build' / (report_name + '.json')
    env = dict(os.environ, QT_QPA_PLATFORM='windows' if platform.system() == 'Windows' else 'offscreen')
    subprocess.run([str(executable), '--self-test', str(report)], cwd=ROOT.parent,
                   check=True, timeout=120, env=env)
    result = json.loads(report.read_text(encoding='utf-8'))
    assert result['ok'] and result['packaged'], result
    print(report_name, 'OK')


def main():
    version = json.loads((ROOT / 'WhisperGUI/version.json').read_text())['version']
    target = ROOT / 'build/安裝測試 with spaces'
    target.mkdir(parents=True, exist_ok=True)
    if platform.system() == 'Darwin':
        application = target / 'TJKSub.app'
        subprocess.run(['ditto', str(ROOT / 'dist/TJKSub.app'), str(application)], check=True)
        check(application / 'Contents/MacOS/TJKSub', 'relocated-smoke')
        image = ROOT / 'release-artifacts' / f'TJKSub-{version}-macos-{platform.machine()}.dmg'
        mount = ROOT / 'build/dmg-mounted'
        mount.mkdir(exist_ok=True)
        subprocess.run(['hdiutil', 'attach', str(image), '-readonly', '-nobrowse', '-mountpoint', str(mount)], check=True)
        try:
            check(mount / 'TJKSub.app/Contents/MacOS/TJKSub', 'readonly-dmg-smoke')
        finally:
            subprocess.run(['hdiutil', 'detach', str(mount)], check=True)
    else:
        installer = ROOT / 'release-artifacts' / f'TJKSub-{version}-windows-x64-setup.exe'
        subprocess.run([str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/DIR=' + str(target)],
                       check=True, timeout=180)
        check(target / 'TJKSub.exe', 'installed-smoke')
        subprocess.run([str(target / 'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], check=True, timeout=120)


if __name__ == '__main__':
    main()
