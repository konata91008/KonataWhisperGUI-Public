TJKSub v4.14.1 · 更新日期 2026-11-04

「語言轉換」、「字幕排錯」、「字幕轉碼」現在都能直接拖入檔案；加入可辨識的虛線拖放區與高亮提示。Windows 與兩種 Mac 安裝包同步更新。

| 電腦 | 建議下載 |
| --- | --- |
| Windows 10 1903 以上／11 x64 | `TJKSub-4.14.1-windows-x64-setup.exe` |
| Mac Apple Silicon（M 系列） | `TJKSub-4.14.1-macos-arm64.dmg` |
| Mac Intel | `TJKSub-4.14.1-macos-x86_64.dmg` |

也提供 ZIP。macOS 需求為 12 以上。Windows ARM 尚未支援。安裝包內含 Python、Qt、whisper.cpp、FFmpeg 與繁簡字典，不需安裝開發工具；語音轉錄首次使用需下載模型及具備可用的 Metal（Mac）或 Vulkan（Windows）GPU／驅動。

- 字幕轉碼、繁簡轉換、SRT 排錯全程離線，不需 AI；跨語言翻譯及 AI 字幕優化需自行設定 API。
- 可拖到內容區、文字框或目前分頁空白處；一次接受一個對應格式的本機檔案，處理中不會被新檔案打斷。
- 拖放不會把路徑貼成字幕，不會移動原始檔，也不會自動發送翻譯 API 請求。
- 支援 SRT／TXT 匯出；字幕修正提供預覽並保護原始檔。
- 轉碼保留時間碼、格式及原始換行，預設另存 `_utf8` 檔案；不覆蓋原檔。判讀結果須確認預覽，解碼錯誤不略過或替換字元。
- 支援 SRT、ASS、SSA、VTT、SBV、文字型 SUB、TXT；每檔上限 20 MiB，預覽最多 100,000 字元，匯出保留全文。
- ANSI 依地區而異；若自動判讀出現亂碼，可手動選 Big5／CP950 或 GBK／GB18030 等編碼。原檔已存成問號或 � 的字元無法單靠轉碼復原。
- 原始碼版包含 v4.13.1 的啟動環境修復、Windows CUDA 工具安裝與編譯路徑修正；詳見 `SOURCE_TESTING.md`。
- 發布流程要求通過三平台建置、100 項回歸測試、GUI 啟動、音訊匯出及安裝檢查。Apple Silicon 另完成實體 Metal GPU 轉錄；Windows／Intel Mac 的 CI 轉錄使用 CPU，尚未涵蓋實體 Vulkan／Intel Metal 顯卡及所有剪輯軟體。AI API 以模擬服務測試。

**簽章狀態：** Windows 尚未簽署商用程式碼憑證，Mac 僅 ad hoc 簽章、尚未 Developer ID 簽署與 Apple 公證；首次安裝可能被系統提醒或阻擋。請閱讀附帶的 `INSTALL.md`，確認來源並比對 `SHA256SUMS-*.txt`。不需全域關閉系統安全功能。

主程式採 **GPL-3.0-or-later**。相符主程式、whisper.cpp 與建置腳本請下載此 tag 原始碼；FFmpeg 原始碼另附 `ffmpeg-9.0.2.tar.xz`，其他第三方元件見 `THIRD_PARTY_NOTICES.md`。模型與私人設定不包含在下載包中。
