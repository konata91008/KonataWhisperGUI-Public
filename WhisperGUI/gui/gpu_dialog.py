"""OS-specific, user-initiated GPU toolchain setup."""
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QPlainTextEdit, QProgressBar, QCheckBox
from .widgets import CustomDialog
from .ai_dialog import theme, label
from core.gpu_setup import scan_host, build_gpu, missing_tools, validate_selection, SetupError
from core.version import PROJECT_ROOT


class SetupWorker(QThread):
    result = pyqtSignal(object)
    failure = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            self.result.emit(self.operation(self.log.emit))
        except Exception as exc:
            self.failure.emit(str(exc))


class GPUSetupDialog(CustomDialog):
    def __init__(self, owner, auto_scan=True):
        super().__init__(owner)
        self.owner, self.scan, self.worker = owner, None, None
        self.setWindowTitle('顯卡與引擎設定')
        self.setMinimumSize(720, 650)
        theme(self, owner)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(12)
        title = QLabel('顯卡與引擎設定', objectName='TitleLabel')
        layout.addWidget(title)
        layout.addWidget(label('首次使用先偵測顯卡，再依實際架構編譯。macOS 與 Windows 會顯示各自適用的選項。'))
        self.systemLabel = label('正在準備偵測…')
        layout.addWidget(self.systemLabel)
        self.gpuCombo = QComboBox()
        self.gpuCombo.currentIndexChanged.connect(self.selection_changed)
        layout.addWidget(self.gpuCombo)
        self.planLabel = label('')
        self.planLabel.setTextInteractionFlags(self.planLabel.textInteractionFlags())
        layout.addWidget(self.planLabel)
        self.consent = QCheckBox('安裝上列缺少工具；我同意其授權條款與套件來源條款')
        self.consent.setChecked(False)
        self.consent.toggled.connect(self.update_button)
        layout.addWidget(self.consent)
        self.status = label('不會自動改用 CPU。編譯失敗會保留先前的引擎，並顯示原因。')
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(1600)
        self.logs.setPlaceholderText('安裝與編譯記錄會顯示在這裡。安裝可能下載數 GB，並出現系統管理員／原廠安裝視窗。')
        layout.addWidget(self.logs, 1)
        actions = QHBoxLayout()
        self.rescanButton = QPushButton('重新偵測')
        self.rescanButton.clicked.connect(self.start_scan)
        self.closeButton = QPushButton('稍後設定')
        self.closeButton.clicked.connect(self.reject)
        self.buildButton = QPushButton('依顯卡編譯', objectName='PrimaryButton')
        self.buildButton.clicked.connect(self.start_build)
        self.buildButton.setEnabled(False)
        actions.addWidget(self.rescanButton)
        actions.addStretch()
        actions.addWidget(self.closeButton)
        actions.addWidget(self.buildButton)
        layout.addLayout(actions)
        self.missing = []
        if auto_scan: QTimer.singleShot(0, self.start_scan)

    def is_busy(self):
        return bool(self.worker and self.worker.isRunning())

    def begin(self, operation, success):
        if self.is_busy(): return
        self.buildButton.setEnabled(False)
        self.rescanButton.setEnabled(False)
        self.closeButton.setEnabled(False)
        self.gpuCombo.setEnabled(False)
        self.consent.setEnabled(False)
        self.progress.setRange(0, 0)
        self.worker = SetupWorker(operation, self)
        self.worker.log.connect(self.logs.appendPlainText)
        self.worker.result.connect(success)
        self.worker.failure.connect(self.failed)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        for widget in (self.rescanButton, self.closeButton, self.gpuCombo, self.consent): widget.setEnabled(True)
        self.update_button()

    def failed(self, error):
        self.status.setText(error)
        self.logs.appendPlainText('\n[未完成] ' + error)

    def start_scan(self):
        self.status.setText('正在讀取顯卡、驅動與編譯工具；此步驟不會安裝任何內容。')
        self.begin(lambda log: scan_host(), self.scanned)

    def scanned(self, scan):
        self.scan = scan
        self.systemLabel.setText(f'{"macOS" if scan.system == "Darwin" else scan.system} · {scan.machine}')
        self.gpuCombo.clear()
        for gpu in scan.gpus:
            self.gpuCombo.addItem(f'{gpu.name}  ·  {gpu.backend.upper()}', gpu)
        if not scan.gpus: self.gpuCombo.addItem('未偵測到可用顯卡', None)
        self.status.setText('\n'.join(scan.notes) or '偵測完成。請確認顯卡與下列編譯方案。')
        self.consent.setChecked(False)
        self.selection_changed()

    def selection_changed(self):
        gpu = self.gpuCombo.currentData()
        self.missing = []
        if not self.scan or gpu is None:
            self.planLabel.setText('找不到顯卡時，請先安裝原廠顯示卡驅動再重新偵測。')
            self.buildButton.setEnabled(False)
            return
        self.consent.setChecked(False)
        try:
            validate_selection(self.scan, gpu)
            self.missing = missing_tools(self.scan, gpu)
            plan = f'{gpu.architecture}\n{gpu.detail}\n'
            if gpu.driver: plan += f'驅動：{gpu.driver}\n'
            if gpu.backend == 'cuda': plan += f'CMake：GGML_CUDA=ON · CMAKE_CUDA_ARCHITECTURES={gpu.cc}\n'
            elif gpu.backend == 'vulkan': plan += 'CMake：GGML_VULKAN=ON；由顯卡驅動針對裝置編譯著色器。\n'
            else: plan += 'CMake：GGML_METAL=ON；使用系統預設 Metal 顯卡。\n'
            plan += ('需要安裝：' + '、'.join(self.missing)) if self.missing else '所需工具已就緒。'
            plan += '\n輸出：whisper.cpp/build/tjksub/ 內的獨立 GPU 編譯目錄。'
            if self.missing:
                plan += '\n來源：CMake／PyPI；Windows 使用 Microsoft winget 原廠安裝包，Mac 使用 Apple 或 Homebrew。'
            self.planLabel.setText(plan)
        except SetupError as exc:
            self.planLabel.setText(str(exc))
        self.consent.setVisible(bool(self.missing))
        self.update_button()

    def update_button(self):
        gpu = self.gpuCombo.currentData()
        eligible = bool(self.scan and gpu and not gpu.blocked)
        if eligible:
            try: validate_selection(self.scan, gpu)
            except SetupError: eligible = False
        self.buildButton.setText('安裝並編譯此顯卡' if self.missing else '依顯卡編譯')
        self.buildButton.setEnabled(eligible and not self.is_busy() and (not self.missing or self.consent.isChecked()))

    def start_build(self):
        if not self.buildButton.isEnabled(): return
        scan, gpu = self.scan, self.gpuCombo.currentData()
        install = bool(self.missing and self.consent.isChecked())
        self.logs.clear()
        self.status.setText('正在安裝／編譯。請完成原廠安裝視窗；為避免中斷工具安裝，此時暫停關閉視窗。')
        self.begin(lambda log: build_gpu(PROJECT_ROOT, scan, gpu, log, install=install), self.built)

    def built(self, result):
        self.owner.find_executable()
        self.owner.load_model_list()
        self.owner.populate_backend_combo()
        self.status.setText('GPU 引擎已編譯，啟動檢查通過。首次轉錄仍會驗證 GPU 初始化；失敗會停止並顯示原因。')
        self.closeButton.setText('完成')

    def reject(self):
        if not self.is_busy(): super().reject()

    def closeEvent(self, event):
        if self.is_busy(): event.ignore()
        else: super().closeEvent(event)
