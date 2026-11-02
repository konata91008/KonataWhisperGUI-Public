import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from core import cuda_download as cd


class CUDADownloadTests(unittest.TestCase):
    def archive(self, entries):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as z:
            for name, body in entries: z.writestr(name, body)
        output.seek(0)
        return output

    def test_components_keep_licenses_and_only_required_vs_extensions(self):
        data = self.archive([('package/LICENSE', b'terms'),
            ('package/visual_studio_integration/MSBuildExtensions/CUDA 12.9.props', b'props'),
            ('package/visual_studio_integration/CudaProjectVsWizards/template', b'not required')])
        with tempfile.TemporaryDirectory() as temp:
            cd.extract_component(data, temp, 'visual_studio_integration')
            root = Path(temp)
            self.assertEqual((root / 'extras/visual_studio_integration/MSBuildExtensions/CUDA 12.9.props').read_bytes(), b'props')
            self.assertEqual((root / 'licenses/visual_studio_integration/LICENSE').read_bytes(), b'terms')
            self.assertFalse((root / 'visual_studio_integration').exists())

    def test_unsafe_archive_paths_are_rejected(self):
        for name in ('package/../../escape', '/absolute', 'C:/escape', 'package\\..\\escape'):
            with tempfile.TemporaryDirectory() as temp, self.subTest(name=name), self.assertRaises(RuntimeError):
                cd.extract_component(self.archive([(name, b'x')]), temp, 'nvcc')
        item = zipfile.ZipInfo('package/link'); item.external_attr = (stat.S_IFLNK | 0o777) << 16
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(RuntimeError):
            cd.extract_component(self.archive([(item, b'/outside')]), temp, 'nvcc')

    def test_download_checks_length_and_sha_before_extracting(self):
        body = b'correct archive'
        package = dict(component='nvcc', path='sample.zip', size=len(body), sha256=hashlib.sha256(body).hexdigest())
        for data, succeeds in [(body, True), (b'wrong archive!!', False), (body[:-2], False), (body + b'extra', False)]:
            with tempfile.TemporaryDirectory() as temp, patch.object(cd.urllib.request, 'urlopen', return_value=io.BytesIO(data)):
                output = Path(temp) / 'download.zip'
                if succeeds:
                    cd.download_package(package, output, lambda _: None)
                    self.assertEqual(output.read_bytes(), body)
                else:
                    with self.assertRaises(RuntimeError): cd.download_package(package, output, lambda _: None)

    def test_failed_install_does_not_publish_or_change_previous_toolkit(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(cd, 'toolchain_root', return_value=Path(temp)), \
             patch.object(cd, 'download_package', side_effect=RuntimeError('connection interrupted')):
            previous = Path(temp) / 'v12.9-old'; previous.mkdir(); (previous / 'marker').write_text('keep')
            with self.assertRaisesRegex(RuntimeError, 'interrupted'): cd.install_cuda('12.9', lambda _: None)
            self.assertEqual(list(Path(temp).iterdir()), [previous])
            self.assertEqual((previous / 'marker').read_text(), 'keep')

    def test_success_publishes_only_after_all_components_are_extracted(self):
        def download(package, target, log):
            self.assertFalse(any(p.name.startswith('v') for p in Path(temp).iterdir()))
            Path(target).write_bytes(self.archive([('package/include/' + package['component'], b'header')]).getvalue())
        with tempfile.TemporaryDirectory() as temp, patch.object(cd, 'toolchain_root', return_value=Path(temp)), \
             patch.object(cd, 'download_package', side_effect=download):
            result = cd.install_cuda('12.9', lambda _: None)
            plan = json.loads((result / 'tjksub-cuda.json').read_text())
            for item in plan['packages']:
                if item['component'] != 'visual_studio_integration':
                    self.assertTrue((result / 'include' / item['component']).exists())
            self.assertEqual([result], list(Path(temp).iterdir()))


if __name__ == '__main__': unittest.main()
