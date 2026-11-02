"""Exercise the real application's FFmpeg -> whisper -> SRT/TXT export pipeline."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'WhisperGUI'))
from core.tasks import transcription_task
from core.translations import TRANSLATIONS
from core.subtitle_ai import parse_srt
from core.network import ssl_context

MODEL_SHA256 = 'be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21'


class Signal:
    def __init__(self): self.calls = []
    def emit(self, *args): self.calls.append(args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', type=Path, default=ROOT / 'build/native')
    parser.add_argument('--require-gpu', action='store_true')
    args = parser.parse_args()
    native = args.native.resolve()
    suffix = '.exe' if os.name == 'nt' else ''
    model = ROOT / 'build/downloads/ggml-tiny.bin'
    model.parent.mkdir(parents=True, exist_ok=True)
    if not model.exists():
        with urllib.request.urlopen('https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin',
                                    context=ssl_context(), timeout=120) as response, model.open('wb') as output:
            shutil.copyfileobj(response, output)
    if hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA256:
        raise RuntimeError('Test model checksum mismatch')
    runtime = json.loads((native / 'runtime.json').read_text())
    runtime.update(path=str(native / ('whisper-cli' + suffix)), ffmpeg=str(native / ('ffmpeg' + suffix)),
                   runtime_bins=[str(native)], device_env={})
    os.environ['PATH'] = str(native) + os.pathsep + os.environ['PATH']
    worker = SimpleNamespace(_is_cancelled=False, process=None,
        **{name: Signal() for name in ('progress_update', 'file_finished', 'file_result',
           'all_finished', 'log_message_received', 'subtitle_line_received')})
    with tempfile.TemporaryDirectory(prefix='tjksub-transcription-') as temp:
        folder = Path(temp) / '模型與暫存 with spaces'
        folder.mkdir()
        (folder / 'models').mkdir()
        shutil.copy2(model, folder / 'models/ggml-tiny.bin')
        audio = folder / '語音 sample.mp3'
        shutil.copy2(ROOT / 'whisper.cpp/samples/jfk.mp3', audio)
        output = folder / '字幕 outputs'
        output.mkdir()
        transcription_task(worker, SimpleNamespace(translations=TRANSLATIONS['en']), [str(audio)],
                           str(output), 'tiny', 'en', runtime['backend'] if args.require_gpu else 'CPU',
                           '', True, True, runtime['path'], str(folder), str(folder),
                           gpu_runtime=runtime if args.require_gpu else None)
        log = '\n'.join(call[0] for call in worker.log_message_received.calls)
        report_name = 'gpu-transcription' if args.require_gpu else 'cpu-transcription'
        (ROOT / 'build' / (report_name + '.log')).write_text(log, encoding='utf-8')
        assert worker.file_result.calls and worker.file_result.calls[0][0]['success'], log[-4000:]
        subtitles = list(output.glob('*.srt'))
        transcripts = list(output.glob('*.txt'))
        assert len(subtitles) == len(transcripts) == 1
        cues = parse_srt(subtitles[0].read_text(encoding='utf-8-sig'))
        assert 'country' in transcripts[0].read_text(encoding='utf-8-sig').lower()
        report = {'ok': True, 'mode': runtime['backend'] if args.require_gpu else 'CPU (CI smoke only)',
                  'cues': len(cues), 'unicode_paths': True, 'srt': True, 'txt': True,
                  'model_sha256': MODEL_SHA256}
        (ROOT / 'build' / (report_name + '.json')).write_text(json.dumps(report, indent=2))
        print(json.dumps(report))


if __name__ == '__main__':
    main()
