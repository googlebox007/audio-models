# audio-models — 本地部署 Kokoro-82M (TTS) + SenseVoice-Small (ASR) + EdgeTTS + CosyVoice2

> **给 AI agent / 想无人值守重建的人**：先看 [`AGENTS-DEPLOY.md`](AGENTS-DEPLOY.md)。
> 它按服务给出可粘贴命令 + 每步验证 + 踩坑清单，重点覆盖 CosyVoice 的依赖链 / 权重 / `patch_loadwav.py`，
> 结尾有 7 条验收清单。venv 丢了可双击 `rebuild_venvs.bat` 一键重建（不含权重与源码包）。

## 环境概览

- **GPU**: RTX 3060 12GB (CUDA),torch 2.10.0+cu126 已启用(CosyVoice 当前用 CPU 版,可用 sensevoice venv 的 cu126 torch 提速)
- **Python**: 3.12 (每个模型独立 venv,互不干扰)
- **部署路径**: `I:\GitHub\audio-models\`

| 模型 | 用途 | 目录 | venv | 默认端口 |
|---|---|---|---|---|
| Kokoro-82M | 文本→语音 (8 语言 54 音色) | `kokoro\` | `kokoro\.venv` | 8898 |
| SenseVoice-Small | 语音→文本 (中/粤/英/日/韩 + 语种识别 + 情绪/事件) | `sensevoice\` | `sensevoice\.venv` | 8899 |
| EdgeTTS | 微软神经音色,14 个中文 Neural(走公网,需联网) | `edge\` | `edge\.venv` | 8896 |
| CosyVoice2-0.5B | 零样本声音克隆,支持参考音频 | `cosyvoice\` | `cosyvoice\.venv` | 8897 |

---

## 一、服务管理(推荐方式)

### Web 客户端界面(推荐入门方式)

现在 `manage.py start` 会**一次拉起全部服务**(Kokoro/SenseVoice/Edge/CosyVoice + Web 客户端),无需再手动起 web:

```powershell
# 启动全部(后端先起,Web 最后起;自动后台+日志)
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py start

# 停止全部(Web 先停)
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py stop
```

Web 客户端运行在 **http://127.0.0.1:8890**(proxy 模式,同源无跨域),三个标签页:
- **🎙️ 语音合成** — 可选 TTS 引擎(Kokoro / EdgeTTS / CosyVoice)+ 音色 + 语言 + 语速;CosyVoice 还支持上传参考音频做零样本克隆
- **📝 语音识别** — 拖入音频文件,选语言,点"转写",立即出文本
- **🔄 串联 (ASR→TTS)** — 上传录音,自动识别并换成指定音色重新播报

两种模式(浏览器自动适配,前端读 `config.js`):
| 模式 | 命令 | 原理 | 适用 |
|---|---|---|---|
| `static` | `web_server.py 8890 static` | 页面直连各后端(依赖 CORS) | 本地 127.0.0.1 访问 |
| `proxy` | `web_server.py 8890 proxy` | 前端请求经 8890 转发到各后端(含 edge/cosy 子路由) | 局域网/远程访问、CORS 被拦时(默认) |

`run_web.bat` 支持参数:`run_web.bat 8890 proxy`(默认 8890 / static)。

---

### 启动 / 停止 / 状态

```powershell
# 同时启动两个服务(后台,日志写到 logs\)
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py start

# 停止
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py stop

# 查看状态
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py status
```

或双击 `start_all.bat` / `stop_all.bat`(内部就是调用 manage.py)。

### 开机自启(可选)

```powershell
# 以管理员身份运行,把两个服务注册为 Windows 计划任务(开机启动)
I:\GitHub\audio-models\setup_autostart.bat

# 移除自启
I:\GitHub\audio-models\remove_autostart.bat
```

### 一键端到端测试

```powershell
# 前提:服务已启动
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\test_services.py
```

会:TTS 合成 → ASR 转写 → 校验一致,全部通过显示 `[PASS]`。

---

## 二、Kokoro-82M (TTS)

### 命令行测试

```powershell
cd I:\GitHub\audio-models\kokoro
# 英文
.\.venv\Scripts\python.exe test_kokoro.py "Hello, local TTS on GPU." am_michael
# 中文
.\.venv\Scripts\python.exe test_kokoro.py "你好,本地语音合成。" zm_yunxi
# 输出: kokoro\output\sample.wav
```

常用音色:`am_michael`/`am_santa`/`af_bella`/`af_heart`(美)、`bm_lewis`/`bf_isabella`(英)、`zm_yunxi`/`zm_yunyang`(中)。

### HTTP API(服务运行时)

```powershell
# TTS(合成)
curl.exe -X POST http://127.0.0.1:8898/tts `
     -H "Content-Type: application/json" `
     -d '{"text":"你好","voice":"zm_yunxi","lang":"z"}' `
     --output out.wav

