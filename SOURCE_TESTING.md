# 原始碼安裝與編譯驗證

此文件區分安裝／編譯成功與實際 GPU 執行成功。沒有實體 NVIDIA 顯卡的 GitHub runner，不能驗證 CUDA 加速或各款驅動相容性。

## 自動化範圍

- `Source Python compatibility`：Windows、Mac Apple Silicon、Mac Intel 使用 Python 3.10／3.11 的空白 venv，由一般設定啟動器安裝套件、開啟介面並跑回歸測試；Python 3.12 由下列完整流程驗證。

- `Desktop packages`：Windows、Mac Apple Silicon、Mac Intel 的全新 Python 環境、一般啟動器、損壞環境備份、殘缺套件修復及中文／空白路徑。測試使用暫存副本，不動使用者模型。
- `Source setup and CUDA`：使用與設定視窗相同的工具偵測、安裝及 `build_gpu()`。Windows 經 NVIDIA 官方 redistributable 安裝 CUDA（每包 SHA256 與大小均鎖定），經 WinGet 安裝 FFmpeg；測試 Pascal `sm_61` 與 Blackwell `sm_121`。其中一組另安裝 Visual Studio Build Tools。Vulkan 與兩種 Mac 架構也執行原始碼編譯流程。
- CUDA 編譯測試使用明確標示的 CI 架構輸入；沒有模擬成功的 NVIDIA 驅動或 GPU 執行結果。CI 會實際嘗試啟動 CUDA 引擎。若測試機缺少 NVIDIA 驅動的 `nvcuda.dll`，則用 Visual Studio `dumpbin` 遞迴檢查引擎與 CUDA DLL 相依，只有缺少這一個驅動時才記為硬體限制；其他缺檔或錯誤仍會失敗。此情況不啟用該引擎、不執行 CUDA 版轉錄，也不提供假驅動。Vulkan／Metal 與封裝工作流程以明確指定的 CPU 測試 FFmpeg → Whisper → SRT／TXT，涵蓋中文／空白模型與音訊路徑。
- 回歸測試涵蓋工具缺漏、CUDA 架構選擇、安裝順序、重新偵測、失敗保留舊引擎、GUI 授權勾選及工作中關閉保護。

工作流程結果與附件見 [GitHub Actions](https://github.com/konata91008/KonataWhisperGUI-Public/actions)。每次來源測試附上 `source-setup.json`、安裝編譯記錄及轉錄測試記錄，`gpu_execution_verified` 表示是否真的驗證 GPU；`launchable` 與 `launch_blocked_by` 另記錄啟動結果。

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
- Windows CUDA：CI 驗證安裝、完整編譯／連結。12.9 本次因缺少 `nvcuda.dll`，另驗證 DLL 相依並將啟動／轉錄記為未驗證；13.4 本次可啟動並通過 CPU 轉錄。兩者的 GPU 加速仍需 Windows NVIDIA 實機。
- Windows Vulkan、Intel Mac Metal：CI 驗證安裝、編譯與 CPU 匯出流程；仍需對應硬體驗證 GPU 加速。
- CI 使用預裝部分系統元件的 runner，不等於所有 Windows 10／11 安裝狀態；UAC、重開機、驅動差異仍會依使用者環境而異。
- Premiere、DaVinci Resolve 等剪輯軟體的匯入相容性未由這些測試涵蓋。

## 2026-11-02 驗證結果

引擎與安裝邏輯測試提交：`a27c104`；Python 相容性工作流程與封裝測試提交：`6766e7e`。之後的測試紀錄文件更新不改變程式碼。

| 項目 | 實際結果 |
| --- | --- |
| Windows CUDA 12.9／sm_61 | 官方元件下載及 SHA256、Build Tools 安裝、完整編譯／連結通過；DLL 相依僅缺 NVIDIA 驅動 `nvcuda.dll`。未啟動、未轉錄，不啟用未通過啟動的引擎。 |
| Windows CUDA 13.4／sm_121 | 官方元件下載及 SHA256、完整編譯、啟動、中文／空白路徑 CPU 轉錄與 SRT／TXT 匯出通過。未驗證實體 GPU。 |
| Windows Vulkan／Mac Apple Silicon／Mac Intel | 原始碼設定啟動器、工具安裝、引擎編譯、啟動與 CPU 轉錄／匯出通過。 |
| 本機 Apple M4 | 全新原始碼環境、Metal 編譯、實際 GPU 轉錄與 SRT／TXT 匯出通過。 |
| Python 3.10／3.11 × Windows／兩種 Mac | 六組空白 venv 的套件安裝、設定啟動器、介面開啟與各 75 項回歸測試均通過。Intel Mac 3.11 曾遇到 原始碼下載停滯，單組重試後通過。 |
| Windows／兩種 Mac 的完整封裝流程 | 各 75 項回歸測試、原始碼啟動、損壞 venv／套件修復、封裝、安裝及搬移啟動通過。 |

[原始碼與 CUDA 完整記錄](https://github.com/konata91008/KonataWhisperGUI-Public/actions/runs/41399918661)、[Python 3.10／3.11 相容性記錄](https://github.com/konata91008/KonataWhisperGUI-Public/actions/runs/41401583295)、[封裝與 Python 3.12 記錄](https://github.com/konata91008/KonataWhisperGUI-Public/actions/runs/41401583271)。

## 原廠參考

- [NVIDIA CUDA Windows 安裝文件](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html)
- [CUDA 12.9 Windows 安裝文件](https://docs.nvidia.com/cuda/archive/12.9.1/cuda-installation-guide-microsoft-windows/index.html)
- [CMake 的 CUDA Visual Studio 整合路徑](https://cmake.org/cmake/help/v3.31/variable/CMAKE_VS_PLATFORM_TOOLSET_CUDA_CUSTOM_DIR.html)
- [Microsoft WinGet 安裝說明](https://learn.microsoft.com/en-us/windows/package-manager/winget/)
