@echo off
REM rebuild_venvs.bat - rebuild 4 service venvs (no weights / no source pkg)
REM Usage: double-click, or: I:\GitHub\audio-models\rebuild_venvs.bat
REM Rebuilds venv + pip deps for kokoro/sensevoice/edge/cosyvoice.
REM Does NOT download cosyvoice_pkg / model weights / Matcha -
REM   see AGENTS-DEPLOY.md section 4 (ghproxy + hf-mirror, needs network).
REM Needs: Python 3.12 (py -3.12), ffmpeg on PATH (Edge mp3 to wav).
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%" neq "\" set "ROOT=%ROOT%\"
set "ALI=-i https://mirrors.aliyun.com/pypi/simple/"
set "TURL=--index-url https://download.pytorch.org/whl/cu126"
echo ==========================================================
echo  Rebuild audio-models venvs   root: %ROOT%
echo ==========================================================

REM ---------- 1) Kokoro 8898 ----------
echo.
echo [1/4] Kokoro ...
pushd "%ROOT%kokoro"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install %TURL% torch torchaudio
".venv\Scripts\python.exe" -m pip install %ALI% -r requirements.txt
popd

REM ---------- 2) SenseVoice 8899 ----------
echo.
echo [2/4] SenseVoice ...
pushd "%ROOT%sensevoice"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install %TURL% torch torchaudio
".venv\Scripts\python.exe" -m pip install %ALI% -r requirements.txt
popd

REM ---------- 3) EdgeTTS 8896 ----------
echo.
echo [3/4] EdgeTTS ...
pushd "%ROOT%edge"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install %ALI% "edge-tts>=7.0" fastapi uvicorn
popd

REM ---------- 4) CosyVoice2 8897 ----------
echo.
echo [4/4] CosyVoice ...
pushd "%ROOT%cosyvoice"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install %ALI% torch torchaudio
".venv\Scripts\python.exe" -m pip install %ALI% soundfile
".venv\Scripts\python.exe" -m pip install %ALI% hyperpyyaml inflect rich wget phonemizer huggingface_hub==0.34.4 pyarrow pypinyin torch-complex pyworld onnxruntime omegaconf gdown librosa matplotlib ninja numpy umap-learn conformer g2p-en openai-whisper diffusers transformers==4.57.0 peft
REM apply load_wav patch (bypass torchcodec), mandatory
".venv\Scripts\python.exe" "%ROOT%cosyvoice\patch_loadwav.py"
popd

echo.
echo ==========================================================
echo  venv rebuild done. Next steps (AGENTS-DEPLOY.md section 4):
echo    - fetch CosyVoice source pkg cosyvoice_pkg/  (ghproxy)
echo    - fetch Matcha-TTS submodule                  (ghproxy)
echo    - download weights model/ + CosyVoice-BlankEN (hf-mirror)
echo    - start: manage.py start
echo ==========================================================
echo.
pause