# 音色列表
curl.exe http://127.0.0.1:8898/voices

# 健康检查
curl.exe http://127.0.0.1:8898/health
```

`lang` 取值:`auto`(按文字自动判断)或单字母码 `a/b/j/z/e/f/h/i/p`(美/英/日/中/西/法/印/意/葡)。

---

## 三、SenseVoice-Small (ASR)

### 命令行测试

```powershell
cd I:\GitHub\audio-models\sensevoice
# 任意 ffmpeg 可读格式(mp3/wav/flac/ogg...)
.\.venv\Scripts\python.exe test_sensevoice.py "..\kokoro\output\sample.wav" zh
# 自动检测语言: 省略第二个参数或写 auto
# 输出: sensevoice\output\<音频名>.txt + 终端打印识别文本
```

### HTTP API(服务运行时)

```powershell
# 转写
curl.exe -F "file=@test.mp3" -F "language=zh" http://127.0.0.1:8899/transcribe
# 返回: {"text":"...","language":"zh","time":0.4}

# 健康检查
curl.exe http://127.0.0.1:8899/health
```

`language` 取值:`auto / zh / en / yue / ja / ko / nospeech`。`itn` 默认 true(数字归一化)。

---

## 四、EdgeTTS(:8896)— 14 个中文 Neural 音色

EdgeTTS 走微软公网神经语音,需要联网;胜在音色多、零本地权重。

### HTTP API(服务运行时)

```powershell
# 合成(JSON POST)
curl.exe -X POST http://127.0.0.1:8896/tts `
     -H "Content-Type: application/json" `
     -d '{"text":"你好","voice":"zh-CN-XiaoxiaoNeural","rate":"+0%","pitch":"+0Hz","vol":"+0%"}' `
     --output out.wav

# 音色列表(14 个中文 Neural)
curl.exe http://127.0.0.1:8896/voices

# 健康检查
curl.exe http://127.0.0.1:8896/health
```

- `voice` 常用:`zh-CN-XiaoxiaoNeural`(晓晓·女)、`zh-CN-YunjianNeural`(云健·男)、
  `zh-CN-YunxiNeural`(云希·男)、`zh-CN-YunyangNeural`(云阳·男)、
  `zh-CN-liaoning-XiaobeiNeural`(晓北·辽宁)、`zh-CN-shaanxi-XiaoniNeural`(小妮·陕西)、
  `zh-HK-HiuGaaiNeural`(港·女)、`zh-TW-YunJheNeural`(台·男)等。
- `rate` 为百分比字符串,如 `"+20%"` / `"-10%"`;`pitch` 为 Hz,如 `"+0Hz"`;`vol` 为百分比。
- 输出统一为 WAV(mp3 经本机 ffmpeg 转码)。

---

## 五、CosyVoice2-0.5B(:8897)— 零样本声音克隆

本地权重约 4GB,支持「参考音频 + 文本」零样本克隆,也可用内置 preset。
当前用 CPU 版 torch 可跑(RTF 偏慢);需要提速可切到 `sensevoice\.venv` 的 cu126 torch。

### HTTP API(服务运行时)

```powershell
# 内置 preset 合成(multipart)
curl.exe -X POST http://127.0.0.1:8897/tts `
     -F "text=你好,这是克隆测试" `
     -F "preset=zero_shot_prompt" `
     --output out.wav

# 零样本克隆(上传参考音频,10~30 秒清晰人声)
curl.exe -X POST http://127.0.0.1:8897/tts `
     -F "text=你好,这是用你的声音合成的" `
     -F "ref_audio=@my_voice.wav" `
     -F "ref_text=参考音频对应的文字" `
     --output out.wav

# preset 列表
curl.exe http://127.0.0.1:8897/voices

# 健康检查
curl.exe http://127.0.0.1:8897/health
```

- `preset` 取值:`zero_shot_prompt` / `cross_lingual_prompt`(不传 `ref_audio` 时使用)。
- 传 `ref_audio` 时忽略 `preset`,改为按参考音频克隆;`ref_text` 尽量与参考音频内容一致。
- 首次请求会触发模型加载,健康检查可能耗时较长。

