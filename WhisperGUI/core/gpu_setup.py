"""Local GPU setup. Detection is read-only; installation only follows an explicit UI action.

CUDA uses the device-reported compute capability and nvcc's supported targets.
Vulkan/Metal compile their shaders for the device through its driver at runtime.
No CPU build or automatic CPU fallback is offered by this module.
"""
import csv
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


class SetupError(RuntimeError):
    pass


def host_key():
    return platform.system(), platform.machine().lower()


def capture(args, env=None, timeout=25):
    try:
        p = subprocess.run([str(x) for x in args], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout, env=env,
                           creationflags=0x08000000 if os.name == 'nt' else 0)
        return p.stdout.strip() if p.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def refreshed_env():
    env = os.environ.copy()
    if os.name == 'nt':
        import winreg
        paths = [env.get('PATH', '')]
        for hive, key in [(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
                          (winreg.HKEY_CURRENT_USER, r'Environment')]:
            try:
                with winreg.OpenKey(hive, key) as reg:
                    for i in range(winreg.QueryInfoKey(reg)[1]):
                        name, value, _ = winreg.EnumValue(reg, i)
                        if name.upper() == 'PATH':
                            paths.append(os.path.expandvars(value))
                        elif name.upper() in ('CUDA_PATH', 'VULKAN_SDK'):
                            env[name.upper()] = os.path.expandvars(value)
            except OSError:
                pass
        env['PATH'] = os.pathsep.join(paths)
    return env


@dataclass
class GPU:
    name: str
    backend: str
    identity: str = ''
    cc: str = ''
    driver: str = ''
    detail: str = ''
    blocked: str = ''

    @property
    def architecture(self):
        families = {'50': 'Maxwell', '52': 'Maxwell', '53': 'Maxwell',
                    '60': 'Pascal', '61': 'Pascal', '62': 'Pascal',
                    '70': 'Volta', '72': 'Volta', '75': 'Turing',
                    '80': 'Ampere', '86': 'Ampere', '87': 'Ampere',
                    '89': 'Ada Lovelace', '90': 'Hopper', '100': 'Blackwell',
                    '103': 'Blackwell', '120': 'Blackwell', '121': 'Blackwell'}
        if self.backend == 'cuda':
            return f"{families.get(self.cc, '裝置回報架構')} / sm_{self.cc}" if self.cc else '架構尚未確認'
        return 'Metal · 依裝置編譯著色器' if self.backend == 'metal' else 'Vulkan · 依裝置編譯著色器'


@dataclass
class Scan:
    system: str
    machine: str
    gpus: list = field(default_factory=list)
    tools: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def parse_nvidia(text):
    result = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) != 5:
            continue
        index, identity, name, capability, driver = (s.strip() for s in row)
        if not re.fullmatch(r'\d+\.\d', capability) or not identity.startswith('GPU-'):
            continue
        cc = capability.replace('.', '')
        result.append(GPU(name, 'cuda', identity, cc, driver,
                          blocked='此架構早於 Maxwell；目前安裝流程不支援。' if int(cc) < 50 else ''))
    return result


def parse_vulkan(text):
    result = []
    for match in re.finditer(r'GPU(\d+):\s*\n(.*?)(?=\nGPU\d+:|\Z)', text, re.S):
        fields = dict(re.findall(r'^\s*(\w+)\s*=\s*(.*?)\s*$', match[2], re.M))
        if fields.get('deviceType') not in ('PHYSICAL_DEVICE_TYPE_DISCRETE_GPU', 'PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU'):
            continue
        name = fields.get('deviceName', '')
        if not name:
            continue
        result.append(GPU(name, 'vulkan', match[1], driver=fields.get('driverInfo', ''),
                          detail=f"Vulkan {fields.get('apiVersion', '?')} / {fields.get('driverName', '')}"))
    return result


