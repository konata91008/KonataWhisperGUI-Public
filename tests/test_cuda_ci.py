import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('cuda_ci', Path(__file__).resolve().parents[1] / 'tools/cuda_ci.py')
ci = importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)

class CUDACIProbeTests(unittest.TestCase):
    def test_parses_real_dumpbin_import_and_delay_load_sections(self):
        text = "Image has the following dependencies:\n    cublas64_13.dll\n    KERNEL32.dll\nDelay load dependencies:\n    nvcuda.dll\n  1000 .data\n"
        self.assertEqual(ci.imported_dlls(text), ['cublas64_13.dll', 'KERNEL32.dll', 'nvcuda.dll'])

    def test_only_missing_driver_can_be_classified_as_hardware_blocked(self):
        result = SimpleNamespace(returncode=0xC0000135, stdout='', stderr='')
        with patch.object(ci.subprocess, 'run', return_value=result):
            for missing in (['nvcuda.dll'], ['cublas64_13.dll', 'nvcuda.dll'], []):
                with self.subTest(missing=missing), patch.object(ci, 'check_dependencies', return_value={'missing':missing}):
                    expected = ci.DriverUnavailable if missing == ['nvcuda.dll'] else RuntimeError
                    with self.assertRaises(expected) as caught:
                        ci.probe_cuda_launch(['engine.exe','--help'], lambda _:None, [], 'VS', env={})
                    if expected is RuntimeError: self.assertNotIsInstance(caught.exception, ci.DriverUnavailable)

    def test_other_launch_errors_are_never_ignored(self):
        with patch.object(ci.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='bad')):
            with self.assertRaises(RuntimeError), patch.object(ci, 'check_dependencies') as inspect:
                ci.probe_cuda_launch(['engine.exe','--help'], lambda _:None, [], 'VS', env={})
            inspect.assert_not_called()
