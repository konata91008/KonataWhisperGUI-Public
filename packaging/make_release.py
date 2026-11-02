"""Package only built, tested binaries; never include a local environment or models."""
import hashlib
import json
import platform
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    version = json.loads((ROOT / 'WhisperGUI/version.json').read_text())['version']
    out = ROOT / 'release-artifacts'
    out.mkdir(exist_ok=True)
    if platform.system() == 'Darwin':
        arch = platform.machine()
        app = ROOT / 'dist/TJKSub.app'
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        staging = ROOT / 'build/dmg'
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        subprocess.run(['ditto', str(app), str(staging / app.name)], check=True)
        (staging / 'Applications').symlink_to('/Applications')
        shutil.copy2(ROOT / 'packaging/INSTALL.md', staging / 'Read me.txt')
        command = ['hdiutil', 'create', '-volname', 'TJKSub', '-srcfolder', str(staging),
                   '-ov', '-format', 'UDZO', str(out / f'TJKSub-{version}-macos-{arch}.dmg')]
        # DiskImages on hosted Macs can briefly hold a staging volume open.
        # Retry only this explicit transient error; propagate all other failures.
        for attempt in range(3):
            result = subprocess.run(command, capture_output=True, text=True)
            print(result.stdout, end='')
            print(result.stderr, end='')
            if result.returncode == 0:
                break
            if 'Resource busy' not in result.stderr or attempt == 2:
                result.check_returncode()
            time.sleep(5 * (attempt + 1))
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app),
                        str(out / f'TJKSub-{version}-macos-{arch}.zip')], check=True)
    else:
        compiler = shutil.which('ISCC') or r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
        subprocess.run([compiler, '/DAppVersion=' + version, str(ROOT / 'packaging/windows.iss')], check=True)
        shutil.make_archive(str(out / f'TJKSub-{version}-windows-x64-portable'), 'zip', ROOT / 'dist', 'TJKSub')
    # Exact corresponding FFmpeg sources accompany binaries on the same release.
    shutil.copy2(ROOT / 'build/downloads/ffmpeg-9.0.2.tar.xz', out)
    shutil.copy2(ROOT / 'packaging/THIRD_PARTY_NOTICES.md', out)
    shutil.copy2(ROOT / 'packaging/INSTALL.md', out)
    label = platform.system().lower() + '-' + platform.machine().lower()
    sums = [hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name
            for path in sorted(out.iterdir()) if path.is_file() and not path.name.startswith('SHA256SUMS')]
    (out / ('SHA256SUMS-' + label + '.txt')).write_text('\n'.join(sums) + '\n')


if __name__ == '__main__':
    main()
