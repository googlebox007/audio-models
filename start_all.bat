@echo off
rem 同时启动 Kokoro (TTS :8898) 和 SenseVoice (ASR :8899) 服务
rem 用法: start_all.bat [kokoro|sensevoice|all]
cd /d I:\GitHub\audio-models

set TARGET=%1
if "%TARGET%"=="" set TARGET=all

echo 启动服务: %TARGET%
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py start
echo.
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py status
echo.
echo 日志目录: I:\GitHub\audio-models\logs\
echo 停止服务: 运行 stop_all.bat
pause
