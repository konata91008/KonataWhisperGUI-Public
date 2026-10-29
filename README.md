# TJKSub / KonataWhisperGUI

支援 macOS 與 Windows 的 whisper.cpp 語音轉錄介面，提供奶茶色主題、字幕匯出、GPU 設定與選用的 AI 字幕優化。

版本：**v4.9.2 · 2026-10-29**

## 安裝與啟動

1. 安裝 Python **3.10–3.12**；Windows 使用 **64 位元**版本。
2. 建議安裝 Git，再執行：

   ```sh
   git clone https://github.com/konata91008/KonataWhisperGUI-Public.git
   ```

3. 進入專案資料夾，雙擊對應啟動檔：

   | 系統 | 啟動檔 |
   | --- | --- |
   | macOS | `start_mac.command` |
   | Windows | `Start_Windows.bat` |

首次啟動會準備 Python 環境及套件，再開啟顯卡與引擎設定。確認偵測結果後，依視窗指示安裝工具並編譯引擎，接著下載所需模型。

這是**原始碼發行版**，不含預先編譯的引擎、模型或系統驅動。首次設定需要網路、儲存空間與編譯時間；工具安裝可能需要系統管理員權限。

也可使用 Download ZIP 取得原始碼，但 ZIP 不包含 `.git`，無法直接使用介面內的 Git 自動更新。

## 顯卡與引擎

- macOS：偵測系統預設 Metal GPU，依 Apple Silicon／Intel 主機架構編譯。
- Windows NVIDIA：由驅動讀取 Compute Capability，確認 CUDA 工具支援該架構後編譯。
- Windows AMD／Intel：使用 Vulkan，驗證驅動提供的實體 GPU 後編譯。

編譯結果放在 `whisper.cpp/build/tjksub/`，成功後透過 `whisper.cpp/build/tjksub-runtime.json` 指定使用的引擎。GPU 初始化失敗會停止轉錄，不會自行改用 CPU 模式；GPU 加速仍會使用 CPU 做音訊前處理與部分工作。

Windows 顯卡安裝、編譯與實際轉錄**尚待實機驗證**，不能保證所有顯卡與驅動組合都能使用。Mac 已驗證偵測流程；完整轉錄仍需依電腦、模型與音訊實測。

## 字幕與 AI 優化

選取音訊／影片、語言、模型與輸出位置後開始轉錄，完成視窗可查看結果並選擇「AI 優化字幕」。

- 齒輪內可設定 OpenAI 相容 Chat Completions、Gemini 原生或 Claude 原生 API，支援自訂網址與模型。
- API Key 只留在本次程式記憶體，關閉後需重新輸入；修改 API 網址會清空 Key。
- AI 優化會將字幕文字與本次指示送至你設定的 API 服務，請自行確認供應商條款、資料處理方式與費用。
- 原始字幕保留，AI 只改文字；原編號與時間碼由程式保留。優化結果需手動匯出，另存為 `.ai.srt`／`.ai.txt`，不覆蓋原檔。
- 轉錄與 AI 優化的 Prompt 各自只作用於當次工作，開始後清空，不寫入設定。
- 檔案清單支援 Delete／Backspace 移除選取項目，不刪除原始檔案。

## 檢查更新

齒輪 → 檢查 GitHub 更新 → 確認下載 → 選擇立即或稍後重啟。

更新來源固定為 **`konata91008/KonataWhisperGUI-Public` 的 `main` 分支**。公開 HTTPS 讀取不需登入；使用 SSH 網址時仍需自己的 SSH 金鑰。

只有位於 `main`、保留正確 `origin`、沒有本機修改且可快轉的 Git 安裝才能自動更新。更新不會強制重設、丟棄本機變更或刪除被 Git 忽略的模型與環境。依賴或引擎來源有變更時，可能需在重啟後另行安裝套件或重新編譯。

由不同儲存庫或不同歷史的安裝切換時，請**在新資料夾重新 clone**，保留舊安裝；模型可自行複製，再於新位置設定 GPU。不要直接合併兩份歷史或強制同步。

## 資料夾

- `WhisperGUI/`：主程式。
- `whisper.cpp/`：引擎原始碼、範例與第三方授權文件。
- `tools/`：設定及更新捷徑，一般可直接使用齒輪。
- `requirements.txt`：Python 套件清單。
- `venv/`、`whisper.cpp/build/`：使用時在本機建立，不隨原始碼發佈。

請保留整個專案資料夾的位置關係。桌面啟動請建立替身／捷徑。

## 第三方軟體與發佈範圍

引擎來自 [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)，授權與著作權聲明保留於 [whisper.cpp/LICENSE](whisper.cpp/LICENSE) 及各第三方元件目錄。其餘依賴適用各自授權。

本副本以目前原始碼建立獨立歷史，不包含舊 Git 歷史、本機編譯產物、Java 快取、模型、個人環境或 API 金鑰。部分功能與文件使用 AI 協助開發；相容性以實際測試及使用環境為準。
