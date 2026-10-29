import os
import sys
import time
import subprocess
import tempfile
import shutil
import signal
import re
import urllib.request
from PyQt5.QtCore import QThread, pyqtSignal
from .gpu_setup import runtime_env, gpu_log_state

#
# 這個檔案負責處理所有耗時的背景任務。
#

# --- Worker Thread ---
class WorkerThread(QThread):
    progress_update = pyqtSignal(int, str)
    file_finished = pyqtSignal(str, float)
    file_result = pyqtSignal(dict)
    all_finished = pyqtSignal(float, str)
    download_finished = pyqtSignal(bool)
    log_message_received = pyqtSignal(str)
    subtitle_line_received = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._is_cancelled = False
        self.process = None

    def run(self):
        self.func(self, *self.args, **self.kwargs)

    def cancel(self):
        self._is_cancelled = True
        if self.process and self.process.poll() is None:
            self.log_message_received.emit("\n[正在嘗試終止任務...]")
            try:
                if sys.platform == "win32":
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
                self.log_message_received.emit("[任務已被成功終止]")
            except OSError as e:
                # CREATE_NO_WINDOW may have no console for CTRL_BREAK_EVENT.
                try:
                    self.process.kill()
                    self.process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired) as stop_error:
                    self.log_message_received.emit(f"[終止程序失敗: {stop_error}]")
            except subprocess.TimeoutExpired:
                self.log_message_received.emit("[終止超時，強制結束...]")
                self.process.kill()
            finally:
                 self.log_message_received.emit("[任務已被使用者取消]")


