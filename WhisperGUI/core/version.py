import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
with (PROJECT_ROOT / 'WhisperGUI' / 'version.json').open(encoding='utf-8') as stream:
    VERSION_INFO = json.load(stream)
VERSION_TEXT = f"v{VERSION_INFO['version']} · {VERSION_INFO['updated_at']}"
