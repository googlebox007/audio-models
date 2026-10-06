@echo off
rem 启动 Kokoro-82M TTS 服务 (端口 8898)
echo [kokoro] 启动 TTS 服务 http://0.0.0.0:8898
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\kokoro\server.py
pause
