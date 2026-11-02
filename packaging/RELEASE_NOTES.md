TJKSub v4.13.0 · 更新日期 2026-11-02

首次提供可直接安裝的 Windows 與 Mac 版本，包含語音轉錄、語言轉換、字幕排錯及 8-bit 秋日楓葉介面。

| 電腦 | 建議下載 |
| --- | --- |
| Windows 10/11 x64 | `TJKSub-4.13.0-windows-x64-setup.exe` |
| Mac Apple Silicon（M 系列） | `TJKSub-4.13.0-macos-arm64.dmg` |
| Mac Intel | `TJKSub-4.13.0-macos-x86_64.dmg` |

也提供 ZIP。macOS 需求為 12 以上。Windows ARM 尚未支援。安裝包內含 Python、Qt、whisper.cpp、FFmpeg 與繁簡字典，不需安裝開發工具；語音轉錄首次使用需下載模型及具備可用的 Metal（Mac）或 Vulkan（Windows）GPU／驅動。

- 繁簡轉換、SRT 排錯全程離線，不需 AI；跨語言翻譯及 AI 字幕優化需自行設定 API。
- 支援 SRT／TXT 匯出；字幕修正提供預覽並保護原始檔。
- 修正新版 Metal 引擎判讀；模型下載中斷不破壞既有模型。
- 版本已通過三平台建置、50 項測試、GUI 啟動、音訊匯出及安裝檢查。Apple Silicon 另完成實體 Metal GPU 轉錄；Windows／Intel Mac 的 CI 轉錄使用 CPU，尚未涵蓋實體 Vulkan／Intel Metal 顯卡及所有剪輯軟體。AI API 以模擬服務測試。

**簽章狀態：** Windows 尚未簽署商用程式碼憑證，Mac 僅 ad hoc 簽章、尚未 Developer ID 簽署與 Apple 公證；首次安裝可能被系統提醒或阻擋。請閱讀附帶的 `INSTALL.md`，確認來源並比對 `SHA256SUMS-*.txt`。不需全域關閉系統安全功能。

主程式採 **GPL-3.0-or-later**。相符主程式、whisper.cpp 與建置腳本請下載此 tag 原始碼；FFmpeg 原始碼另附 `ffmpeg-9.0.2.tar.xz`，其他第三方元件見 `THIRD_PARTY_NOTICES.md`。模型與私人設定不包含在下載包中。
