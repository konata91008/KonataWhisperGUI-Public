"""Reconcile checksums after platform artifacts are merged for publication."""
import hashlib
import sys
from pathlib import Path


def reconcile(folder):
    folder = Path(folder)
    manifests = sorted(folder.glob('SHA256SUMS-*.txt'))
    if not manifests:
        raise RuntimeError('No platform checksum manifests were found')
    for manifest in manifests:
        entries = []
        for line in manifest.read_text(encoding='utf-8').splitlines():
            _, name = line.split('  ', 1)
            if Path(name).name != name or not (folder / name).is_file():
                raise RuntimeError('Invalid checksum target: ' + name)
            digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
            entries.append(digest + '  ' + name)
        manifest.write_text('\n'.join(entries) + '\n', encoding='utf-8', newline='\n')
    print('Reconciled', len(manifests), 'manifests against the exact published files')


if __name__ == '__main__':
    reconcile(sys.argv[1])
