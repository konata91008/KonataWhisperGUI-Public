"""Download a pinned FFmpeg source archive; the same archive ships with releases."""
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    info = json.loads((ROOT / 'packaging/sources.json').read_text())['ffmpeg']
    folder = ROOT / 'build/downloads'
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / ('ffmpeg-' + info['version'] + '.tar.xz')
    if not archive.is_file():
        with urllib.request.urlopen(info['url'], timeout=60) as response, archive.with_suffix('.part').open('wb') as output:
            shutil.copyfileobj(response, output)
        archive.with_suffix('.part').replace(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != info['sha256']:
        raise RuntimeError('FFmpeg source checksum mismatch')
    source = ROOT / 'build' / ('ffmpeg-' + info['version'])
    if not source.exists():
        with tarfile.open(archive) as compressed:
            compressed.extractall(ROOT / 'build', filter='data')
    return source


if __name__ == '__main__':
    print(prepare())