---

## 六、组合使用:ASR → TTS 工作流

```powershell
# 方式 A: 命令行串联
# 1. ASR 把录音转成文字
I:\GitHub\audio-models\sensevoice\.venv\Scripts\python.exe I:\GitHub\audio-models\sensevoice\test_sensevoice.py C:\path\recording.mp3 auto
$text = Get-Content I:\GitHub\audio-models\sensevoice\output\recording.txt
# 2. TTS 把文字换成另一种音色
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\kokoro\test_kokoro.py $text af_heart

# 方式 B: HTTP 串联(推荐,不占 CPU/GPU 互锁)
# ASR
$r = curl.exe -s -F "file=@recording.mp3" -F "language=auto" http://127.0.0.1:8899/transcribe
# TTS
curl.exe -s -X POST http://127.0.0.1:8898/tts -H "Content-Type: application/json" `
         -d "{`"text`":$($r.text),`"voice`":`"af_heart`",`"lang`":`"z`"}" -o out.wav
```

---

## 七、常见问题

- **首次运行慢**: 两个服务首次启动都会自动从 HuggingFace 下载模型权重
  (Kokoro ~320MB,SenseVoice ~900MB),之后就完全离线可用。
- **Windows 上 espeak-ng 不需要装**: Kokoro 0.9.4 用 `phonemizer-fork` + `espeakng_loader`
  包内置处理,无需系统 espeak-ng。
- **soundfile 在 Windows 上有 libsndfile.dll 加载问题**: 测试/服务脚本已改用 `wave` 模块写 wav,无需第三方库。
- **GPU 显存**: 两个模型合计 < 3GB 显存,RTX 3060 12GB 可长期同时运行两个服务。
- **curl 报错**: PowerShell 把 `curl` 解析成 `Invoke-WebRequest`,请显式用 `curl.exe`。
- **Web 客户端 401/连不上**: 若浏览器从远程访问 `web_server.py`,用 `proxy` 模式
  (`web_server.py 8890 proxy`),让前端请求经 8890 转发,避免跨域。

## 八、重新安装(如 venv 丢失)

**一键(推荐)**：双击运行根目录的 `rebuild_venvs.bat`——它会重建 4 个服务 venv
并装好各自依赖(含 CosyVoice 依赖链与 `patch_loadwav.py` 补丁)。
**它不下载** CosyVoice 的源码包 `cosyvoice_pkg/`、权重 `model/` 与 Matcha 子模块
(那三步走 ghproxy / hf-mirror,需要联网,按 `AGENTS-DEPLOY.md` 第 4 节手动做)。

手动等效命令:

```powershell
# Kokoro
cd I:\GitHub\audio-models\kokoro
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch torchaudio -U
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# SenseVoice 同理
# EdgeTTS: py -3.12 -m venv edge\.venv;edge\.venv\Scripts\python.exe -m pip install "edge-tts>=7.0" fastapi uvicorn
# CosyVoice: 见 cosyvoice\README(需权重,走 hf-mirror,依赖较多,含 third_party/Matcha-TTS)
```

注意: torch CUDA 版从 `https://download.pytorch.org/whl/cu126` 安装(网络不稳时可用本地 wheel 兜底,见 `kokoro\install_local_torch.py`)。

---

## 九、GitHub 推送备忘

仓库: `https://github.com/googlebox007/audio-models` (公开,`main` 分支)

本机网络**直连 github.com 的 443 端口会被重置**,但 `ghproxy.net` 镜像可访问。
`origin` 保持干净的直连地址;只有推送失败时,才临时用镜像内联转发(不污染全局配置):

```powershell
# 直连失败时, 用 ghproxy 镜像推一次 (带 GitHub token, 不回显)
$token = gh auth token
git push "https://x-access-token:$token@ghproxy.net/https://github.com/googlebox007/audio-models.git" main
```

不要全局加 `url."https://ghproxy.net/...".insteadOf="https://github.com/"` 的重写,
否则这台机器上**所有** GitHub 仓库都会静默走第三方代理(隐私/安全隐患)。

`.gitignore` 已排除 `kokoro/.venv`、`sensevoice/.venv`、`wheels/`、`logs/` 与模型权重,
仓库只含可复用脚本与文档,克隆后按「六、重新安装」重建 venv 即可。
