# Rebuilding desktop packages

Build on the target OS and architecture with CPython 3.12. PyInstaller does not cross-compile. The GitHub workflow records exact tools, source hashes, checks and upload steps; all three platforms must pass before a version tag is published as a Release.

## macOS

Install Xcode Command Line Tools, then in a clean checkout:

```sh
python3.12 -m venv .build-venv
.build-venv/bin/python -m pip install -r packaging/requirements-build.txt
export PATH="$PWD/.build-venv/bin:$PATH"
export PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache"
export MACOSX_DEPLOYMENT_TARGET=12.0
python -m unittest discover -s tests -v
python packaging/build_native.py
python packaging/prepare_assets.py
python -m PyInstaller --noconfirm --clean packaging/TJKSub.spec
dist/TJKSub.app/Contents/MacOS/TJKSub --self-test build/frozen-smoke.json
python packaging/smoke_transcription.py --native dist/TJKSub.app/Contents/Frameworks/native --require-gpu
python packaging/make_release.py
python packaging/verify_install.py
```

On hosted machines without a usable GPU, omit `--require-gpu` for the pipeline smoke test; this tests CPU processing only and does not establish GPU compatibility. The normal UI still requires GPU confirmation. Native builds target macOS 12; use the Intel runner for x86_64 and the Apple Silicon runner for arm64.

## Windows x64

Use Visual Studio 2022 C++ Build Tools, Python 3.12 x64, MSYS2 MINGW64 (`make mingw-w64-x86_64-gcc diffutils`), Vulkan SDK 1.4.363.0, and Inno Setup 6. Set `VULKAN_SDK` and add its `Bin` directory to PATH. Install `packaging/requirements-build.txt` in a fresh virtual environment. Run `prepare_ffmpeg.py`, build `packaging/build_ffmpeg.sh` from MINGW64, then `build_native.py --ffmpeg-ready` from the Python environment. Follow the same asset, PyInstaller, self-test, transcription, release and install-test steps. The packaged executable is `dist/TJKSub/TJKSub.exe`; native binaries live in its `_internal/native` directory. `ISCC` should be on PATH or installed in its default Program Files (x86) location.

## Distribution and validation

The FFmpeg archive is SHA256-verified before extraction. Its complete build configuration is in `build_ffmpeg.sh`; the unchanged corresponding source archive is copied beside the installer. whisper.cpp is built from the vendored source without source changes. `prepare_assets.py` collects licenses, icons and version resources. Dependencies and native downloads are pinned in `requirements-build.txt`, `sources.json` and `install_vulkan.ps1`.

`--self-test` uses temporary settings and data, exercises three tabs, four locales, two themes, conversions, subtitle repair and packaged resources, then exits with a JSON report and screenshot. `verify_install.py` launches the installed/relocated program from paths containing spaces and Chinese characters, including a read-only DMG on macOS; Windows also tests installer removal. Tests never call a paid translation API.

Release binaries contain no models, API keys, local settings, source virtual environments or Git credentials. `v4.13.0` must match `WhisperGUI/version.json`. Push a version tag only after the main-branch workflow passes. A tag run rebuilds/tests all three platforms before the release job uploads installers, portable archives, source archive, licenses, installation instructions and SHA256 files.

Current signing: macOS ad hoc only; no Developer ID/notarization credentials or Windows code-signing certificate are configured. Do not label these packages notarized or signed by a verified publisher.
