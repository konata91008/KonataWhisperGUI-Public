import copy
import hashlib
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from core.release_updater import (API_URL, RELEASES_URL, ReleaseUpdater, UpdateError,
    GitHubRedirects, package_kind, windows_installed, installer_command, launch_installer)
from core.release_translations import STRINGS


def fixture(kind='windows-setup', version='4.15.0', body=b'verified fixture package'):
    suffix, label = {
        'windows-setup': ('windows-x64-setup.exe', 'windows-amd64'),
        'windows-portable': ('windows-x64-portable.zip', 'windows-amd64'),
        'macos-arm64': ('macos-arm64.dmg', 'darwin-arm64'),
        'macos-x86_64': ('macos-x86_64.dmg', 'darwin-x86_64'),
    }[kind]
    name = f'TJKSub-{version}-{suffix}'
    checksum = f'SHA256SUMS-{label}.txt'
    base = f'{RELEASES_URL}/download/v{version}/'
    digest = hashlib.sha256(body).hexdigest()
    manifest = (digest + '  ' + name + '\n').encode()
    assets = [dict(name=n, size=len(b), state='uploaded', browser_download_url=base+n,
                   digest='sha256:'+hashlib.sha256(b).hexdigest()) for n,b in ((name,body),(checksum,manifest))]
    release = dict(tag_name='v'+version, published_at='2026-11-17T06:00:00Z',
                   draft=False, prerelease=False, body='Update notes\n<not HTML>', assets=assets)
    responses = {API_URL: json.dumps(release).encode(), base+name: body, base+checksum: manifest}
    return release, responses


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.release, self.responses = fixture()
        self.requests = []
        def opener(url):
            self.requests.append(url)
            return io.BytesIO(self.responses[url])
        self.updater = ReleaseUpdater('windows-setup', '4.14.1', self.folder/'updates', opener)
        self.cancel = threading.Event()

    def tearDown(self):
        self.temp.cleanup()

    def test_numeric_versions_ignore_equal_older_and_reject_prereleases(self):
        for remote, current, available in [('4.15.0','4.14.1',True),('4.9.0','4.14.1',False),
                ('4.15.0','4.15.0',False),('4.100.0','4.99.9',True)]:
            self.updater.current = current
            payload = fixture(version=remote)[0]
            self.assertEqual(self.updater.parse_release(payload).available, available)
        for tag in ('v4.16.0-rc1','v4.16.0/evil','v4.16.0\n','4.16.0','v04.16.0'):
            payload = dict(self.release, tag_name=tag)
            with self.assertRaises(UpdateError): self.updater.parse_release(payload)
        for flag in ('prerelease', 'draft'):
            with self.assertRaises(UpdateError): self.updater.parse_release(dict(self.release, **{flag:True}))

    def test_selects_exact_platform_package_and_manifest(self):
        for kind in ('windows-setup','windows-portable','macos-arm64','macos-x86_64'):
            release, responses = fixture(kind)
            updater = ReleaseUpdater(kind, '4.14.1', self.folder, lambda url: io.BytesIO(responses[url]))
            info = updater.check()
            self.assertEqual(info.kind,kind)
            self.assertIn(info.url,responses)
            self.assertIn(info.checksum_url,responses)
            self.assertEqual(info.date,'2026-11-17')

    def test_rejects_missing_ambiguous_oversized_and_untrusted_assets(self):
        mutations = [lambda p:p['assets'].clear(), lambda p:p['assets'].append(p['assets'][0]),
            lambda p:p['assets'][0].update(size=0), lambda p:p['assets'][0].update(size=2**31),
            lambda p:p['assets'][0].update(browser_download_url='https://example.com/installer.exe'),
            lambda p:p['assets'][1].update(browser_download_url='http://github.com/fake'),
            lambda p:p['assets'][0].update(digest='sha1:123'), lambda p:p['assets'][0].update(state='new')]
        for mutate in mutations:
            payload = copy.deepcopy(self.release); mutate(payload)
            with self.assertRaises(UpdateError): self.updater.parse_release(payload)

    def test_invalid_or_oversized_json_fails_closed(self):
        for payload in (b'not json',b'[]',b'null',b'{}',b'x'*(2*1024*1024+1)):
            self.responses[API_URL]=payload
            with self.assertRaises(UpdateError): self.updater.check()

    def test_download_is_verified_and_does_not_touch_models_or_installation(self):
        models=self.folder/'models'; models.mkdir(); (models/'model.bin').write_bytes(b'keep')
        info=self.updater.check(); progress=[]
        downloaded=self.updater.download(info,self.cancel,lambda *args:progress.append(args))
        self.assertEqual(downloaded.path.read_bytes(),self.responses[info.url])
        self.assertEqual(self.updater.verify(downloaded),downloaded)
        self.assertEqual(progress[-1],(info.size,info.size))
        self.assertEqual((models/'model.bin').read_bytes(),b'keep')
        self.assertFalse(list(self.folder.rglob('*.part')))
        self.assertEqual(self.requests,[API_URL,info.checksum_url,info.url])

    def test_truncated_modified_and_oversized_downloads_are_deleted(self):
        info=self.updater.check()
        for body in (b'',b'tampered',b'x'*info.size,b'x'*(info.size+1)):
            self.responses[info.url]=body
            with self.assertRaises(UpdateError): self.updater.download(info,self.cancel,lambda *a:None)
            self.assertEqual(list(self.updater.folder.iterdir()),[])

    def test_missing_conflicting_and_duplicate_checksums_prevent_package_download(self):
        info=self.updater.check()
        original=self.responses[info.checksum_url]
        for manifest in (b'', original+original, b'0'*64+b'  '+info.name.encode()+b'\n', b'\xff'):
            self.responses[info.checksum_url]=manifest
            with self.assertRaises(UpdateError): self.updater.download(info,self.cancel,lambda *a:None)
            self.assertNotIn(info.url,self.requests)

    def test_manifest_verifies_releases_without_github_digest(self):
        payload=copy.deepcopy(self.release); payload['assets'][0].pop('digest')
        info=self.updater.parse_release(payload)
        self.assertTrue(self.updater.download(info,self.cancel,lambda *a:None).path.is_file())

    def test_cancel_before_and_during_download_removes_partial_file(self):
        info=self.updater.check(); self.cancel.set()
        with self.assertRaisesRegex(UpdateError,'cancelled'):
            self.updater.download(info,self.cancel,lambda *a:None)
        self.assertNotIn(info.checksum_url,self.requests)
        self.cancel.clear()
        with self.assertRaisesRegex(UpdateError,'cancelled'):
            self.updater.download(info,self.cancel,lambda *a:self.cancel.set())
        self.assertEqual(list(self.updater.folder.iterdir()),[])

    def test_failed_stream_removes_partial_download(self):
        info=self.updater.check(); realopen=self.updater.open
        class Broken(io.BytesIO):
            def read(self,*args): raise ConnectionError('disconnected')
        self.updater.open=lambda url:Broken() if url==info.url else realopen(url)
        with self.assertRaises(ConnectionError): self.updater.download(info,self.cancel,lambda *a:None)
        self.assertEqual(list(self.updater.folder.iterdir()),[])

    def test_reverify_catches_file_changes_removal_and_outside_paths(self):
        info=self.updater.check(); result=self.updater.download(info,self.cancel,lambda *a:None)
        outside=self.folder/info.name; outside.write_bytes(result.path.read_bytes())
        with self.assertRaises(UpdateError): self.updater.verify(replace(result,path=outside))
        result.path.write_bytes(b'x'*info.size)
        with self.assertRaises(UpdateError): self.updater.verify(result)
        result.path.unlink()
        with self.assertRaises(UpdateError): self.updater.verify(result)

    def test_redirects_require_https_and_official_hosts(self):
        handler=GitHubRedirects(); request=__import__('urllib.request',fromlist=['Request']).Request(API_URL)
        for url in ('http://github.com/file','https://evil.example/file','https://github.com.evil/file',
                    'https://name:secret@github.com/file','https://github.com:444/file','file:///tmp/x'):
            with self.assertRaises(UpdateError): handler.redirect_request(request,None,302,'',{},url)
        redirected=handler.redirect_request(request,None,302,'',{},'https://release-assets.githubusercontent.com/file?token=test')
        self.assertEqual(redirected.host,'release-assets.githubusercontent.com')

    def test_registry_matches_only_current_installation(self):
        executable=self.folder/'installed'/'TJKSub.exe'
        registry=Mock(KEY_READ=1,KEY_WOW64_64KEY=2)
        registry.OpenKey.return_value=Mock(__enter__=Mock(return_value='key'),__exit__=Mock(return_value=False))
        registry.QueryValueEx.return_value=(str(executable.parent),1)
        with patch.dict(sys.modules,{'winreg':registry}):
            self.assertTrue(windows_installed(executable))
            self.assertFalse(windows_installed(self.folder/'portable'/'TJKSub.exe'))
            self.assertFalse(windows_installed(self.folder/'installed'/'other.exe'))
            registry.QueryValueEx.side_effect=OSError()
            self.assertFalse(windows_installed(executable))

    def test_platform_detection_preserves_portable_and_handles_rosetta(self):
        with patch('core.release_updater.sys.platform','win32'), patch('core.release_updater.platform.machine',return_value='AMD64'):
            with patch('core.release_updater.windows_installed',return_value=False): self.assertEqual(package_kind(),'windows-portable')
            with patch('core.release_updater.windows_installed',return_value=True): self.assertEqual(package_kind(),'windows-setup')
        with patch('core.release_updater.sys.platform','darwin'), patch('core.release_updater.platform.machine',return_value='x86_64'), \
                patch('subprocess.run',return_value=SimpleNamespace(stdout=b'1\n')):
            self.assertEqual(package_kind(),'macos-arm64')

    def test_installer_targets_exact_installation_without_shell_or_force_exit(self):
        info=self.updater.check(); result=self.updater.download(info,self.cancel,lambda *a:None)
        exe=self.folder/'應用 程式'/'TJKSub.exe'
        with patch('core.release_updater.windows_installed',return_value=True):
            command=installer_command(result,exe)
        self.assertIn('/DIR='+str(exe.resolve().parent),command)
        self.assertNotIn('/VERYSILENT',command)
        self.assertNotIn('/FORCECLOSEAPPLICATIONS',command)
        with patch('core.release_updater.windows_installed',return_value=False):
            with self.assertRaises(UpdateError): installer_command(result,exe)

    def test_launch_restores_dll_search_even_when_installer_cannot_start(self):
        import ctypes
        kernel=Mock(); kernel.SetDllDirectoryW.return_value=1
        with patch.object(ctypes,'windll',SimpleNamespace(kernel32=kernel),create=True), \
                patch('core.release_updater.installer_command',return_value=['installer']), \
                patch('subprocess.Popen',side_effect=OSError('cannot start')), \
                patch.object(sys,'_MEIPASS','bundle',create=True):
            with self.assertRaises(OSError): launch_installer(SimpleNamespace(path=Path('updates/setup.exe')))
        self.assertEqual(kernel.SetDllDirectoryW.call_args_list[0].args,(None,))
        self.assertEqual(kernel.SetDllDirectoryW.call_args_list[-1].args,('bundle',))

    def test_all_locales_have_complete_matching_placeholders(self):
        from string import Formatter
        for language,strings in STRINGS.items():
            self.assertEqual(set(strings),set(STRINGS['en']))
            for key,value in strings.items():
                fields=lambda s:{field for _,field,_,_ in Formatter().parse(s) if field}
                self.assertEqual(fields(value),fields(STRINGS['en'][key]),(language,key))


