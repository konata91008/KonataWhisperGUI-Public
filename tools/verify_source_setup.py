"""Exercise the source install/build path. CI fixtures never claim GPU execution."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'WhisperGUI'))
from core.gpu_setup import GPU, build_gpu, install_tools, scan_host, runtime_env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=['cuda', 'metal', 'vulkan'], required=True)
    parser.add_argument('--install-tools', action='store_true')
    parser.add_argument('--ci-cuda-cc', choices=['61', '86', '120', '121'])
    args = parser.parse_args()
    if args.ci_cuda_cc and (os.environ.get('GITHUB_ACTIONS') != 'true' or args.backend != 'cuda'):
        parser.error('--ci-cuda-cc is only a GPU-less GitHub Actions compiler test')
    scan = scan_host()
    if args.ci_cuda_cc:
        gpu = GPU('CI compiler target (no physical GPU)', 'cuda', 'GPU-ci-no-device', args.ci_cuda_cc)
        # Force the fresh-install path on ephemeral CI, even if a runner ships CUDA.
        scan.tools['cuda'] = []
        scan.tools['cmake'] = None
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
            install_tools(scan, gpu, log, unattended=bool(args.ci_cuda_cc))
            scan = scan_host()
        runtime = build_gpu(ROOT, scan, gpu, log)
    env = runtime_env(runtime)
    command = [sys.executable, str(ROOT / 'packaging/smoke_transcription.py'), '--source-runtime']
    if not args.ci_cuda_cc:
        command.append('--require-gpu')
    subprocess.run(command, check=True, env=env)
    report = {'ok': True, 'backend': args.backend, 'compute_capability': gpu.cc,
              'compiled': True, 'launchable': True, 'gpu_execution_verified': not bool(args.ci_cuda_cc),
              'install_requested': args.install_tools, 'unicode_paths': True,
              'note': 'CI has no NVIDIA GPU; transcription explicitly uses CPU.' if args.ci_cuda_cc else 'Real GPU transcription passed.'}
    (ROOT / 'build/source-setup.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__': main()
