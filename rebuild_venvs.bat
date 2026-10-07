@echo off
REM ============================================================
REM  rebuild_venvs.bat - 一键重建全部 4 个服务 venv (不下载权重/源码)
REM
REM  用法:
REM    双击运行, 或 powershell 里: I:\GitHub\audio-models\rebuild_venvs.bat
REM
REM  只做: 建 venv + pip install 依赖。
REM  不做: 下载 CosyVoice 源码包 (cosyvoice_pkg/) 与权重 (model/),
REM        以及 Matcha 子模块 —— 那三步按 AGENTS-DEPLOY.md 的第 4 节做
REM        (走 ghproxy / hf-mirror, 需要网络)。
REM
REM  前置: 已装 Python 3.12 (py -3.12 可用)
REM ============================================================
setlocal
set "ROOT=%~dp0"
set "PIP=-i https://mirrors.aliyun.com/pypi/simple/"
echo ==========================================================
echo  重建 audio-models 各服务 venv
echo  根目录: %ROOT%
echo ==========================================================

REM ---------- 1) Kokoro 8898 ----------
echo.
echo [1/4] Kokoro ...
pushd "%ROOT%kokoro"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install %PIP% torch torchaudio --index-url https://download.pytorch.org/whl/cu126
".venv\Scripts\python.exe" -m pip install %PIP% -r requirements.txt
popd

REM ---------- 2) SenseVoice 8899 ----------
echo.
echo [2/4] SenseVoice ...
pushd "%ROOT%sensevoice"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install %PIP% torch torchaudio --index-url https://download.pytorch.org/whl/cu126
".venv\Scripts\python.exe" -m pip install %PIP% -r requirements.txt
popd

REM ---------- 3) EdgeTTS 8896 ----------
echo.
echo [3/4] EdgeTTS ...
pushd "%ROOT%edge"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install %PIP% "edge-tts>=7.0" fastapi uvicorn
popd

REM ---------- 4) CosyVoice2 8897 ----------
echo.
echo [4/4] CosyVoice ...
pushd "%ROOT%cosyvoice"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install %PIP% torch torchaudio
".venv\Scripts\python.exe" -m pip install %PIP% soundfile
".venv\Scripts\python.exe" -m pip install %PIP% `
    hyperpyyaml inflect rich wget phonemizer huggingface_hub==0.34.4 `
    pyarrow pypinyin torch-complex pyworld onnxruntime omegaconf gdown `
    librosa matplotlib ninja numpy umap-learn conformer g2p-en openai-whisper `
    diffusers transformers==4.57.0 peft
REM 应用 load_wav 补丁(绕开 torchcodec), 必须做
".venv\Scripts\python.exe" "%ROOT%cosyvoice\patch_loadwav.py"
popd

echo.
echo ==========================================================
echo  venv 重建完成。下一步 (按 AGENTS-DEPLOY.md 第 4 节):
echo    - 拉 CosyVoice 源码包 cosyvoice_pkg/  (ghproxy)
echo    - 拉 Matcha-TTS 子模块                 (ghproxy)
echo    - 下载权重 model/ + CosyVoice-BlankEN  (hf-mirror)
echo    - 启动: manage.py start
echo ==========================================================
echo.
pause
