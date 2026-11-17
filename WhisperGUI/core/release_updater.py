"""Explicit, verified downloads of official desktop releases. Never updates source trees."""
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .network import ssl_context
from .paths import data_root
from .updater import REPOSITORY, UpdateError
from .version import VERSION_INFO

API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
RELEASES_URL = f'https://github.com/{REPOSITORY}/releases'
MAX_PACKAGE = 1024 * 1024 * 1024
INSTALL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{AB1C41CF-B5D9-4A07-8467-F6E81FC20A21}_is1'


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise UpdateError('invalid_release')
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


def windows_installed(executable=None):
    """A copied/portable EXE must not update some other registered installation."""
    executable = Path(executable or sys.executable).resolve()
    if executable.name.lower() != 'tjksub.exe':
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INSTALL_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            location = winreg.QueryValueEx(key, 'InstallLocation')[0]
        return bool(location) and Path(location).resolve() == executable.parent
    except (ImportError, OSError, ValueError):
        return False


def package_kind():
    system, arch = sys.platform, platform.machine().lower()
    if system == 'win32' and arch in ('amd64', 'x86_64'):
        return 'windows-setup' if windows_installed() else 'windows-portable'
    if system == 'darwin' and arch in ('arm64', 'x86_64'):
        # Prefer Apple Silicon even when an Intel app is running under Rosetta.
        if arch == 'x86_64':
            import subprocess
            try:
                if subprocess.run(['/usr/sbin/sysctl', '-in', 'sysctl.proc_translated'],
                                  capture_output=True, timeout=3).stdout.strip() == b'1':
                    arch = 'arm64'
            except (OSError, subprocess.TimeoutExpired):
                pass
        return 'macos-' + arch
    raise UpdateError('unsupported_platform')


def allowed_url(url):
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and parsed.port in (None, 443) and parsed.hostname in (
                'api.github.com', 'github.com', 'release-assets.githubusercontent.com',
                'objects.githubusercontent.com'))


class GitHubRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise UpdateError('invalid_release')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_github(url):
    if not allowed_url(url):
        raise UpdateError('invalid_release')
    opener = urllib.request.build_opener(GitHubRedirects(),
                urllib.request.HTTPSHandler(context=ssl_context()))
    request = urllib.request.Request(url, headers={
        'User-Agent': 'TJKSub/' + VERSION_INFO['version'],
        'Accept': 'application/vnd.github+json' if url == API_URL else 'application/octet-stream',
    })
    try:
        return opener.open(request, timeout=20)
    except urllib.error.HTTPError as error:
        raise UpdateError('rate_limit' if error.code in (403, 429) else
                          'no_release' if error.code == 404 else 'network_error') from None
    except (OSError, urllib.error.URLError):
        raise UpdateError('network_error') from None


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    date: str
    notes: str
    kind: str
    available: bool
    name: str = ''
    url: str = ''
    size: int = 0
    checksum_url: str = ''
    digest: str = ''


@dataclass(frozen=True)
class DownloadedUpdate:
    info: ReleaseInfo
    path: Path
    sha256: str


