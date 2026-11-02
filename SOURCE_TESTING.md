# 原始碼安裝與編譯驗證

此文件區分安裝／編譯成功與實際 GPU 執行成功。沒有實體 NVIDIA 顯卡的 GitHub runner，不能驗證 CUDA 加速或各款驅動相容性。

## 自動化範圍

- `Desktop packages`：Windows、Mac Apple Silicon、Mac Intel 的全新 Python 環境、一般啟動器、損壞環境備份、殘缺套件修復及中文／空白路徑。測試使用暫存副本，不動使用者模型。
- `Source setup and CUDA`：使用與設定視窗相同的工具偵測、安裝及 `build_gpu()`。Windows 經 NVIDIA 官方 redistributable 安裝 CUDA（每包 SHA256 與大小均鎖定），經 WinGet 安裝 FFmpeg；測試 Pascal `sm_61` 與 Blackwell `sm_121`。其中一組另安裝 Visual Studio Build Tools。Vulkan 與兩種 Mac 架構也執行原始碼編譯流程。
- CUDA 編譯測試使用明確標示的 CI 架構輸入；沒有模擬成功的 NVIDIA 驅動或 GPU 執行結果。啟動檢查後，以明確指定的 CPU 測試 FFmpeg → Whisper → SRT／TXT，涵蓋中文／空白模型與音訊路徑。
- 回歸測試涵蓋工具缺漏、CUDA 架構選擇、安裝順序、重新偵測、失敗保留舊引擎、GUI 授權勾選及工作中關閉保護。

工作流程結果與附件見 [GitHub Actions](https://github.com/konata91008/KonataWhisperGUI-Public/actions)。每次來源測試附上 `source-setup.json`、安裝編譯記錄及轉錄測試記錄，`gpu_execution_verified` 表示是否真的驗證 GPU。

## 有實體顯卡時執行

先使用一般啟動器完成 Python 環境與「顯卡與引擎設定」。在專案資料夾中執行下列命令，會重新編譯獨立引擎、下載約 78 MB 的 tiny 測試模型，並轉錄專案內的 JFK 音訊：

Windows NVIDIA：

```bat
venv\Scripts\python.exe tools\verify_source_setup.py --backend cuda
```

Windows AMD／Intel：

```bat
venv\Scripts\python.exe tools\verify_source_setup.py --backend vulkan
```

macOS：

```sh
venv/bin/python tools/verify_source_setup.py --backend metal
```

成功會產生 `build/source-setup.json` 與 `build/gpu-transcription.json`。實機模式必須收到引擎確認啟用選定 GPU 的訊息，且 SRT／TXT 匯出通過才算成功；不會自動以 CPU 代替。測試成功後使用新編譯引擎，失敗則保留原有設定。

`--install-tools` 可在明確同意原廠授權與套件來源條款後補裝工具。Windows 可能出現 UAC；Mac 缺 Apple Command Line Tools 時需先完成 Apple 視窗，再執行一次。CUDA 僅安裝編譯所需元件，不更換顯示卡驅動，也不執行 Visual Studio IDE 外掛註冊。工具位於 `%LOCALAPPDATA%/TJKSub/toolchains`，原有系統 CUDA 仍可使用；新工具完整下載並驗證後才加入偵測清單。

## 驗證限制

- Mac Apple M4：已實際完成一鍵安裝、Metal 編譯、GPU 轉錄及字幕匯出。
- Windows CUDA／Vulkan、Intel Mac Metal：CI 驗證安裝、編譯與 CPU 匯出流程；仍需對應硬體驗證 GPU 加速。
- CI 使用預裝部分系統元件的 runner，不等於所有 Windows 10／11 安裝狀態；UAC、重開機、驅動差異仍會依使用者環境而異。
- Premiere、DaVinci Resolve 等剪輯軟體的匯入相容性未由這些測試涵蓋。

## 原廠參考

- [NVIDIA CUDA Windows 安裝文件](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html)
- [CUDA 12.9 Windows 安裝文件](https://docs.nvidia.com/cuda/archive/12.9.1/cuda-installation-guide-microsoft-windows/index.html)
- [CMake 的 CUDA Visual Studio 整合路徑](https://cmake.org/cmake/help/v3.31/variable/CMAKE_VS_PLATFORM_TOOLSET_CUDA_CUSTOM_DIR.html)
- [Microsoft WinGet 安裝說明](https://learn.microsoft.com/en-us/windows/package-manager/winget/)
