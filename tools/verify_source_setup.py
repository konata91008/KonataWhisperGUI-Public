"""Exercise the source install/build path. CI fixtures never claim GPU execution."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'WhisperGUI'))
from core.gpu_setup import GPU, build_gpu, install_tools, scan_host, runtime_env, run_logged, cuda_toolkit, cuda_binary_dirs
from cuda_ci import DriverUnavailable, probe_cuda_launch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['cuda', 'metal', 'vulkan'], required=True)
    parser.add_argument('--install-tools', action='store_true')
    parser.add_argument('--ci-cuda-cc', choices=['61', '86', '120', '121'])
    parser.add_argument('--ci-install-vs', action='store_true')
    parser.add_argument('--ci-compile-only', action='store_true')
    args = parser.parse_args()
    if args.ci_install_vs and not args.ci_cuda_cc:
        parser.error('--ci-install-vs requires the CUDA CI fixture')
    ci_fixture = bool(args.ci_cuda_cc or args.ci_compile_only)
    if ci_fixture and os.environ.get('GITHUB_ACTIONS') != 'true':
        parser.error('Compiler-only fixtures are restricted to GitHub Actions')
    if args.ci_cuda_cc and args.backend != 'cuda':
        parser.error('--ci-cuda-cc is only a GPU-less GitHub Actions compiler test')
    scan = scan_host()
    if args.ci_cuda_cc:
        gpu = GPU('CI compiler target (no physical GPU)', 'cuda', 'GPU-ci-no-device', args.ci_cuda_cc)
        # Force the fresh-install path on ephemeral CI, even if a runner ships CUDA.
        scan.tools['cuda'] = []
        scan.tools['cmake'] = None
        scan.tools['ffmpeg'] = None
        if args.ci_install_vs:
            scan.tools.update(vs='', vs_any='', windows_sdk=False)
    elif args.ci_compile_only:
        if args.backend == 'cuda':
            parser.error('CUDA compiler tests require --ci-cuda-cc')
        gpu = GPU('CI compiler target (no physical GPU)', args.backend,
                  'system-default' if args.backend == 'metal' else '0')
        scan.tools['cmake'] = None
        if args.backend == 'vulkan':
            scan.tools['vulkan_sdk'] = ''
            scan.tools['ffmpeg'] = None
    else:
        devices = [g for g in scan.gpus if g.backend == args.backend and not g.blocked]
        if not devices: raise RuntimeError('No verified GPU available for requested backend')
        gpu = devices[0]
    logpath = ROOT / 'build/source-setup.log'
    logpath.parent.mkdir(exist_ok=True)
    with logpath.open('w', encoding='utf-8') as output:
        def log(message):
            print(message, flush=True); output.write(message + '\n'); output.flush()
        if args.install_tools:
            install_tools(scan, gpu, log, unattended=ci_fixture)
            scan = scan_host()
        def runner(command, logger, **kwargs):
            if args.ci_cuda_cc and command[-1:] == ['--help']:
                kit = cuda_toolkit(scan, gpu)
                return probe_cuda_launch(command, logger, cuda_binary_dirs(kit['root']), scan.tools['vs'], **kwargs)
            return run_logged(command, logger, **kwargs)
        try:
            runtime = build_gpu(ROOT, scan, gpu, log, runner=runner)
        except DriverUnavailable as exc:
            # build_gpu deliberately does not activate an engine that cannot launch.
            # Verify actual PE imports instead of supplying a fake driver/GPU.
            report = {'ok': True, 'backend': 'cuda', 'compute_capability': gpu.cc,
                      'compiled': True, 'launchable': False, 'gpu_execution_verified': False,
                      'install_requested': args.install_tools, 'exports_tested': False,
                      'launch_blocked_by': 'missing NVIDIA display driver (nvcuda.dll)',
                      'dependency_check': exc.evidence,
                      'note': 'Real CUDA compilation and DLL inspection passed; launch/transcription require a Windows NVIDIA machine.'}
            (ROOT / 'build/source-setup.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))
            return
    env = runtime_env(runtime)
    command = [sys.executable, str(ROOT / 'packaging/smoke_transcription.py'), '--source-runtime']
    if not ci_fixture:
        command.append('--require-gpu')
    subprocess.run(command, check=True, env=env)
    report = {'ok': True, 'backend': args.backend, 'compute_capability': gpu.cc,
              'compiled': True, 'launchable': True, 'gpu_execution_verified': not ci_fixture,
              'install_requested': args.install_tools, 'unicode_paths': True,
              'note': 'CI does not verify physical GPU execution; transcription explicitly uses CPU.' if ci_fixture else 'Real GPU transcription passed.'}
    (ROOT / 'build/source-setup.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__': main()
