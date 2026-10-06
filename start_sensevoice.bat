@echo off
rem 启动 SenseVoice-Small ASR 服务 (端口 8899)
echo [sensevoice] 启动 ASR 服务 http://0.0.0.0:8899
I:\GitHub\audio-models\sensevoice\.venv\Scripts\python.exe I:\GitHub\audio-models\sensevoice\server.py
pause
