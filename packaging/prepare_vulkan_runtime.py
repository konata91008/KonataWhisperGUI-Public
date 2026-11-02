"""Bundle the official x64 loader without installing a system-wide runtime."""
import hashlib
import json
import shutil
import struct
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(native):
    info = json.loads((ROOT / 'packaging/sources.json').read_text())['vulkan_runtime']
    name = 'VulkanRT-X64-' + info['version'] + '-Components'
    archive = ROOT / 'build/downloads' / (name + '.zip')
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.is_file():
        request = urllib.request.Request(info['url'], headers={'User-Agent': 'TJKSub-build/4.13.0'})
        with urllib.request.urlopen(request, timeout=90) as response, archive.with_suffix('.part').open('wb') as output:
            shutil.copyfileobj(response, output)
        archive.with_suffix('.part').replace(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != info['sha256']:
        raise RuntimeError('Vulkan runtime checksum mismatch')
    with zipfile.ZipFile(archive) as files:
        binary = files.read(name + '/x64/vulkan-1.dll')
        pe = struct.unpack_from('<I', binary, 0x3c)[0]
        if binary[pe:pe+4] != b'PE\0\0' or struct.unpack_from('<H', binary, pe+4)[0] != 0x8664:
            raise RuntimeError('The Vulkan loader is not an x64 PE binary')
        native.mkdir(parents=True, exist_ok=True)
        (native / 'vulkan-1.dll').write_bytes(binary)
        licenses = ROOT / 'build/licenses/vulkan'
        licenses.mkdir(parents=True, exist_ok=True)
        (licenses / 'VulkanRT-License.txt').write_bytes(files.read(name + '/VulkanRT-License.txt'))
