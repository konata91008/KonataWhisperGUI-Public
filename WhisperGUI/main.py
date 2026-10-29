import sys
import hashlib
import tempfile
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QLockFile, QTimer
from gui.main_window import WhisperGUI
from core.version import PROJECT_ROOT
from core.update_translations import update_strings

#
# 程式的主要進入點
# 它的職責很簡單：建立應用程式實例、建立主視窗，然後執行。
#
if __name__ == "__main__":
    # 建立 QApplication 實例
    app = QApplication(sys.argv)

    # One running instance per installation. A restarted child waits for the old
    # process to release the lock before it opens files from the new version.
    identity = hashlib.sha256(str(PROJECT_ROOT.resolve()).encode()).hexdigest()[:24]
    instance_lock = QLockFile(str(Path(tempfile.gettempdir()) / f'tjksub-{identity}.lock'))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(5000 if '--restarted' in sys.argv else 0):
        QMessageBox.information(None, 'TJKSub', update_strings('zh_TW')['already_running'])
        sys.exit(1)
    
    # 建立主視窗 WhisperGUI 的實例
    gui = WhisperGUI()
    
    # 顯示視窗
    gui.show()
    if '--check-updates' in sys.argv:
        QTimer.singleShot(0, gui.open_update_dialog)
    elif '--setup' in sys.argv or not gui.gpu_runtime:
        QTimer.singleShot(0, gui.open_gpu_setup)
    
    # 進入應用程式的主事件循環
    sys.exit(app.exec_())