from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from gui.main_window import WhisperGUI
from gui.release_update_dialog import ReleaseUpdateDialog


class ReleaseDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.folder=Path(self.temp.name)
        self.settings=patch('gui.main_window.QSettings',side_effect=lambda *a:QSettings(str(self.folder/'settings.ini'),QSettings.IniFormat))
        self.runtime=patch('gui.main_window.load_runtime',return_value=None)
        self.data=patch.dict(os.environ,{'TJKSUB_DATA_DIR':str(self.folder/'data')})
        for context in (self.settings,self.runtime,self.data): context.start()
        self.window=WhisperGUI()
        self.release,self.responses=fixture()
        self.updater=ReleaseUpdater('windows-setup','4.14.1',self.folder/'updates',lambda url:io.BytesIO(self.responses[url]))
        self.dialog=ReleaseUpdateDialog(self.window,self.updater)
        self.window.update_dialog=self.dialog
        self.dialog.show()

    def tearDown(self):
        self.wait(); self.dialog.close(); self.window.close()
        self.dialog.deleteLater(); self.window.deleteLater(); self.app.processEvents()
        for context in (self.data,self.runtime,self.settings): context.stop()
        self.temp.cleanup()

    def wait(self):
        deadline=time.monotonic()+10
        while self.dialog.is_busy() and time.monotonic()<deadline: QTest.qWait(10)
        self.assertFalse(self.dialog.is_busy())

    def ready(self):
        self.dialog.check(); self.wait(); self.dialog.download(); self.wait()
        self.assertIsNotNone(self.dialog.downloaded)

    def test_check_and_download_are_separate_and_never_auto_launch(self):
        with patch('gui.release_update_dialog.launch_installer') as launch:
            self.dialog.check(); self.wait()
            self.assertEqual(self.dialog.details.toPlainText(),self.release['body'])
            self.assertTrue(self.dialog.download_button.isEnabled())
            self.assertIsNone(self.dialog.downloaded)
            self.dialog.download(); self.wait()
            self.assertTrue(self.dialog.apply_button.isVisible())
            self.assertEqual(self.dialog.status.text(),STRINGS['zh_TW']['verified'])
            launch.assert_not_called()

    def test_current_version_disables_download_and_clears_previous_result(self):
        self.ready(); self.updater.current='4.15.0'
        self.dialog.check(); self.wait()
        self.assertFalse(self.dialog.download_button.isEnabled())
        self.assertIsNone(self.dialog.downloaded)
        self.assertEqual(self.dialog.status.text(),STRINGS['zh_TW']['latest'])

    def test_rate_limit_error_keeps_release_page_available(self):
        self.updater.open=Mock(side_effect=UpdateError('rate_limit'))
        self.dialog.check(); self.wait()
        self.assertEqual(self.dialog.status.text(),STRINGS['zh_TW']['rate_limit'])
        self.assertTrue(self.dialog.page_button.isEnabled())
        self.assertFalse(self.dialog.download_button.isEnabled())

    def test_cancel_and_close_during_download_do_not_destroy_running_thread(self):
        self.dialog.check(); self.wait()
        def download(info,event,progress):
            event.wait(5)
            raise UpdateError('cancelled')
        self.updater.download=download
        self.dialog.download()
        self.assertFalse(self.dialog.close_button.isEnabled())
        self.dialog.reject(); self.assertTrue(self.dialog.isVisible())
        self.dialog.cancel(); self.wait()
        self.assertIsNone(self.dialog.downloaded)
        self.assertTrue(self.dialog.close_button.isEnabled())
        self.assertEqual(self.dialog.status.text(),STRINGS['zh_TW']['cancelled'])

    def test_busy_and_declined_confirmation_never_launch_or_close(self):
        self.ready()
        with patch('gui.release_update_dialog.CustomMessageBox') as message, \
                patch('gui.release_update_dialog.launch_installer') as launch:
            self.window.is_downloading=True
            self.dialog.confirm_apply(); message.assert_not_called()
            self.window.is_downloading=False
            message.return_value.exec_.return_value=0; message.return_value.Accepted=1
            self.dialog.confirm_apply(); self.wait(); launch.assert_not_called()
            self.assertIn(STRINGS['zh_TW']['confirm'],message.call_args.args[3])

    def test_changed_download_cannot_launch_after_confirmation(self):
        self.ready(); self.dialog.downloaded.path.write_bytes(b'changed')
        with patch('gui.release_update_dialog.CustomMessageBox') as message, \
                patch('gui.release_update_dialog.launch_installer') as launch:
            message.return_value.exec_.return_value=1; message.return_value.Accepted=1
            self.dialog.confirm_apply(); self.wait(); launch.assert_not_called()
        self.assertIsNone(self.dialog.downloaded)
        self.assertEqual(self.dialog.status.text(),STRINGS['zh_TW']['checksum_error'])

    def test_installer_launch_failure_keeps_application_open(self):
        self.ready()
        with patch('gui.release_update_dialog.launch_installer',side_effect=OSError('blocked')), \
                patch.object(self.window,'close') as close:
            self.dialog.launch(self.dialog.downloaded); close.assert_not_called()
        self.assertEqual(self.dialog.status.text(),STRINGS['zh_TW']['launch_failed'])

    def test_successful_handoff_saves_settings_and_closes_after_launch(self):
        self.ready()
        with patch('gui.release_update_dialog.launch_installer') as launch, \
                patch.object(self.window,'save_settings') as save, patch.object(self.window,'close') as close, \
                patch('gui.release_update_dialog.QApplication') as app:
            self.dialog.launch(self.dialog.downloaded)
            save.assert_called_once(); launch.assert_called_once(); close.assert_called_once(); app.instance().quit.assert_called_once()

    def test_mac_and_portable_open_dmg_or_folder_without_running_installer(self):
        self.ready()
        with patch('gui.release_update_dialog.launch_installer') as launch, \
                patch('gui.release_update_dialog.QDesktopServices.openUrl',return_value=True) as open_url, \
                patch.object(self.window,'close'), patch('gui.release_update_dialog.QApplication'):
            for kind in ('macos-arm64','windows-portable'):
                downloaded=replace(self.dialog.downloaded,info=replace(self.dialog.downloaded.info,kind=kind))
                self.dialog.launch(downloaded)
                expected=downloaded.path.parent if kind=='windows-portable' else downloaded.path
                self.assertEqual(Path(open_url.call_args.args[0].toLocalFile()),expected)
            launch.assert_not_called()

    def test_packaged_menu_uses_release_dialog_and_source_keeps_git(self):
        self.dialog.close()
        with patch('gui.main_window.is_packaged',return_value=True), \
                patch('gui.main_window.ReleaseUpdateDialog') as packaged, patch('gui.main_window.UpdateDialog') as source:
            self.window.open_update_dialog(); packaged.assert_called_once(); source.assert_not_called()
            packaged.return_value.check.assert_called_once()
        self.window.update_dialog=None
        with patch('gui.main_window.is_packaged',return_value=False), \
                patch('gui.main_window.UpdateDialog') as source:
            self.window.open_update_dialog(); source.assert_called_once()
        self.window.update_dialog=self.dialog


if __name__=='__main__': unittest.main()
