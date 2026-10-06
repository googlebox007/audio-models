@echo off
rem 停止 Kokoro TTS (:8898) 和 SenseVoice ASR (:8899) 服务
cd /d I:\GitHub\audio-models
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py stop
pause
