# TJKSub third-party software

TJKSub is free software under GNU GPL version 3 or later. The application source,
including its build/install scripts, is available at:
https://github.com/konata91008/KonataWhisperGUI-Public
Use the release tag matching the installed application version.

The distribution includes the following independently licensed components:

| Component | Version | License | Corresponding source |
| --- | --- | --- | --- |
| CPython | 3.12 | PSF License | https://www.python.org/downloads/source/ |
| PyQt5 | 5.15.11 | GPLv3 | https://pypi.org/project/PyQt5/5.15.11/#files |
| Qt | 5.15.19 (macOS), 5.15.2 (Windows) | LGPLv3 / GPLv3 and component licenses | https://download.qt.io/archive/qt/5.15/5.15.19/ ; https://download.qt.io/archive/qt/5.15/5.15.2/ |
| PyQt5-sip | 12.20.0 | BSD-2-Clause | https://pypi.org/project/PyQt5-sip/12.20.0/#files |
| OpenCC Python reimplementation | 0.1.7 | Apache-2.0 | https://pypi.org/project/opencc-python-reimplemented/0.1.7/#files |
| certifi | 2026.10.23 | MPL-2.0 | https://pypi.org/project/certifi/2026.10.23/#files |
| whisper.cpp / ggml | vendored source in matching TJKSub tag | MIT and included component licenses | https://github.com/konata91008/KonataWhisperGUI-Public/tree/main/whisper.cpp |
| FFmpeg | 9.0.2 | LGPL-2.1-or-later; no GPL/nonfree components enabled | `ffmpeg-9.0.2.tar.xz` attached to the same GitHub release |
| Vulkan loader (Windows) | SDK 1.4.363.0 | Apache-2.0 | https://github.com/KhronosGroup/Vulkan-Loader/tree/vulkan-sdk-1.4.363.0 |
| PyInstaller bootloader | 6.22.3 | GPL with bootloader exception | https://github.com/pyinstaller/pyinstaller/tree/v6.22.3 |

License texts supplied with these packages are copied into this `licenses` folder.
The bundled FFmpeg is a separate command-line executable, compiled from the exact
source archive attached to this release. Its configuration is recorded in
`packaging/build_ffmpeg.sh`; there are no FFmpeg source modifications.

Qt libraries are dynamically loaded and can be replaced by compatible versions.
No application restriction is imposed on debugging such modifications or on the
rights granted by the component licenses. Application binaries are not DRM protected.
Models are downloaded separately from ggerganov/whisper.cpp on Hugging Face;
OpenAI Whisper models are subject to their own upstream license.
