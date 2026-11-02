STRINGS = {
 'zh_TW': {
  'setup_title': '內建轉錄引擎',
  'setup': '安裝版已內附 {backend} 引擎與 FFmpeg，不需要 Python 或編譯工具。\n\n請先在模型選單下載模型，再匯入音訊或影片。GPU 驅動必須可用；初始化失敗時會停止，不會自動改用 CPU。\n\n模型位置：{models}',
  'broken': '找不到完整的內建引擎。請從官方 GitHub Releases 重新安裝對應系統的版本。',
  'updates_title': '下載新版安裝程式',
  'updates': '安裝版請透過官方 GitHub Releases 下載新版，再關閉程式後安裝。模型與 API 網址設定保留於使用者資料夾；API Key 不會寫入設定檔。',
  'open_releases': '開啟下載頁', 'close': '關閉',
 },
 'zh_CN': {
  'setup_title': '内置转录引擎',
  'setup': '安装版内置 {backend} 引擎与 FFmpeg，无需 Python 或编译工具。\n\n先从模型菜单下载模型，再导入音频或视频。GPU 驱动必须可用；初始化失败时会停止，不会自动改用 CPU。\n\n模型位置：{models}',
  'broken': '找不到完整的内置引擎。请从官方 GitHub Releases 重新安装对应系统的版本。',
  'updates_title': '下载新版安装程序',
  'updates': '安装版请通过官方 GitHub Releases 下载新版，关闭程序后安装。模型与 API 网址设置保留在用户目录；API Key 不写入设置文件。',
  'open_releases': '打开下载页', 'close': '关闭',
 },
 'en': {
  'setup_title': 'Bundled transcription engine',
  'setup': 'This installation includes the {backend} engine and FFmpeg. Python and build tools are not required.\n\nDownload a model from the model menu, then import audio or video. A working GPU driver is required. GPU initialization failures stop transcription without automatic CPU fallback.\n\nModels: {models}',
  'broken': 'Bundled engine files are missing. Reinstall the correct platform package from the official GitHub Releases page.',
  'updates_title': 'Download an updated installer',
  'updates': 'Download the new installer from official GitHub Releases, close the app, then install it. Models and API URL settings remain in your user data. API keys are never saved in settings.',
  'open_releases': 'Open downloads', 'close': 'Close',
 },
 'ja': {
  'setup_title': '同梱の文字起こしエンジン',
  'setup': '{backend} エンジンと FFmpeg を同梱しています。Python やビルドツールは不要です。\n\nモデルをダウンロードして音声・動画を読み込んでください。GPU ドライバーが必要です。GPU の初期化に失敗した場合は停止し、CPU に自動切り替えしません。\n\nモデルの保存先：{models}',
  'broken': '同梱エンジンが見つかりません。公式 GitHub Releases から対応版を再インストールしてください。',
  'updates_title': '最新版のダウンロード',
  'updates': '公式 GitHub Releases から最新版をダウンロードし、アプリを閉じてインストールしてください。モデルと API URL 設定はユーザーフォルダーに保持されます。API キーは保存しません。',
  'open_releases': 'ダウンロードページ', 'close': '閉じる',
 },
}


def distribution_strings(language):
    return STRINGS.get(language, STRINGS['en'])
