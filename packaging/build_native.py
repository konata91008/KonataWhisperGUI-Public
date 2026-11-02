"""Build the vendored engine without changing its source or requiring end-user tools."""
import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from prepare_ffmpeg import prepare
from prepare_vulkan_runtime import prepare as prepare_vulkan_runtime

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ffmpeg-ready', action='store_true')
    args = parser.parse_args()
    native = ROOT / 'build/native'
    native.mkdir(parents=True, exist_ok=True)
    prepare()
    if not args.ffmpeg_ready:
        subprocess.run(['bash', str(ROOT / 'packaging/build_ffmpeg.sh')], check=True)
    windows = platform.system() == 'Windows'
    if windows:
        prepare_vulkan_runtime(native)
    backend = 'vulkan' if windows else 'metal'
    build = ROOT / 'build/whisper'
    command = ['cmake', '-S', str(ROOT / 'whisper.cpp'), '-B', str(build),
        '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF', '-DGGML_NATIVE=OFF',
        '-DGGML_OPENMP=OFF', '-DWHISPER_BUILD_TESTS=OFF', '-DWHISPER_BUILD_SERVER=OFF',
        '-DGGML_CUDA=OFF', '-DGGML_VULKAN=' + ('ON' if windows else 'OFF'),
        '-DGGML_METAL=' + ('OFF' if windows else 'ON'), '-DGGML_METAL_EMBED_LIBRARY=ON']
    if windows:
        command += ['-A', 'x64', '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
                    '-DCMAKE_POLICY_DEFAULT_CMP0091=NEW', '-DGGML_AVX=OFF', '-DGGML_AVX2=OFF',
                    '-DGGML_FMA=OFF', '-DGGML_F16C=OFF']
        # whisper-cli accepts narrow argv and its model loader expects UTF-8.
        # Set the process code page without changing the user's Windows locale.
        manifest = ROOT / 'packaging/windows-runtime.manifest'
        command += [f'-DCMAKE_EXE_LINKER_FLAGS=/MANIFEST:EMBED /MANIFESTINPUT:"{manifest}"']
        if os.environ.get('VULKAN_SDK'):
            command += ['-DCMAKE_PREFIX_PATH=' + os.environ['VULKAN_SDK']]
    else:
        command += ['-DCMAKE_OSX_DEPLOYMENT_TARGET=12.0', '-DGGML_METAL_MACOSX_VERSION_MIN=12.0']
    subprocess.run(command, check=True)
    subprocess.run(['cmake', '--build', str(build), '--config', 'Release', '--target', 'whisper-cli', '--parallel', '4'], check=True)
    executable = build / ('bin/Release/whisper-cli.exe' if windows else 'bin/whisper-cli')
    shutil.copy2(executable, native / executable.name)
    (native / 'runtime.json').write_text(json.dumps({'schema': 1, 'system': platform.system(),
        'machine': platform.machine().lower(), 'backend': backend}, indent=2))
    subprocess.run([str(native / executable.name), '--help'], check=True, cwd=native)


if __name__ == '__main__':
    main()
