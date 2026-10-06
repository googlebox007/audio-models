@echo off
rem 启动本地音频模型 Web 客户端 (静态模式,浏览器直连后端,依赖 CORS)
rem 用法: run_web.bat [8890] [static|proxy]
cd /d I:\GitHub\audio-models

set PORT=%1
set MODE=%2
if "%PORT%"=="" set PORT=8890
if "%MODE%"=="" set MODE=static

echo 启动 Web 客户端 http://127.0.0.1:%PORT% (模式 %MODE%)
rem 用 kokoro venv 的 python(已含所有依赖)运行
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\web\web_server.py %PORT% %MODE%
