STRINGS = {
    'zh_TW': {
        'backend_unset': '尚未設定顯卡 · 請開啟齒輪設定', 'backend_hint': '使用已設定的 GPU，不會自動切換 CPU。', 'gpu_settings': '顯卡與引擎設定…',
        'tagline': '語音與文字工作室', 'files_title': '媒體檔案',
        'files_empty': '從一段聲音開始', 'files_hint': '將音訊或影片拖曳到這裡\n也可以使用下方的匯入按鈕',
        'settings_title': '轉錄設定', 'transcription_hint': '音訊在本機轉錄，完成後匯出字幕或逐字稿。',
        'conversion_title': '讓文字自在轉換', 'conversion_hint': '繁體與簡體雙向轉換，保留字幕時間碼與段落。',
        'offline': '本機離線處理', 'theme': '切換深淺色', 'minimize': '最小化',
        'maximize': '放大／還原', 'close': '關閉',
    },
    'zh_CN': {
        'backend_unset': '尚未设置显卡 · 请打开设置', 'backend_hint': '使用已设置的 GPU，不会自动切换 CPU。', 'gpu_settings': '显卡与引擎设置…',
        'tagline': '语音与文字工作室', 'files_title': '媒体文件',
        'files_empty': '从一段声音开始', 'files_hint': '将音频或视频拖到这里\n也可以使用下方的导入按钮',
        'settings_title': '转录设置', 'transcription_hint': '音频在本机转录，完成后导出字幕或文字稿。',
        'conversion_title': '让文字自在转换', 'conversion_hint': '繁体与简体双向转换，保留字幕时间码与段落。',
        'offline': '本机离线处理', 'theme': '切换深浅色', 'minimize': '最小化',
        'maximize': '放大／还原', 'close': '关闭',
    },
    'en': {
        'backend_unset': 'GPU not configured · Open settings', 'backend_hint': 'Uses the configured GPU, without automatic CPU fallback.', 'gpu_settings': 'GPU & engine settings…',
        'tagline': 'A studio for voice & text', 'files_title': 'Media files',
        'files_empty': 'Start with a sound', 'files_hint': 'Drop audio or video here\nor use the import button below',
        'settings_title': 'Transcription settings', 'transcription_hint': 'Transcribe locally, then export subtitles or a transcript.',
        'conversion_title': 'Give your words a new form', 'conversion_hint': 'Convert Chinese scripts while keeping subtitle timing and paragraphs.',
        'offline': 'Local & offline', 'theme': 'Switch light / dark theme', 'minimize': 'Minimize',
        'maximize': 'Maximize / restore', 'close': 'Close',
    },
    'ja': {
        'backend_unset': 'GPU 未設定 · 設定を開く', 'backend_hint': '設定済みの GPU を使用します。CPU への自動切り替えはありません。', 'gpu_settings': 'GPU とエンジンの設定…',
        'tagline': '音声とテキストのスタジオ', 'files_title': 'メディアファイル',
        'files_empty': '音声からはじめる', 'files_hint': '音声や動画をここにドラッグ\nまたは下のボタンから読み込み',
        'settings_title': '文字起こしの設定', 'transcription_hint': 'ローカルで文字起こしし、字幕やテキストに書き出します。',
        'conversion_title': '文字を、読みたいかたちに', 'conversion_hint': '字幕のタイムコードと段落を保ちながら、繁体字と簡体字を変換します。',
        'offline': 'ローカル・オフライン', 'theme': 'ライト／ダークを切り替え', 'minimize': '最小化',
        'maximize': '最大化／元に戻す', 'close': '閉じる',
    },
}


def interface_strings(language):
    return STRINGS.get(language, STRINGS['en'])
