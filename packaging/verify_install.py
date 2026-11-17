"""Launch installed/relocated packages, with isolated settings and data."""
import json
import hashlib
import os
import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(executable, report_name, expected_version=None, expected_kind=None):
    report = ROOT / 'build' / (report_name + '.json')
    env = dict(os.environ, QT_QPA_PLATFORM='windows' if platform.system() == 'Windows' else 'offscreen')
    subprocess.run([str(executable), '--self-test', str(report)], cwd=ROOT.parent,
                   check=True, timeout=120, env=env)
    result = json.loads(report.read_text(encoding='utf-8'))
    assert result['ok'] and result['packaged'], result
    if expected_version:
        assert result['version'] == expected_version, result
    if expected_kind:
        assert result['update_package_kind'] == expected_kind, result
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
        # Real previous release -> current release in one registered installation.
        # Download is pinned by both version and SHA-256, never execute an unverified fixture.
        import sys
        sys.path.insert(0, str(ROOT / 'WhisperGUI'))
        from core.release_updater import open_github, RELEASES_URL
        previous = ROOT / 'build/TJKSub-4.14.1-windows-x64-setup.exe'
        expected = '9185523b0505178aedcc98d247f13b6cabf378fcb7c6f971f8378c27d5d7e91b'
        with open_github(RELEASES_URL + '/download/v4.14.1/' + previous.name) as response:
            content = response.read(39040293 + 1)
        assert len(content) == 39040293 and hashlib.sha256(content).hexdigest() == expected
        previous.write_bytes(content)
        arguments = ['/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/DIR=' + str(target)]
        from PyQt5.QtCore import QSettings
        settings = QSettings('Konata', 'KonataSub')
        sentinel_key = 'update_verification_sentinel'
        assert not settings.contains(sentinel_key)
        settings.setValue(sentinel_key, 'keep settings through upgrade')
        settings.sync()
        model = Path(os.environ['LOCALAPPDATA']) / 'TJKSub/models/update-verification-sentinel.txt'
        model.parent.mkdir(parents=True, exist_ok=True)
        with model.open('xb') as stream:
            stream.write(b'keep model through upgrade')
        try:
            subprocess.run([str(previous), *arguments], check=True, timeout=180)
            check(target / 'TJKSub.exe', 'previous-installed-smoke', '4.14.1')
            subprocess.run([str(installer), *arguments], check=True, timeout=180)
            check(target / 'TJKSub.exe', 'installed-smoke', version, 'windows-setup')
            check(ROOT / 'dist/TJKSub/TJKSub.exe', 'portable-smoke', version, 'windows-portable')
            settings.sync()
            assert settings.value(sentinel_key) == 'keep settings through upgrade'
            assert model.read_bytes() == b'keep model through upgrade'
            print('Previous release upgrade retained models and settings; installation kind matched.')
        finally:
            settings.remove(sentinel_key)
            settings.sync()
            model.unlink()
            uninstaller = target / 'unins000.exe'
            if uninstaller.is_file():
                subprocess.run([str(uninstaller), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], check=True, timeout=120)


if __name__ == '__main__':
    main()