def default_metal_device():
    # Ask Metal itself, rather than assuming the first System Profiler adapter is used.
    import ctypes
    try:
        metal = ctypes.CDLL('/System/Library/Frameworks/Metal.framework/Metal')
        objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
        metal.MTLCreateSystemDefaultDevice.restype = ctypes.c_void_p
        device = metal.MTLCreateSystemDefaultDevice()
        if not device: return ''
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        objc.objc_msgSend.restype = ctypes.c_void_p
        name = objc.objc_msgSend(device, objc.sel_registerName(b'name'))
        objc.objc_msgSend.restype = ctypes.c_char_p
        return objc.objc_msgSend(name, objc.sel_registerName(b'UTF8String')).decode('utf-8')
    except (OSError, AttributeError, ValueError):
        return ''


def scan_host():
    system, machine = host_key()
    scan = Scan(system, machine)
    env = refreshed_env()
    which = lambda name: shutil.which(name, path=env.get('PATH'))
    scan.tools['env'] = env
    # A venv-local CMake is preferred; never install into the global Python.
    local_cmake = Path(sys.executable).parent / ('cmake.exe' if system == 'Windows' else 'cmake')
    scan.tools['cmake'] = str(local_cmake) if local_cmake.is_file() else which('cmake')
    scan.tools['ffmpeg'] = which('ffmpeg')
    if system == 'Darwin':
        scan.tools['clang'] = capture(['xcrun', '--find', 'clang'])
        scan.tools['brew'] = which('brew') or next((p for p in ['/opt/homebrew/bin/brew', '/usr/local/bin/brew'] if Path(p).is_file()), None)
        name = default_metal_device()
        if name:
            scan.gpus.append(GPU(name, 'metal', 'system-default', detail='Metal 已回報系統預設 GPU；多顯卡 Mac 由系統選擇。'))
        else:
            scan.notes.append('Metal 未回報可用顯卡；請檢查 macOS、顯卡及遠端桌面環境。')
        if machine not in ('arm64', 'x86_64'):
            scan.notes.append('目前僅支援原生 Apple Silicon 或 Intel macOS。')
    elif system == 'Windows':
        scan.tools['winget'] = which('winget')
        pf = Path(env.get('ProgramFiles', r'C:\Program Files'))
        pf86 = Path(env.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))
        vswhere = pf86 / 'Microsoft Visual Studio/Installer/vswhere.exe'
        scan.tools['vs_any'] = capture([vswhere, '-latest', '-products', '*', '-version', '[17.0,18.0)', '-property', 'installationPath']) if vswhere.is_file() else ''
        scan.tools['vs_product'] = capture([vswhere, '-latest', '-products', '*', '-version', '[17.0,18.0)', '-property', 'productId']) if vswhere.is_file() else ''
        scan.tools['vs_installer'] = str(vswhere.parent / 'setup.exe')
        scan.tools['windows_sdk'] = any((pf86 / 'Windows Kits/10/Lib').glob('*/um/x64/kernel32.lib'))
        scan.tools['vs'] = capture([vswhere, '-latest', '-products', '*', '-version', '[17.0,18.0)',
                                    '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                    '-property', 'installationPath']) if vswhere.is_file() else ''
        smi = which('nvidia-smi') or str(Path(env.get('SystemRoot', r'C:\Windows')) / 'System32/nvidia-smi.exe')
        scan.gpus.extend(parse_nvidia(capture([smi, '--query-gpu=index,uuid,name,compute_cap,driver_version', '--format=csv,noheader'])))
        cuda_roots = list((pf / 'NVIDIA GPU Computing Toolkit/CUDA').glob('v*'))
        if env.get('CUDA_PATH'):
            cuda_roots.append(Path(env['CUDA_PATH']))
        scan.tools['cuda'] = []
        for root in sorted(set(cuda_roots), reverse=True):
            nvcc = root / 'bin/nvcc.exe'
            if nvcc.is_file():
                targets = re.findall(r'\bsm_(\d+)\b', capture([nvcc, '--list-gpu-code']))
                version = capture([nvcc, '--version'])
                scan.tools['cuda'].append({'root': str(root), 'targets': targets, 'version': version})
        sdk_roots = list(Path(env.get('SystemDrive', 'C:') + '/VulkanSDK').glob('*'))
        if env.get('VULKAN_SDK'):
            sdk_roots.insert(0, Path(env['VULKAN_SDK']))
        sdk = next((p for p in sdk_roots if (p / 'Bin/glslc.exe').is_file()), None)
        scan.tools['vulkan_sdk'] = str(sdk) if sdk else ''
        info = which('vulkaninfo') or (str(sdk / 'Bin/vulkaninfo.exe') if sdk else None)
        if info:
            scan.gpus.extend(parse_vulkan(capture([info, '--summary'])))
        # WMI names are inventory, never used to guess CUDA compute capability.
        raw = capture(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                       '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); '
                       '@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion) | ConvertTo-Json -Compress'])
        try:
            adapters = json.loads(raw)
            if isinstance(adapters, dict): adapters = [adapters]
            for adapter in adapters:
                name = adapter.get('Name', '')
                if not name or any(g.name == name for g in scan.gpus): continue
                if 'nvidia' in name.lower():
                    scan.gpus.append(GPU(name, 'cuda', blocked='無法讀取 CUDA Compute Capability；請安裝／更新 NVIDIA 驅動後重新偵測。'))
                elif any(x in name.lower() for x in ('amd', 'radeon', 'intel')):
                    scan.gpus.append(GPU(name, 'vulkan', detail='安裝 Vulkan SDK 後驗證裝置；不依名稱猜測支援。'))
                else:
                    scan.notes.append(f'{name}：未找到可驗證的 GPU 後端。')
        except (ValueError, TypeError):
            scan.notes.append('Windows 顯卡清單讀取失敗；請確認顯示卡驅動已安裝。')
        if machine not in ('amd64', 'x86_64'):
            scan.notes.append('Windows 安裝流程目前支援 x64；不支援 ARM64 或 32 位元。')
    else:
        scan.notes.append('本次安裝流程僅支援 macOS 與 Windows。')
    return scan


def cuda_toolkit(scan, gpu):
    for item in scan.tools.get('cuda', []):
        if gpu.cc in item['targets']:
            return item
    return None


def cuda_package_version(gpu):
    # 12.9 retains Maxwell/Pascal/Volta and includes RTX 50 (sm_120).
    return '12.9' if int(gpu.cc) <= 100 or gpu.cc in ('101', '120') else '13.4'


def missing_tools(scan, gpu):
    missing = []
    cmake = scan.tools.get('cmake')
    version = capture([cmake, '--version']) if cmake else ''
    m = re.search(r'version (\d+)\.(\d+)\.(\d+)', version)
    if not m or not ((3, 31, 8) <= tuple(map(int, m.groups())) < (4, 0, 0)):
        missing.append('CMake 3.31（此程式的 Python 環境）')
    if scan.system == 'Darwin':
        if not scan.tools.get('clang'): missing.append('Apple Command Line Tools')
    elif scan.system == 'Windows':
        if not scan.tools.get('vs') or not scan.tools.get('windows_sdk'): missing.append('Visual Studio 2022 C++ Build Tools / Windows SDK')
        if gpu.backend == 'cuda' and not cuda_toolkit(scan, gpu):
            missing.append('CUDA Toolkit ' + cuda_package_version(gpu))
        if gpu.backend == 'vulkan' and not scan.tools.get('vulkan_sdk'):
            missing.append('Vulkan SDK')
    if not scan.tools.get('ffmpeg'): missing.append('FFmpeg（影片轉音訊）')
    return missing


def run_logged(args, log, env=None, cwd=None, timeout=3600):
    """No shell interpolation. Keep installers' UAC/license UI visible."""
    log('> ' + subprocess.list2cmdline([str(x) for x in args]))
    # File-backed logs avoid a pipe deadlock and keep long compiler output bounded.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='tjksub-build-') as temp:
      with open(Path(temp) / 'process.log', 'w+b') as writer, open(Path(temp) / 'process.log', 'rb') as output:
        process = subprocess.Popen([str(x) for x in args], stdout=writer, stderr=subprocess.STDOUT,
                                   env=env, cwd=cwd, start_new_session=os.name != 'nt')
        start, position = time.monotonic(), 0
        while True:
            output.seek(position)
            chunk = output.read()
            position = output.tell()
            if chunk: log(chunk.decode('utf-8', errors='replace').rstrip())
            if process.poll() is not None:
                output.seek(position)
                tail = output.read()
                if tail: log(tail.decode('utf-8', errors='replace').rstrip())
                break
            if timeout and time.monotonic() - start > timeout:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    import signal
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait()
                raise SetupError('編譯逾時；保留原本的引擎，請檢查記錄後重試。')
            time.sleep(.15)
        if process.returncode != 0:
            raise SetupError(f'工具結束代碼 {process.returncode}。若安裝程式要求重開機，請先重開機再重新偵測。詳細原因請看上方記錄。')


def install_tools(scan, gpu, log, runner=run_logged):
    missing = missing_tools(scan, gpu)
    env = scan.tools.get('env') or refreshed_env()
    if any(x.startswith('CMake') for x in missing):
        if sys.prefix == sys.base_prefix:
            raise SetupError('請從 start_mac.command 或 Start_Windows.bat 啟動，才能將 CMake 安裝在程式專用 venv。')
        runner([sys.executable, '-m', 'pip', 'install', 'cmake>=3.31.8,<4'], log, env=env)
    if scan.system == 'Darwin':
        if 'Apple Command Line Tools' in missing:
            runner(['xcode-select', '--install'], log, env=env)
            raise SetupError('已開啟 Apple 安裝視窗；完成後按「重新偵測」再編譯。')
        if any(x.startswith('FFmpeg') for x in missing):
            brew = scan.tools.get('brew')
            if not brew: raise SetupError('缺少 FFmpeg。請先依 https://ffmpeg.org/download.html 安裝，或安裝 Homebrew 後重新偵測。')
            runner([brew, 'install', 'ffmpeg'], log, env=env, timeout=None)
    else:
        packages = []
        if any(x.startswith('Visual Studio') for x in missing) and scan.tools.get('vs_any'):
            runner([scan.tools['vs_installer'], 'modify', '--installPath', scan.tools['vs_any'],
                    '--add', ('Microsoft.VisualStudio.Workload.VCTools' if 'buildtools' in scan.tools.get('vs_product', '').lower() else 'Microsoft.VisualStudio.Workload.NativeDesktop'), '--includeRecommended',
                    '--passive', '--norestart'], log, env=env, timeout=None)
        elif any(x.startswith('Visual Studio') for x in missing):
            packages.append(('Microsoft.VisualStudio.2022.BuildTools', ['--override', '--wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended']))
        if any(x.startswith('CUDA Toolkit') for x in missing):
            packages.append(('Nvidia.CUDA', ['--version', cuda_package_version(gpu)]))
        if 'Vulkan SDK' in missing: packages.append(('KhronosGroup.VulkanSDK', []))
        if any(x.startswith('FFmpeg') for x in missing): packages.append(('Gyan.FFmpeg', []))
        if packages and not scan.tools.get('winget'):
            raise SetupError('缺少 Windows App Installer（winget）；請先從 Microsoft Store 安裝「應用程式安裝程式」，再重試。')
        for package, extra in packages:
            # Source/package terms are displayed in the plan before this user-initiated action.
            runner([scan.tools['winget'], 'install', '--id', package, '--exact', '--source', 'winget',
                    '--interactive', '--accept-source-agreements', '--accept-package-agreements'] + extra,
                   log, env=env, timeout=None)


def validate_selection(scan, gpu):
    if scan.system not in ('Windows', 'Darwin'):
        raise SetupError('此安裝流程僅支援 macOS 與 Windows。')
    if (scan.system == 'Windows' and scan.machine not in ('amd64', 'x86_64')) or (scan.system == 'Darwin' and scan.machine not in ('arm64', 'x86_64')):
        raise SetupError('目前不支援此作業系統架構。')
    if gpu.blocked: raise SetupError(gpu.blocked)
    if gpu.backend not in (('metal',) if scan.system == 'Darwin' else ('cuda', 'vulkan')):
        raise SetupError('顯卡後端與作業系統不相容。')
    if gpu.backend == 'cuda' and not re.fullmatch(r'\d{2,3}', gpu.cc):
        raise SetupError('必須先讀取顯卡實際回報的 CUDA 架構。')


def cmake_command(source, build, scan, gpu):
    validate_selection(scan, gpu)
    cmd = [scan.tools['cmake'], '-S', str(source), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release',
           '-DBUILD_SHARED_LIBS=OFF', '-DGGML_BACKEND_DL=OFF', '-DWHISPER_BUILD_TESTS=OFF',
           '-DWHISPER_BUILD_SERVER=OFF', '-DWHISPER_BUILD_EXAMPLES=ON',
           '-DWHISPER_COREML=OFF', '-DWHISPER_OPENVINO=OFF']
    for backend in ('cuda', 'metal', 'vulkan'):
        cmd.append(f'-DGGML_{backend.upper()}={"ON" if gpu.backend == backend else "OFF"}')
    if scan.system == 'Windows':
        cmd += ['-G', 'Visual Studio 17 2022', '-A', 'x64', '-DCMAKE_GENERATOR_INSTANCE=' + scan.tools['vs']]
    else:
        cmd += ['-DCMAKE_OSX_ARCHITECTURES=' + scan.machine, '-DGGML_METAL_EMBED_LIBRARY=ON']
    if gpu.backend == 'cuda':
        kit = cuda_toolkit(scan, gpu)
        if not kit: raise SetupError(f'找不到可編譯 sm_{gpu.cc} 的 nvcc，請安裝相容 CUDA Toolkit。')
        cmd += ['-T', 'cuda=' + kit['root'], '-DCUDAToolkit_ROOT=' + kit['root'],
                '-DCMAKE_CUDA_ARCHITECTURES=' + gpu.cc]
    if gpu.backend == 'vulkan':
        cmd += ['-DCMAKE_PREFIX_PATH=' + scan.tools['vulkan_sdk']]
    return cmd


def runtime_file(root):
    return Path(root) / 'whisper.cpp/build/tjksub-runtime.json'


def load_runtime(root):
    try:
        data = json.loads(runtime_file(root).read_text(encoding='utf-8'))
        if data.get('schema') != 1 or not isinstance(data['gpu']['name'], str): return None
        if not isinstance(data.get('runtime_bins'), list) or not all(isinstance(p, str) for p in data['runtime_bins']): return None
        if not isinstance(data.get('device_env'), dict) or not set(data['device_env']).issubset({'CUDA_VISIBLE_DEVICES', 'GGML_VK_VISIBLE_DEVICES'}): return None
        if not all(isinstance(v, str) for v in data['device_env'].values()): return None
        if (data['system'], data['machine']) != host_key() or data['backend'] not in ('cuda', 'metal', 'vulkan'):
            return None
        exe = (Path(root) / data['executable']).resolve()
        exe.relative_to((Path(root) / 'whisper.cpp/build/tjksub').resolve())
        if not exe.is_file(): return None
        data['path'] = str(exe)
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def runtime_env(runtime):
    env = refreshed_env()
    for name in ('CUDA_VISIBLE_DEVICES', 'GGML_VK_VISIBLE_DEVICES', 'WHISPER_ARG_DEVICE'):
        env.pop(name, None)
    env.update(runtime.get('device_env', {}))
    bins = runtime.get('runtime_bins', [])
    env['PATH'] = os.pathsep.join(bins + [env.get('PATH', '')])
    return env


def build_gpu(root, scan, gpu, log, install=False, runner=run_logged, scanner=scan_host):
    validate_selection(scan, gpu)
    root = Path(root).resolve()
    source = root / 'whisper.cpp'
    if not (source / 'CMakeLists.txt').is_file() or not (source / 'ggml/CMakeLists.txt').is_file():
        raise SetupError('缺少完整 whisper.cpp 原始碼。請將這份更新套用到原專案，不能單獨執行 GUI 更新壓縮檔。')
    if install:
        install_tools(scan, gpu, log, runner)
        fresh = scanner()
        candidates = [g for g in fresh.gpus if g.backend == gpu.backend and g.name == gpu.name
                      and (not gpu.identity or g.identity == gpu.identity)]
        if len(candidates) != 1: raise SetupError('安裝後顯卡清單有變，請重新偵測並選取要使用的顯卡。')
        scan, gpu = fresh, candidates[0]
    validate_selection(scan, gpu)
    missing = missing_tools(scan, gpu)
    if missing: raise SetupError('仍缺少：' + '、'.join(missing) + '。請完成安裝／重開機後重新偵測。')
    if gpu.backend == 'vulkan' and not gpu.identity:
        raise SetupError('Vulkan 驅動未回報這張顯卡；請更新原廠驅動後重新偵測。不會改用 CPU。')
    suffix = '-sm' + gpu.cc if gpu.backend == 'cuda' else ''
    build = source / 'build/tjksub' / (f'{scan.system.lower()}-{scan.machine}-{gpu.backend}{suffix}-' + uuid.uuid4().hex[:8])
    build.mkdir(parents=True)
    env = dict(scan.tools.get('env') or refreshed_env())
    bins, device_env = [], {}
    if gpu.backend == 'cuda':
        kit = cuda_toolkit(scan, gpu)
        bins.append(str(Path(kit['root']) / 'bin'))
        device_env['CUDA_VISIBLE_DEVICES'] = gpu.identity
    elif gpu.backend == 'vulkan':
        env['VULKAN_SDK'] = scan.tools['vulkan_sdk']
        device_env['GGML_VK_VISIBLE_DEVICES'] = gpu.identity
    if scan.tools.get('ffmpeg'): bins.append(str(Path(scan.tools['ffmpeg']).parent))
    env['PATH'] = os.pathsep.join(bins + [env.get('PATH', '')])
    env.update(device_env)
    command = cmake_command(source, build, scan, gpu)
    runner(command, log, env=env)
    runner([scan.tools['cmake'], '--build', str(build), '--config', 'Release', '--target', 'whisper-cli',
            '--parallel', str(min(os.cpu_count() or 2, 8))], log, env=env)
    candidates = [build / 'bin/Release/whisper-cli.exe', build / 'bin/whisper-cli.exe'] if scan.system == 'Windows' else [build / 'bin/whisper-cli']
    exe = next((p for p in candidates if p.is_file()), None)
    if not exe: raise SetupError('編譯結束但找不到 whisper-cli；保留原本的引擎。')
    runner([str(exe), '--help'], log, env=env, cwd=str(exe.parent), timeout=30)
    data = {'schema': 1, 'system': scan.system, 'machine': scan.machine, 'backend': gpu.backend,
            'gpu': asdict(gpu), 'executable': str(exe.relative_to(root)), 'runtime_bins': bins,
            'device_env': device_env, 'built_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'configure': command, 'verification': 'compiled-and-launchable'}
    destination = runtime_file(root)
    temporary = destination.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, destination)
    log('GPU 引擎編譯與啟動檢查完成。首次轉錄會再次確認 GPU 初始化；若失敗就停止，不會以 CPU 繼續。')
    return data


def gpu_log_state(line, backend):
    """The bundled whisper.cpp exposes backend selection in startup logs; fail closed."""
    lower = line.lower()
    if 'whisper_backend_init_gpu:' in lower:
        if 'no gpu found' in lower or 'failed to initialize' in lower: return 'failed'
        if re.search(r'using\s+' + re.escape(backend) + r'\d*\s+backend', lower): return 'selected'
    return None
