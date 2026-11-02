import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'WhisperGUI'))
from PyQt5.QtCore import QSettings
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from core.gpu_setup import GPU, Scan, SetupError
from gui.main_window import WhisperGUI
from gui.gpu_dialog import GPUSetupDialog


class GPUDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.settings = patch('gui.main_window.QSettings', side_effect=lambda *args: QSettings(str(Path(self.folder.name) / 'test.ini'), QSettings.IniFormat))
        self.settings.start()
        self.owner = WhisperGUI()
        self.dialog = GPUSetupDialog(self.owner, auto_scan=False)
        self.scan = Scan('Windows', 'amd64', [GPU('NVIDIA test', 'cuda', 'GPU-test', '86')])

    def tearDown(self):
        self.dialog.close(); self.owner.close(); self.settings.stop(); self.folder.cleanup()

    def finish(self):
        deadline = time.monotonic() + 5
        while self.dialog.worker is not None and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertIsNone(self.dialog.worker)

    def test_install_consent_and_selection_changes(self):
        with patch('gui.gpu_dialog.missing_tools', return_value=['CUDA Toolkit 12.9']):
            self.dialog.scanned(self.scan)
            self.assertFalse(self.dialog.buildButton.isEnabled())
            self.dialog.consent.setChecked(True)
            self.assertTrue(self.dialog.buildButton.isEnabled())
            self.dialog.selection_changed()
            self.assertFalse(self.dialog.buildButton.isEnabled())

    def test_scan_error_restores_controls(self):
        with patch('gui.gpu_dialog.scan_host', side_effect=SetupError('driver read failed')):
            self.dialog.start_scan(); self.finish()
        self.assertIn('driver read failed', self.dialog.status.text())
        self.assertTrue(self.dialog.rescanButton.isEnabled())
        self.assertFalse(self.dialog.buildButton.isEnabled())

    def test_build_failure_keeps_window_alive_and_allows_retry(self):
        gate = threading.Event()
        def fail(*args, **kwargs):
            gate.wait(3)
            raise SetupError('compiler error')
        with patch('gui.gpu_dialog.missing_tools', return_value=[]), patch('gui.gpu_dialog.build_gpu', side_effect=fail):
            self.dialog.scanned(self.scan); self.dialog.show(); self.dialog.start_build()
            self.assertFalse(self.dialog.closeButton.isEnabled())
            self.dialog.close(); self.assertTrue(self.dialog.isVisible())
            gate.set(); self.finish()
            self.assertIn('compiler error', self.dialog.status.text())
            self.assertTrue(self.dialog.buildButton.isEnabled())
            self.assertTrue(self.dialog.closeButton.isEnabled())


if __name__ == '__main__': unittest.main()
