import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from core import paths
from core.tasks import download_task
from core.gpu_setup import gpu_log_state


class DistributionTests(unittest.TestCase):
    def test_backend_confirmation_matches_actual_engine_device_names(self):
        for backend, names in [('metal', ['Metal', 'MTL0']), ('vulkan', ['Vulkan0']), ('cuda', ['CUDA0'])]:
            for name in names:
                line = 'whisper_backend_init_gpu: using ' + name + ' backend'
                self.assertEqual(gpu_log_state(line, backend), 'selected')
        self.assertIsNone(gpu_log_state('whisper_backend_init_gpu: using CPU backend', 'metal'))
        self.assertIsNone(gpu_log_state('whisper_backend_init_gpu: using Vulkan0 backend', 'metal'))
        self.assertIsNone(gpu_log_state('ggml_metal_init: found device: Apple M4', 'metal'))
        self.assertEqual(gpu_log_state('whisper_backend_init_gpu: no GPU found', 'metal'), 'failed')

    def test_packaged_data_is_outside_readonly_resources(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, 'frozen', True, create=True), \
                patch.object(sys, '_MEIPASS', folder, create=True), \
                patch.dict(os.environ, {'USERPROFILE': folder, 'HOME': folder}, clear=True):
            self.assertEqual(paths.resource_root(), Path(folder))
            self.assertNotEqual(paths.data_root(), paths.resource_root())
            with patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': folder}):
                with patch.object(Path, 'home', side_effect=RuntimeError('No home directory')):
                    self.assertEqual(paths.data_root(), Path(folder) / 'TJKSub')

    def test_explicit_data_override_and_restart_do_not_require_python(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'TJKSUB_DATA_DIR': folder}), \
                patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(paths.data_root(), Path(folder).resolve())
            executable, args, cwd = paths.restart_command()
            self.assertEqual(executable, sys.executable)
            self.assertEqual(args, ['--restarted'])
            self.assertNotIn('main.py', ' '.join(args))

    def test_bundled_runtime_rejects_wrong_machine_and_missing_files(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, 'frozen', True, create=True), \
                patch.object(sys, '_MEIPASS', folder, create=True), \
                patch('core.paths.platform.system', return_value='Darwin'), \
                patch('core.paths.platform.machine', return_value='arm64'), patch.object(sys, 'platform', 'darwin'):
            native = Path(folder) / 'native'; native.mkdir()
            manifest = native / 'runtime.json'
            manifest.write_text(json.dumps({'system': 'Darwin', 'machine': 'arm64', 'backend': 'metal'}))
            self.assertIsNone(paths.bundled_runtime())
            for name in ('whisper-cli', 'ffmpeg'): (native / name).touch()
            self.assertEqual(paths.bundled_runtime()['backend'], 'metal')
            manifest.write_text(json.dumps({'system': 'Darwin', 'machine': 'x86_64', 'backend': 'metal'}))
            self.assertIsNone(paths.bundled_runtime())


class Signal:
    def __init__(self): self.calls = []
    def emit(self, *args): self.calls.append(args)


class DownloadTests(unittest.TestCase):
    def download(self, folder, response, cancelled=False):
        worker = SimpleNamespace(_is_cancelled=cancelled, progress_update=Signal(), download_finished=Signal())
        owner = SimpleNamespace(translations={
            'downloading_progress': '{downloaded}/{total}',
            'downloading_progress_no_total': '{downloaded}', 'download_complete': 'done'})
        with patch('core.tasks.urllib.request.urlopen', return_value=response):
            download_task(worker, owner, 'tiny', folder)
        return worker

    def test_atomic_model_download_replaces_only_after_success(self):
        with tempfile.TemporaryDirectory() as folder:
            response = io.BytesIO(b'new model'); response.headers = {'Content-Length': '9'}
            worker = self.download(folder, response)
            self.assertEqual(worker.download_finished.calls, [(True,)])
            self.assertEqual((Path(folder) / 'models/ggml-tiny.bin').read_bytes(), b'new model')
            self.assertFalse((Path(folder) / 'models/ggml-tiny.bin.part').exists())

    def test_cancelled_and_truncated_downloads_preserve_existing_model(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / 'models/ggml-tiny.bin'; model.parent.mkdir(); model.write_bytes(b'original')
            for cancelled in (True, False):
                response = io.BytesIO(b'partial'); response.headers = {'Content-Length': '100'}
                worker = self.download(folder, response, cancelled)
                self.assertEqual(worker.download_finished.calls, [(False,)])
                self.assertEqual(model.read_bytes(), b'original')
                self.assertFalse(model.with_suffix('.bin.part').exists())

    def test_network_failure_never_deletes_a_previous_model(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / 'models/ggml-tiny.bin'; model.parent.mkdir(); model.write_bytes(b'original')
            response = io.BytesIO(b''); response.headers = {}
            worker = self.download(folder, response)
            self.assertEqual(worker.download_finished.calls, [(False,)])
            self.assertEqual(model.read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
