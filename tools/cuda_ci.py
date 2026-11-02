"""Verify a real CUDA build on a GPU-less Windows runner without fake drivers."""
import os
from pathlib import Path
import re
import subprocess


class DriverUnavailable(RuntimeError):
    def __init__(self, executable, evidence):
        super().__init__('CUDA compiled; launch requires the absent NVIDIA display driver')
        self.executable = str(executable)
        self.evidence = evidence


def imported_dlls(output):
    # dumpbin /DEPENDENTS lists one DLL per line (including delay-load imports).
    return sorted(set(re.findall(r'^\s*([\w.+-]+\.dll)\s*$', output, re.M | re.I)), key=str.lower)


def check_dependencies(executable, cuda_dirs, vs_root, env):
    tools = Path(vs_root) / 'VC/Tools/MSVC'
    dumpbin = next(iter(sorted(tools.glob('*/bin/Hostx64/x64/dumpbin.exe'), reverse=True)), None)
    if not dumpbin:
        raise RuntimeError('Cannot inspect CUDA executable dependencies: dumpbin is missing')
    system = Path(env.get('SystemRoot') or env.get('SYSTEMROOT', 'C:/Windows')) / 'System32'
    folders = [Path(executable).parent, *map(Path, cuda_dirs), system]
    folders.extend(Path(p) for p in env.get('PATH', '').split(os.pathsep) if p)
    pending, inspected, missing = [Path(executable)], {}, set()
    while pending:
        binary = pending.pop()
        if str(binary).lower() in inspected:
            continue
        result = subprocess.run([str(dumpbin), '/DEPENDENTS', str(binary)], env=env,
                                capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        imports = imported_dlls(result.stdout)
        if not imports:
            raise RuntimeError(f'No PE imports found for {binary}; refusing to assume the build is valid')
        inspected[str(binary).lower()] = imports
        for name in imports:
            if name.lower().startswith(('api-ms-', 'ext-ms-')):
                continue  # Windows API-set contracts are resolved by the OS loader.
            location = next((folder / name for folder in folders if (folder / name).is_file()), None)
            if location is None:
                missing.add(name.lower())
            elif any(location.resolve().is_relative_to(Path(d).resolve()) for d in cuda_dirs):
                pending.append(location)
    return {'imports': inspected, 'missing': sorted(missing)}


def probe_cuda_launch(args, log, cuda_dirs, vs_root, **kwargs):
    log('> ' + subprocess.list2cmdline(args))
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace',
                            **{k: v for k, v in kwargs.items() if k in ('env', 'cwd', 'timeout')})
    if result.stdout: log(result.stdout)
    if result.stderr: log(result.stderr)
    if result.returncode == 0:
        return
    if result.returncode & 0xFFFFFFFF == 0xC0000135:
        evidence = check_dependencies(args[0], cuda_dirs, vs_root, kwargs['env'])
        log('CUDA PE dependency check: ' + str(evidence))
        if evidence['missing'] == ['nvcuda.dll']:
            raise DriverUnavailable(args[0], evidence)
    raise RuntimeError(f'CUDA launch failed with exit code {result.returncode}; not an isolated missing NVIDIA driver')
