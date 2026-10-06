@echo off
rem 把两个音频模型服务注册为 Windows 计划任务,开机自启
rem 需要以管理员身份运行本脚本
cd /d I:\GitHub\audio-models

echo 注册开机自启计划任务...

schtasks /Create /TN "AudioModels-Kokoro-TTS" /TR "I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\kokoro\server.py" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
schtasks /Create /TN "AudioModels-SenseVoice-ASR" /TR "I:\GitHub\audio-models\sensevoice\.venv\Scripts\python.exe I:\GitHub\audio-models\sensevoice\server.py" /SC ONSTART /RU SYSTEM /RL HIGHEST /F

echo.
echo 已创建两个计划任务:
echo   AudioModels-Kokoro-TTS       (开机启动 Kokoro TTS)
echo   AudioModels-SenseVoice-ASR   (开机启动 SenseVoice ASR)
echo.
echo 查看: schtasks /Query /TN "AudioModels-Kokoro-TTS"
echo 删除: schtasks /Delete /TN "AudioModels-Kokoro-TTS"
echo.
pause
