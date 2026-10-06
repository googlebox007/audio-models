@echo off
rem 移除开机自启计划任务
rem 需要以管理员身份运行本脚本
cd /d I:\GitHub\audio-models

echo 移除计划任务...
schtasks /Delete /TN "AudioModels-Kokoro-TTS" /F
schtasks /Delete /TN "AudioModels-SenseVoice-ASR" /F
echo 完成。
pause
