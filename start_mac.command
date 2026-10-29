#!/bin/bash
# ============================================================
# TJKSub 啟動腳本 (macOS)
# [修復說明]
# 舊版直接 source venv + 執行 `python`，在以下情況會直接閃退：
#   1. venv 不存在，或是從別台電腦複製來的（venv 內含絕對路徑，會失效）
#   2. macOS 沒有 `python` 指令（只有 python3）
#   3. 發生錯誤時視窗立刻關閉，看不到訊息
# 新版：自動檢查/重建 venv、自動補裝套件、錯誤時保留視窗。
# ============================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

fail() {
    echo ""
    echo "[錯誤] $1"
    echo "按 Enter 關閉視窗..."
    read -r
    exit 1
}

# 1. 確認系統有 python3（macOS 沒有 `python` 指令）
TJK_PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if "$candidate" -c 'import sys; assert (3,10) <= sys.version_info[:2] <= (3,12)' >/dev/null 2>&1; then
        TJK_PYTHON="$candidate"
        break
    fi
done

# 2. 檢查 venv 是否存在且「可用」——venv 內含建立當下的絕對路徑，
#    換電腦或移動資料夾後會失效，此時自動重建
if ! "$DIR/venv/bin/python" -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,12)" >/dev/null 2>&1; then
    [ -n "$TJK_PYTHON" ] || fail "請先安裝 Python 3.10~3.12 (https://www.python.org)"
    echo "虛擬環境不存在或已失效，正在重新建立（首次需要幾分鐘）..."
    if [ -e "$DIR/venv" ]; then
        mv "$DIR/venv" "$DIR/venv.backup-$(date +%Y%m%d%H%M%S)-$$" || fail "無法備份舊 venv"
    fi
    "$TJK_PYTHON" -m venv "$DIR/venv" || fail "建立虛擬環境失敗"
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt" || fail "安裝套件失敗，請檢查網路連線"
fi

# 3. venv 存在但套件不齊時，自動補裝
if ! "$DIR/venv/bin/python" -c "import PyQt5, opencc" >/dev/null 2>&1; then
    echo "偵測到缺少 PyQt5，正在安裝套件..."
    "$DIR/venv/bin/pip" install -r "$DIR/requirements.txt" || fail "安裝套件失敗，請檢查網路連線"
fi

# 4. 啟動（直接用 venv 的 python，不依賴 activate）
echo "正在啟動 TJKSub..."
"$DIR/venv/bin/python" "$DIR/WhisperGUI/main.py" "$@"
code=$?
if [ $code -ne 0 ]; then
    fail "程式異常結束 (exit code: $code)，以上為錯誤訊息"
fi
