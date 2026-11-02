"""Install verified NVIDIA redistributables without running IDE/driver installers."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import urllib.request
import uuid
import zipfile
from .network import ssl_context

BASE_URL = 'https://developer.download.nvidia.com/compute/cuda/redist/'


def toolchain_root():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local') / 'TJKSub/toolchains'


def extract_component(archive, destination, component):
    """Remove NVIDIA's top-level archive directory, rejecting unsafe ZIP entries."""
    destination = Path(destination)
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            name = item.filename.replace('\\', '/')
            path = PurePosixPath(name)
            if path.is_absolute() or any(p in ('.', '..') or ':' in p for p in path.parts):
                raise RuntimeError('CUDA archive contains an unsafe path')
            if stat.S_ISLNK(item.external_attr >> 16):
                raise RuntimeError('CUDA archive contains an unexpected symlink')
            if item.is_dir() or len(path.parts) < 2:
                continue
            relative = Path(*path.parts[1:])
            if relative.name.upper().startswith('LICENSE'):
                relative = Path('licenses') / component / relative
            elif component == 'visual_studio_integration':
                # CMake's custom CUDA toolset reads these files directly.
                # IDE project wizards are unnecessary and are not registered.
                if relative.parts[:2] != ('visual_studio_integration', 'MSBuildExtensions'):
                    continue
                relative = Path('extras') / relative
            target = destination / relative
            if not target.resolve().is_relative_to(destination.resolve()):
                raise RuntimeError('CUDA archive path escaped its destination')
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(item) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)


def download_package(package, destination, log):
    request = urllib.request.Request(BASE_URL + package['path'], headers={'User-Agent': 'TJKSub-CUDA-Setup/4.13.1'})
    digest = hashlib.sha256()
    count, reported = 0, 0
    with urllib.request.urlopen(request, context=ssl_context(), timeout=120) as response, Path(destination).open('wb') as output:
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            if count > package['size']:
                raise RuntimeError('CUDA download exceeds the pinned package size')
            digest.update(chunk); output.write(chunk)
            if count - reported >= 32 * 1024 * 1024:
                log(f"  {package['component']}: {count // (1024 * 1024)} / {package['size'] // (1024 * 1024)} MB")
                reported = count
    if count != package['size'] or digest.hexdigest() != package['sha256']:
        raise RuntimeError('CUDA 下載不完整或 SHA256 不符，未安裝；請檢查網路後重試。')


def install_cuda(version, log):
    with Path(__file__).with_name('cuda_sources.json').open(encoding='utf-8') as source:
        plan = json.load(source)[version]
    root = toolchain_root()
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < sum(p['size'] for p in plan['packages']) * 4:
        raise RuntimeError('CUDA 工具安裝空間不足，請先釋出約 3 GB 空間。')
    with tempfile.TemporaryDirectory(prefix='.cuda-', dir=root) as temporary:
        staging = Path(temporary) / 'toolkit'; staging.mkdir()
        for package in plan['packages']:
            log(f"下載 NVIDIA 官方 {package['component']}（CUDA {plan['release']}），驗證 SHA256 後安裝。")
            archive = Path(temporary) / 'component.zip'
            download_package(package, archive, log)
            extract_component(archive, staging, package['component'])
            archive.unlink()
        # Publish an immutable directory only after every package is verified.
        (staging / 'tjksub-cuda.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
        destination = root / f'v{version}-{uuid.uuid4().hex[:8]}'
        staging.rename(destination)
    log(f'CUDA 工具已安裝於 {destination}；未修改顯示卡驅動或 Visual Studio IDE。')
    return destination