# --- 下載模型的任務 ---
def download_task(worker_thread, main_window, model_name, base_dir):
    models_dir = os.path.join(base_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    model_path = os.path.join(models_dir, f'ggml-{model_name}.bin')
    url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{model_name}.bin"
    
    trans = main_window.translations

    def progress_hook(count, block_size, total_size):
        if worker_thread._is_cancelled:
            raise ValueError("Download cancelled by user.")
        
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            downloaded_mb = count * block_size / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            progress_text = trans['downloading_progress'].format(downloaded=downloaded_mb, total=total_mb)
            worker_thread.progress_update.emit(percent, progress_text)
        else:
            downloaded_mb = count * block_size / (1024 * 1024)
            progress_text = trans['downloading_progress_no_total'].format(downloaded=downloaded_mb)
            worker_thread.progress_update.emit(0, progress_text)


    try:
        urllib.request.urlretrieve(url, model_path, reporthook=progress_hook)
        
        if worker_thread._is_cancelled:
            if os.path.exists(model_path):
                os.remove(model_path)
            worker_thread.download_finished.emit(False)
        else:
            worker_thread.progress_update.emit(100, trans['download_complete'])
            worker_thread.download_finished.emit(True)

    except (urllib.error.URLError, ValueError, Exception) as e:
        print(f"下載模型時發生錯誤: {e}")
        if os.path.exists(model_path):
            os.remove(model_path)
        worker_thread.download_finished.emit(False)


# --- 執行轉錄的任務 ---
def transcription_task(worker_thread, main_window, files, save_dir, model, lang, backend_str, prompt, out_srt, out_txt, exe_path, base_dir, temp_dir, gpu_runtime=None):
    total_start_time = time.time()
    process_env = runtime_env(gpu_runtime) if gpu_runtime else None
    models_dir = os.path.join(base_dir, 'models')
    model_path = os.path.join(models_dir, f'ggml-{model}.bin')
    
    # [修復閃退] macOS 上在多執行緒環境使用 preexec_fn=os.setsid 不是 fork-safe，
    # 有機率導致整個程式在子行程啟動時直接崩潰退出。
    # 改用 start_new_session=True（等效且執行緒安全），mac 優先、Windows 為輔。
    start_new_session = False
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        start_new_session = True
    
    for i, f in enumerate(files):
        if worker_thread._is_cancelled:
            break
        
        progress_val = int((i / len(files)) * 100)
        file_basename = os.path.basename(f)
        
        trans = main_window.translations
        processing_text = trans['processing_file'].format(
            file_name=file_basename, current=i+1, total=len(files)
        )
        worker_thread.progress_update.emit(progress_val, processing_text)

        # 逐檔收集細節，轉錄結束後在結果視窗以分頁呈現
        sub_lines = []
        log_lines = []
        final_outputs = []

        def log(msg):
            log_lines.append(msg)
            worker_thread.log_message_received.emit(msg)

        log(f"--- 開始處理檔案: {file_basename} ---")

        file_start_time = time.time()

        original_ext = os.path.splitext(f)[1]
        temp_input_path = os.path.join(temp_dir, f"temp_input_{i}{original_ext}")
        temp_output_base = os.path.join(temp_dir, f"temp_output_{i}")
        tmp_wav_to_clean = None

        try:
            shutil.copy(f, temp_input_path)
            
            ext = os.path.splitext(temp_input_path)[1].lower()
            input_path_for_whisper = temp_input_path
            
            if ext not in ['.wav', '.mp3', '.ogg', '.flac']:
                fd, tmp_wav = tempfile.mkstemp(suffix='.wav', dir=temp_dir)
                os.close(fd)
                tmp_wav_to_clean = tmp_wav
                ffmpeg_cmd = ['ffmpeg', '-y', '-i', temp_input_path, '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', tmp_wav]
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=creationflags, env=process_env)
                input_path_for_whisper = tmp_wav

            final_output_dir = save_dir if save_dir else os.path.dirname(f)
            
            cmd = [exe_path]
            
            # [修正] 移除 lang != 'auto' 的判斷，讓自動偵測能正常運作
            if lang: 
                cmd.extend(['-l', lang])

            n_threads = str(min(os.cpu_count() or 4, 8))
            cmd.extend(['-t', n_threads])

            if gpu_runtime:
                cmd.extend(['-dev', '0'])
            elif "CPU" in backend_str:
                cmd.append('-ng')
            
            cmd.extend(['-m', model_path, 
                        '-f', input_path_for_whisper, 
                        '-of', temp_output_base])
            
            if prompt: cmd.extend(['--prompt', prompt])
            # Retain a time-coded snapshot for optional AI review, including TXT-only exports.
            cmd.append('-osrt')
            if out_txt: cmd.append('-otxt')

            exe_dir = os.path.dirname(exe_path)
            log(f"[偵錯] 工作目錄: {exe_dir}")
            log(f"[偵錯] 執行指令: {' '.join(cmd)}")
            
            worker_thread.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                start_new_session=start_new_session, creationflags=creationflags,
                cwd=exe_dir, env=process_env
            )
            
            subtitle_pattern = re.compile(r'\[\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]')

            gpu_selected = False
            for line in iter(worker_thread.process.stdout.readline, ''):
                if worker_thread._is_cancelled:
                    break
                clean_line = line.strip()
                if clean_line:
                    if gpu_runtime:
                        state = gpu_log_state(clean_line, gpu_runtime['backend'])
                        if state == 'selected': gpu_selected = True
                        if state == 'failed':
                            worker_thread.process.terminate()
                            try: worker_thread.process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                worker_thread.process.kill()
                                worker_thread.process.wait()
                            raise RuntimeError('GPU 初始化失敗，已停止；不會改用 CPU。' + clean_line)
                    if subtitle_pattern.match(clean_line):
                        sub_lines.append(clean_line)
                        worker_thread.subtitle_line_received.emit(clean_line)
                    else:
                        log(clean_line)
            
            worker_thread.process.wait()
            
            if worker_thread._is_cancelled:
                break

            return_code = worker_thread.process.returncode
            if return_code != 0:
                log(f"[錯誤] whisper.cpp 處理失敗，返回錯誤碼: {return_code}")
                worker_thread.file_result.emit({
                    "file": f, "time": time.time() - file_start_time, "success": False,
                    "subtitles": sub_lines[:], "log": log_lines[:], "outputs": [],
                })
                continue

            if gpu_runtime and not gpu_selected:
                raise RuntimeError('未確認引擎使用指定 GPU，不匯出本次結果。請重新設定顯卡並檢查引擎記錄。')

            # --- 處理檔案移動 ---
            original_base_name = os.path.splitext(file_basename)[0]
            srt_snapshot = ''
            try:
                with open(f'{temp_output_base}.srt', encoding='utf-8-sig') as source:
                    srt_snapshot = source.read()
            except (OSError, UnicodeError):
                log('[AI] 無法讀取字幕時間碼；本次無法使用 AI 優化。')
            output_files = []
            if out_srt: output_files.append(f"{temp_output_base}.srt")
            if out_txt: output_files.append(f"{temp_output_base}.txt")

            for temp_file_path in output_files:
                if os.path.exists(temp_file_path):
                    final_file_path = os.path.join(final_output_dir, os.path.basename(temp_file_path).replace(f"temp_output_{i}", original_base_name))
                    shutil.move(temp_file_path, final_file_path)
                    final_outputs.append(final_file_path)

            file_time = time.time() - file_start_time
            worker_thread.file_finished.emit(f, file_time)
            log(f"--- 檔案處理完畢，耗時: {file_time:.2f} 秒 ---\n")
            worker_thread.file_result.emit({
                "file": f, "time": file_time, "success": True,
                "subtitles": sub_lines[:], "log": log_lines[:], "outputs": final_outputs[:],
                "srt": srt_snapshot, "output_base": os.path.join(final_output_dir, original_base_name),
                "formats": tuple(ext for ext, enabled in [('srt', out_srt), ('txt', out_txt)] if enabled),
            })

        except Exception as e:
            error_msg = f"處理檔案時發生嚴重錯誤: {e}"
            print(error_msg)
            log(error_msg)
            worker_thread.file_result.emit({
                "file": f, "time": time.time() - file_start_time, "success": False,
                "subtitles": sub_lines[:], "log": log_lines[:], "outputs": [],
            })
        
        finally:
             worker_thread.process = None
             paths_to_clean = [
                 temp_input_path, 
                 tmp_wav_to_clean,
                 f"{temp_output_base}.srt", 
                 f"{temp_output_base}.txt"
             ]
             
             for path_to_clean in paths_to_clean:
                 if path_to_clean and os.path.exists(path_to_clean):
                     try:
                         os.remove(path_to_clean)
                     except OSError as e:
                         print(f"無法刪除暫存檔 {path_to_clean}: {e}")

    if not worker_thread._is_cancelled:
        total_time = time.time() - total_start_time
        worker_thread.all_finished.emit(total_time, backend_str)

