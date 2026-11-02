import json
from .paths import resource_root

PROJECT_ROOT = resource_root()
with (PROJECT_ROOT / 'WhisperGUI' / 'version.json').open(encoding='utf-8') as stream:
    VERSION_INFO = json.load(stream)
VERSION_TEXT = f"v{VERSION_INFO['version']} · {VERSION_INFO['updated_at']}"
