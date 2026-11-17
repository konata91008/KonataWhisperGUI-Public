TJKSub v4.15.0 — Windows / macOS

Windows 10 version 1903 or later / Windows 11 x64: run the setup.exe installer. No administrator permission is required.
A portable ZIP is also available: extract the entire folder before running TJKSub.exe.
Do not copy the EXE without its _internal directory.

macOS: download the DMG matching your Mac (arm64 = Apple Silicon, x86_64 = Intel),
then drag TJKSub.app to Applications. macOS 12 or later is required.
A ZIP alternative contains the same application.

These community builds are not signed by an Apple Developer ID / Windows publisher
certificate and have not been Apple-notarized. The OS may warn or block first launch.
Only approve a package after confirming its official GitHub source and checksum.
On macOS, use System Settings > Privacy & Security > Open Anyway when macOS offers
that option for this downloaded app. Do not disable Gatekeeper or antivirus globally.

Python, Qt, the transcription engine, and FFmpeg are bundled. Traditional/Simplified
conversion and subtitle diagnostics work offline immediately. Transcription requires
one initial model download, then runs locally. macOS uses Metal; Windows uses Vulkan
and requires a compatible graphics driver from the hardware vendor. GPU initialization
failure stops transcription rather than silently switching to CPU.

Models:
  Windows: %LOCALAPPDATA%\TJKSub\models
  macOS: ~/Library/Application Support/TJKSub/models
API keys are never persisted. Cross-language API translation is optional and sends
text only after you press Translate. Provider fees and policies apply.

Updates (v4.15.0 and later): Settings > Check GitHub updates compares stable releases,
shows release notes, downloads the matching package and verifies SHA-256. Downloads
can be cancelled. The file is verified again before opening it. No GitHub login is required.
Windows installed copies open the visible installer at the current install location,
then close TJKSub. Portable copies download the full ZIP and show its folder; extract
it to a new location after closing the app. Do not replace just the EXE.
Mac copies open the matching DMG, then close TJKSub. Drag the app to Applications,
choose Replace, then launch it. Automatic app-bundle replacement is not implemented.
Finish running tasks and export any unsaved subtitles before continuing. Models and
saved settings are retained; unexported edits and API keys are not retained across restart.
Downloads are stored in the updates folder alongside your models folder.
Older versions need one manual installation of v4.15.0 or later to get this feature.
Uninstalling the app does not delete downloaded models; remove the model directory
yourself if no longer needed. Source Git installations keep their separate Git updater.

License: GPL-3.0-or-later. Component notices are included under licenses.
Official downloads/source: https://github.com/konata91008/KonataWhisperGUI-Public
