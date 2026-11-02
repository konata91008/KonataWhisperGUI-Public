import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from core import gpu_setup as gs


class GPUSetupTests(unittest.TestCase):
    def windows(self, cc='86'):
        gpu = gs.GPU('NVIDIA test device', 'cuda', 'GPU-test', cc)
        scan = gs.Scan('Windows', 'amd64', [gpu], {
            'cmake': 'cmake', 'vs': 'C:/VS', 'windows_sdk': True, 'ffmpeg': 'ffmpeg',
            'winget': 'winget', 'cuda': [{'root': 'C:/CUDA', 'targets': [cc], 'missing': []}]})
        return scan, gpu

    def test_driver_inventory_does_not_guess_architecture(self):
        result = gs.parse_nvidia('0, GPU-a, "NVIDIA, test", 8.6, 580.0\r\n1, GPU-b, RTX, 12.0, 580.0\n2, GPU-c, Old, 3.5, 580.0\n3, GPU-d, Unknown, N/A, 580.0')
        self.assertEqual([g.cc for g in result], ['86', '120', '35'])
        self.assertEqual(result[0].name, 'NVIDIA, test')
        self.assertTrue(result[2].blocked)

    def test_vulkan_inventory_excludes_software_devices(self):
        text = ''.join(f'GPU{i}:\n deviceType = PHYSICAL_DEVICE_TYPE_{kind}\n deviceName = {kind}\n apiVersion = 1.3\n' for i, kind in enumerate(['DISCRETE_GPU', 'CPU', 'INTEGRATED_GPU']))
        self.assertEqual([g.identity for g in gs.parse_vulkan(text)], ['0', '2'])

    def test_registry_expansion_uses_new_values_and_handles_cycles(self):
        variables = {'CUDA_PATH': '%ProgramFiles%/CUDA', 'PROGRAMFILES': 'C:/Program Files', 'CYCLE': '%cycle%'}
        self.assertEqual(gs.expand_windows_vars('%cuda_path%/bin', variables), 'C:/Program Files/CUDA/bin')
        self.assertEqual(gs.expand_windows_vars('%cycle%', variables), '%cycle%')
        self.assertEqual(gs.expand_windows_vars('%unknown%', variables), '%unknown%')
        self.assertGreater(gs.version_key('v13.4'), gs.version_key('v9.2'))

    def test_cuda_13_runtime_dll_directory_is_on_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'bin/x64').mkdir(parents=True)
            self.assertEqual(gs.cuda_binary_dirs(root), [str(root / 'bin/x64'), str(root / 'bin')])
        self.assertEqual(gs.cuda_binary_dirs('toolkit'), [str(Path('toolkit/bin'))])

    def test_partial_toolkit_is_not_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'bin').mkdir(); (root / 'bin/nvcc.exe').touch()
            with patch.object(gs, 'capture', return_value='sm_61 sm_86 sm_120 sm_120a'):
                kit = gs.inspect_cuda(root)
            self.assertIn('lib/x64/cublas.lib', kit['missing'])
            self.assertTrue(any('integration' in x for x in kit['missing']))
            scan, gpu = self.windows(); scan.tools['cuda'] = [kit]
            self.assertIsNone(gs.cuda_toolkit(scan, gpu))

    def test_selects_compatible_complete_toolkit_not_newest_only(self):
        scan, gpu = self.windows('61')
        scan.tools['cuda'] = [dict(root='13', targets=['86'], missing=[]),
                              dict(root='broken12', targets=['61'], missing=['cublas']),
                              dict(root='12', targets=['61'], missing=[])]
        self.assertEqual(gs.cuda_toolkit(scan, gpu)['root'], '12')
        self.assertEqual(gs.cuda_package_version(gpu), '12.9')
        self.assertEqual(gs.cuda_package_version(gs.GPU('new', 'cuda', 'GPU-x', '121')), '13.4')

    def test_invalid_selection_stops_before_install(self):
        for system, machine, gpu in [('Windows', 'arm64', gs.GPU('x', 'cuda', 'GPU-x', '86')),
             ('Windows', 'amd64', gs.GPU('x', 'cuda', '', '86')),
             ('Windows', 'amd64', gs.GPU('x', 'cuda', 'GPU-x', '35')),
             ('Darwin', 'arm64', gs.GPU('x', 'vulkan'))]:
            with self.subTest(system=system, gpu=gpu), self.assertRaises(gs.SetupError):
                gs.validate_selection(gs.Scan(system, machine), gpu)

    def test_cuda_config_uses_selected_device_and_unicode_manifest(self):
        scan, gpu = self.windows('120')
        args = gs.cmake_command(Path('中文 source'), Path('build'), scan, gpu)
        self.assertIn('-DCMAKE_CUDA_ARCHITECTURES=120', args)
        self.assertIn('cuda=C:/CUDA', args)
        self.assertIn('-DGGML_CUDA=ON', args)
        self.assertIn('-DGGML_VULKAN=OFF', args)
        self.assertTrue(any('/MANIFESTINPUT:' in a for a in args))
        self.assertNotIn('--allow-unsupported-compiler', ' '.join(args))

    def test_install_order_and_no_display_driver_changes(self):
        scan, gpu = self.windows(); scan.tools.update(vs='', cuda=[])
        calls = []
        with patch.object(gs, 'capture', return_value='cmake version 3.31.10'), \
             patch.object(gs, 'install_cuda', side_effect=lambda version, log: calls.append(['CUDA', version])):
            gs.install_tools(scan, gpu, lambda _: None, runner=lambda args, *a, **kw: calls.append(args))
        self.assertIn('Microsoft.VisualStudio.2022.BuildTools', calls[0])
        self.assertEqual(calls[1], ['CUDA', '12.9'])
        self.assertNotIn('Display.Driver', str(calls))

    def test_cmake_never_installs_into_global_python(self):
        scan, gpu = self.windows(); scan.tools['cmake'] = None
        with patch.object(sys, 'prefix', sys.base_prefix), self.assertRaisesRegex(gs.SetupError, 'venv'):
            gs.install_tools(scan, gpu, lambda _: None)

    def test_compile_failure_preserves_previous_engine(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'whisper.cpp/ggml').mkdir(parents=True)
            (root / 'whisper.cpp/CMakeLists.txt').touch(); (root / 'whisper.cpp/ggml/CMakeLists.txt').touch()
            manifest = gs.runtime_file(root); manifest.parent.mkdir(); manifest.write_text('previous runtime')
            scan, gpu = self.windows()
            for failure_step in (0, 1, 2):
                calls = []
                def runner(args, *a, **kw):
                    step = len(calls); calls.append(args)
                    if step == failure_step: raise gs.SetupError('simulated failure')
                    if step == 0:
                        exe = Path(args[args.index('-B') + 1]) / 'bin/Release/whisper-cli.exe'
                        exe.parent.mkdir(parents=True); exe.touch()
                with patch.object(gs, 'missing_tools', return_value=[]), self.assertRaises(gs.SetupError):
                    gs.build_gpu(root, scan, gpu, lambda _: None, runner=runner)
                self.assertEqual(len(calls), failure_step + 1)
                self.assertEqual(manifest.read_text(), 'previous runtime')

    def test_windows_build_promotes_executable_from_short_temporary_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / ('long-project-' * 4)
            (root / 'whisper.cpp/ggml').mkdir(parents=True)
            (root / 'whisper.cpp/CMakeLists.txt').touch(); (root / 'whisper.cpp/ggml/CMakeLists.txt').touch()
            scan, gpu = self.windows(); calls = []
            def runner(args, *a, **kw):
                calls.append(args)
                if '-B' in args:
                    build = Path(args[args.index('-B') + 1])
                    self.assertNotIn(str(root), str(build))
                    exe = build / 'bin/Release/whisper-cli.exe'
                    exe.parent.mkdir(parents=True); exe.write_bytes(b'compiled executable')
                    (build / 'CMakeConfigureLog.yaml').write_text('diagnostics')
                elif '--help' in args:
                    self.assertTrue(Path(args[0]).is_relative_to(root.resolve()))
            with patch.object(gs, 'missing_tools', return_value=[]):
                result = gs.build_gpu(root, scan, gpu, lambda _: None, runner=runner)
            exe = root / result['executable']
            self.assertEqual(exe.read_bytes(), b'compiled executable')
            self.assertEqual((exe.parent / 'configure-0.yaml').read_text(), 'diagnostics')
            working = Path(calls[0][calls[0].index('-B') + 1])
            self.assertFalse(working.exists())
            with patch.object(gs, 'host_key', return_value=('Windows', 'amd64')):
                self.assertEqual(gs.load_runtime(root)['path'], str(exe.resolve()))

    def test_install_rescan_rejects_changed_device(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'whisper.cpp/ggml').mkdir(parents=True)
            (root / 'whisper.cpp/CMakeLists.txt').touch(); (root / 'whisper.cpp/ggml/CMakeLists.txt').touch()
            scan, gpu = self.windows()
            with patch.object(gs, 'install_tools'), self.assertRaisesRegex(gs.SetupError, '顯卡清單有變'):
                gs.build_gpu(root, scan, gpu, lambda _: None, install=True, scanner=lambda: gs.Scan('Windows', 'amd64'))
            self.assertFalse(gs.runtime_file(root).exists())

    def test_logged_process_failure_and_timeout(self):
        with self.assertRaises(gs.SetupError):
            gs.run_logged([sys.executable, '-c', 'raise SystemExit(7)'], lambda _: None)
        started = time.monotonic()
        with self.assertRaisesRegex(gs.SetupError, '逾時'):
            gs.run_logged([sys.executable, '-c', 'import time; time.sleep(30)'], lambda _: None, timeout=.1)
        self.assertLess(time.monotonic() - started, 10)


if __name__ == '__main__': unittest.main()
