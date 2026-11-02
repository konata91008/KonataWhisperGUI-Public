# TJKSub / KonataWhisperGUI

支援 macOS 與 Windows 的 whisper.cpp 語音轉錄介面，提供秋日暖色主題、字幕匯出、語言轉換、字幕排錯、GPU 設定與選用的 AI 字幕優化。

目前版本：**v4.13.2 · 2026-11-02**

版本變更請見 [版本紀錄](CHANGELOG.md)。

## 下載安裝版（一般使用者）

從 [GitHub Releases](https://github.com/konata91008/KonataWhisperGUI-Public/releases/latest) 下載對應版本：

| 系統 | 下載檔案 | 安裝方式 |
| --- | --- | --- |
| Windows 10 1903 以上／11 x64 | `TJKSub-4.13.2-windows-x64-setup.exe` | 執行安裝程式，安裝至目前使用者帳戶 |
| Mac Apple Silicon（M 系列） | `TJKSub-4.13.2-macos-arm64.dmg` | 開啟後把 TJKSub 拖進 Applications |
| Mac Intel | `TJKSub-4.13.2-macos-x86_64.dmg` | 開啟後把 TJKSub 拖進 Applications |

Mac 需求為 macOS 12 以上及可用的 Metal GPU。Windows 需求為 x64 處理器、支援 Vulkan 的 GPU 與原廠驅動；Windows ARM 尚未支援。另提供 Windows portable ZIP 與 Mac app ZIP。

安裝版已包含 Python、Qt、whisper.cpp、FFmpeg 與繁簡轉換字典，不需自行安裝開發工具。語音轉錄首次使用仍需下載模型；模型不隨安裝包附送。繁簡轉換與字幕排錯可以離線使用；跨語言翻譯需自行設定 API。

目前 Windows 程式未購買程式碼簽章，Mac 使用 ad hoc 簽章、尚未經 Developer ID 簽署及 Apple 公證，因此首次開啟可能出現系統警告或被阻擋。請確認檔案來自本專案 Release 並比對 SHA256；Mac 若提供「隱私權與安全性 → 強制打開」可依系統提示操作。不需要全域關閉系統安全功能。詳見 [安裝說明](packaging/INSTALL.md)。

模型資料位於 `%LOCALAPPDATA%/TJKSub/models`（Windows）或 `~/Library/Application Support/TJKSub/models`（Mac）；程式搬移、更新與移除不會自動刪除這些模型。安裝版的「檢查更新」會開啟正式 Release 頁面，下載新版本後重新安裝即可。

## 從原始碼啟動（開發者）

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

首次啟動會準備 Python 環境及套件，再開啟主視窗。「語言轉換」中的繁簡模式及「字幕排錯」可直接使用；需要語音轉錄時，請從齒輪開啟「顯卡與引擎設定」，確認偵測結果後，依視窗指示安裝工具並編譯引擎，接著下載所需模型。

這是**原始碼發行版**，不含預先編譯的引擎、模型或系統驅動。首次設定需要網路、儲存空間與編譯時間；工具安裝可能需要系統管理員權限。

也可使用 Download ZIP 取得原始碼，但 ZIP 不包含 `.git`，無法直接使用介面內的 Git 自動更新。

## 顯卡與引擎

安裝版固定使用 Mac Metal／Windows Vulkan，無需編譯。以下為原始碼版的自訂引擎流程：

- macOS：偵測系統預設 Metal GPU，依 Apple Silicon／Intel 主機架構編譯。
- Windows NVIDIA：由驅動讀取 Compute Capability，確認 CUDA 工具支援該架構後編譯。
- Windows AMD／Intel：使用 Vulkan，驗證驅動提供的實體 GPU 後編譯。

CUDA 設定會檢查架構支援、必要函式庫及 Visual Studio 整合檔；缺少元件時可重新安裝。CUDA 使用 NVIDIA 官方元件並核對 SHA256，安裝至使用者資料夾；不替換 NVIDIA 驅動，也不註冊 Visual Studio IDE 外掛。詳細測試範圍與實機驗證指令見 [原始碼測試說明](SOURCE_TESTING.md)。

編譯結果放在 `whisper.cpp/build/tjksub/`，成功後透過 `whisper.cpp/build/tjksub-runtime.json` 指定使用的引擎。GPU 初始化失敗會停止轉錄，不會自行改用 CPU 模式；GPU 加速仍會使用 CPU 做音訊前處理與部分工作。

Mac Apple Silicon 已完成 Metal 實際音訊轉錄與 SRT／TXT 匯出測試。Windows／Intel Mac 透過對應 GitHub runner 驗證建置、啟動、安裝及 CPU 轉錄流程；CI 的 CPU 模式僅用於測試，產品仍要求 GPU。CUDA 12.9 另驗證完整編譯及 DLL 相依，啟動因 CI 缺少 NVIDIA 驅動而未驗證；CUDA 13.4 已通過啟動與 CPU 轉錄。Windows CUDA／Vulkan 與 Intel Mac Metal 尚待實體顯卡驗證，不能保證所有顯卡與驅動組合都能使用。

## 語言轉換

主視窗提供「語音轉錄」、「語言轉換」與「字幕排錯」三個分頁。在語言轉換頁選擇處理方式：

- **繁體 → 簡體／簡體 → 繁體**：使用 OpenCC `t2s`／`s2t` 在本機離線轉換，不需 API、模型或 GPU。保留分行，不做地區詞彙替換；多義字仍需人工確認。
- **跨語言翻譯（API）**：選擇來源語言（可自動偵測）與目標語言，完成 API 設定後按「開始翻譯」。提供繁中、簡中、英文、日文、韓文、西班牙文、法文、德文、義大利文、葡萄牙文、俄文、越南文、泰文、印尼文及阿拉伯文選項；實際翻譯能力依所選模型而定。
- 翻譯沿用現有 OpenAI 相容、Gemini 或 Claude API 設定。畫面會顯示目的服務及模型；只有按下開始翻譯才會傳送文字，費用與資料處理由所選供應商決定。API Key 只保留在本次程式記憶體。
- 兩種模式皆可匯入 `.txt`／`.srt`，支援 UTF-8（含 BOM）及含 BOM 的 UTF-16；檔案上限 2 MB，文字上限 50 萬字。API 翻譯的單行文字或單段字幕上限為 6,000 字，超過時須先分段。
- SRT 翻譯只傳送字幕文字，字幕編號及時間碼由程式保留。純文字翻譯保留原有分行與空白行。API 回傳格式不符時不套用結果。
- 原文與結果並排顯示，可複製或另存為 UTF-8，另存不允許覆蓋匯入的原始檔。翻譯完成後請對照原文檢查內容。
- 翻譯顯示批次進度並可取消；取消會等待目前請求結束，不再傳送下一批，也不保留部分結果。已送出的請求可能仍會計費。
- 更改原文、處理方式或翻譯語言後，舊結果會清空。內容不自動寫入設定；關閉視窗即結束本次內容。

介面 Logo 採用 8-bit 像素楓葉與飄散的方形粒子，搭配秋日暖棕及金色的向量圖，原始檔位於 `WhisperGUI/gui/resources/autumn-logo.svg`。

## 字幕排錯（不需 AI）

時間重疊、結束早於開始、段落分隔與時間碼格式都可用確定性規則檢查，不需要 AI、API Key、語音模型或 GPU。此分頁全程在本機處理，不傳送字幕，也不自動寫入設定。

1. 開啟「字幕排錯」，匯入 `.srt` 或貼上字幕，按「檢查字幕」。
2. 右側列出錯誤／提醒、原文行號與建議；點選一列會定位到對應字幕。即使中間段落損壞，也會繼續掃描後面的內容。
3. 在原文區修正無效時間碼、結束早於／等於開始、缺少文字及無法辨識的段落，然後重新檢查。這些問題不會以猜測時間或刪除字幕的方式修復。
4. 按「產生修正預覽」，整理連續編號、可辨識的時間碼格式與缺少的段落空白行。字幕文字及可辨識的位置附加資訊會保留。
5. 視需要勾選「依開始時間排序」及「縮短前段以消除重疊」，兩者預設關閉。消除重疊會把前段結束縮至下一段開始前 **1 毫秒**，不平移後續字幕、不合併或刪除段落。若開始時間相同或過近、縮短後沒有正時長，會要求手動處理，不輸出部分結果。
6. 預覽會重新檢查，右側可切換原文／預覽結果。確認後可複製或另存 UTF-8 `.srt`，預設檔名為 `原檔名.fixed.srt`，禁止覆蓋匯入原檔（包含同一檔案的連結）。

檢查範圍包含編號不連續／重複、缺少編號或分隔、非標準／無效時間碼、時間倒退、無效時長、巢狀重疊、空字幕、控制字元，以及少於 100 毫秒的短字幕。重疊與短時長列為提醒，因為可能是有意安排；輸出預覽仍會顯示尚待確認的提醒。原文或修正選項一改動，舊預覽即失效，避免誤存過期結果。

匯入支援 UTF-8（含 BOM）與含 BOM 的 UTF-16，上限 2 MB／50 萬字。純文字沒有時間碼時無法自動生成有效 SRT；未知格式或有歧義的時間行需人工判斷。本工具不檢查字幕語意、影片長度、幀率或實際口型同步，也不能保證所有剪輯軟體的匯入行為。

格式依據參考 [美國國會圖書館的 SRT 說明](https://www.loc.gov/preservation/digital/formats/fdd/fdd000569.shtml)。字幕只匯入一部分，也可能與多餘換行或時間安排有關，見 [Simon Says 的匯入排錯說明](https://www.simonsaysai.com/help/5072306-srt-subtitle-file-does-not-import-troubleshooting)。

自動驗證涵蓋 50 項功能測試與四語／深淺色／三分頁的 24 種小視窗組合。SRT 尚未在 Premiere 或其他剪輯軟體實機匯入驗證。API 翻譯與優化使用模擬服務測試，未向付費 API 發送測試內容。

## 字幕與 AI 優化

選取音訊／影片、語言、模型與輸出位置後開始轉錄，完成視窗可查看結果並選擇「AI 優化字幕」。

- 齒輪內可設定 OpenAI 相容 Chat Completions、Gemini 原生或 Claude 原生 API，支援自訂網址與模型。
- API Key 只留在本次程式記憶體，關閉後需重新輸入；修改 API 網址會清空 Key。
- AI 優化會將字幕文字與本次指示送至你設定的 API 服務，請自行確認供應商條款、資料處理方式與費用。
- 原始字幕保留，AI 只改文字；原編號與時間碼由程式保留。優化結果需手動匯出，另存為 `.ai.srt`／`.ai.txt`，不覆蓋原檔。
- 轉錄與 AI 優化的 Prompt 各自只作用於當次工作，開始後清空，不寫入設定。
- 檔案清單支援 Delete／Backspace 移除選取項目，不刪除原始檔案。

## 檢查更新

安裝版會開啟 GitHub Releases 下載頁。以下 Git 更新流程僅適用原始碼版。

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

## 授權與第三方軟體

TJKSub 主程式採用 **GNU GPL v3 或更新版本（GPL-3.0-or-later）**，完整條文見 [LICENSE](LICENSE)。你可以依授權使用、修改與散布；散布衍生程式及二進位時須遵守 GPL 的原始碼與授權要求。軟體不提供擔保。

第三方元件保留各自授權，清單及對應原始碼見 [第三方聲明](packaging/THIRD_PARTY_NOTICES.md)。安裝包內附授權文字，Release 附上相同版本 FFmpeg 原始碼；主程式及引擎原始碼可由相同版本 Git tag 取得。建置方式見 [封裝文件](packaging/BUILD.md)。

引擎來自 [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)，授權與著作權聲明保留於 [whisper.cpp/LICENSE](whisper.cpp/LICENSE) 及各第三方元件目錄。其餘依賴適用各自授權。

本副本以目前原始碼建立獨立歷史，不包含舊 Git 歷史、本機編譯產物、Java 快取、模型、個人環境或 API 金鑰。部分功能與文件使用 AI 協助開發；相容性以實際測試及使用環境為準。