class ReleaseUpdater:
    def __init__(self, kind=None, current=None, folder=None, opener=None):
        self.kind = kind or package_kind()
        self.current = current or VERSION_INFO['version']
        self.folder = Path(folder) if folder is not None else data_root() / 'updates'
        self.open = opener or open_github

    def _read(self, url, limit):
        with self.open(url) as response:
            data = response.read(limit + 1)
        if len(data) > limit:
            raise UpdateError('invalid_release')
        return data

    def check(self):
        try:
            release = json.loads(self._read(API_URL, 2 * 1024 * 1024))
            return self.parse_release(release)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise UpdateError('invalid_release') from None

    def parse_release(self, release):
        tag = release['tag_name']
        version = version_tuple(tag)
        if not tag.startswith('v') or release.get('draft') is not False or release.get('prerelease') is not False:
            raise UpdateError('invalid_release')
        date = str(release.get('published_at', ''))[:10]
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
            raise UpdateError('invalid_release')
        info = dict(version=tag[1:], date=date, notes=str(release.get('body') or '')[:30000],
                    kind=self.kind, available=version > version_tuple(self.current))
        if not info['available']:
            return ReleaseInfo(**info)
        suffixes = {
            'windows-setup': ('windows-x64-setup.exe', 'windows-amd64'),
            'windows-portable': ('windows-x64-portable.zip', 'windows-amd64'),
            'macos-arm64': ('macos-arm64.dmg', 'darwin-arm64'),
            'macos-x86_64': ('macos-x86_64.dmg', 'darwin-x86_64'),
        }
        if self.kind not in suffixes:
            raise UpdateError('unsupported_platform')
        suffix, checksum_platform = suffixes[self.kind]
        name = f'TJKSub-{tag[1:]}-{suffix}'
        checksum = f'SHA256SUMS-{checksum_platform}.txt'
        base = f'{RELEASES_URL}/download/{tag}/'
        assets = release['assets']
        def asset_named(filename, limit):
            matches = [a for a in assets if a.get('name') == filename]
            if len(matches) != 1:
                raise UpdateError('missing_package')
            asset = matches[0]
            if (asset.get('state') != 'uploaded' or type(asset.get('size')) is not int
                    or not 0 < asset['size'] <= limit or asset.get('browser_download_url') != base + filename):
                raise UpdateError('invalid_release')
            return asset
        asset = asset_named(name, MAX_PACKAGE)
        asset_named(checksum, 65536)
        digest = asset.get('digest') or ''
        if digest and not re.fullmatch('sha256:[0-9a-f]{64}', digest):
            raise UpdateError('invalid_release')
        return ReleaseInfo(**info, name=name, url=base + name, size=asset['size'],
                           checksum_url=base + checksum, digest=digest.removeprefix('sha256:'))

    def download(self, info, cancel, progress):
        if not info.available or info.kind != self.kind:
            raise UpdateError('invalid_release')
        def cancelled():
            if cancel.is_set():
                raise UpdateError('cancelled')
        cancelled()
        try:
            manifest = self._read(info.checksum_url, 65536).decode('utf-8')
            digests = []
            for line in manifest.splitlines():
                match = re.fullmatch(r'([0-9a-fA-F]{64})  (.+)', line)
                if match and match[2] == info.name:
                    digests.append(match[1].lower())
            if len(digests) != 1 or (info.digest and digests[0] != info.digest):
                raise UpdateError('checksum_error')
            expected = digests[0]
        except UnicodeError:
            raise UpdateError('checksum_error') from None
        cancelled()
        self.folder.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=info.version + '-', dir=self.folder))
        try:
            path = temporary / info.name
            partial = temporary / (info.name + '.part')
            count, digest = 0, hashlib.sha256()
            with self.open(info.url) as response, partial.open('xb') as output:
                progress(0, info.size)
                while True:
                    cancelled()
                    block = response.read(256 * 1024)
                    if not block:
                        break
                    count += len(block)
                    if count > info.size:
                        raise UpdateError('checksum_error')
                    output.write(block)
                    digest.update(block)
                    progress(count, info.size)
            cancelled()
            if count != info.size or digest.hexdigest() != expected:
                raise UpdateError('checksum_error')
            partial.replace(path)
            return DownloadedUpdate(info, path, expected)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    def verify(self, downloaded):
        """Recheck after the user has chosen to open/install a saved download."""
        path, info = downloaded.path, downloaded.info
        if (info.kind != self.kind or path.name != info.name or path.is_symlink()
                or not path.resolve().is_relative_to(self.folder.resolve())):
            raise UpdateError('checksum_error')
        try:
            digest, count = hashlib.sha256(), 0
            with path.open('rb') as source:
                for block in iter(lambda: source.read(256 * 1024), b''):
                    count += len(block)
                    if count > info.size:
                        raise UpdateError('checksum_error')
                    digest.update(block)
            if count != info.size or digest.hexdigest() != downloaded.sha256:
                raise UpdateError('checksum_error')
        except OSError:
            raise UpdateError('checksum_error') from None
        return downloaded


def installer_command(downloaded, executable=None):
    executable = Path(executable or sys.executable).resolve()
    if downloaded.info.kind != 'windows-setup' or not windows_installed(executable):
        raise UpdateError('installation_changed')
    # Keep the wizard visible; never force-terminate an application or reboot Windows.
    return [str(downloaded.path), '/NORESTART', '/NOFORCECLOSEAPPLICATIONS',
            '/NORESTARTAPPLICATIONS', '/DIR=' + str(executable.parent)]


def launch_installer(downloaded):
    import ctypes
    import subprocess
    command = installer_command(downloaded)
    # PyInstaller's DLL search directory is inherited by child processes.
    # The external installer must use its own/system libraries instead.
    kernel = ctypes.windll.kernel32
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.SetDllDirectoryW.restype = ctypes.c_int
    if not kernel.SetDllDirectoryW(None):
        raise OSError('Unable to restore system DLL search')
    try:
        return subprocess.Popen(command, cwd=str(downloaded.path.parent))
    finally:
        kernel.SetDllDirectoryW(getattr(sys, '_MEIPASS', None))
