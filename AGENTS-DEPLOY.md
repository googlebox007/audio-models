# AGENTS-DEPLOY.md — 给 AI Agent 的部署执行手册

> 这份文档**专门写给 AI agent**（Claude Code / 其他编码 agent），目的是让你能在**无人值守**下
> 把 `audio-models` 项目从头部署到 5 个服务全部可运行。人类可以读，但行文默认你是要**直接执行命令**的 agent。
>
> **执行原则：**
> 1. 每一步都给出**可粘贴的完整命令**，不要让我猜参数。
> 2. 每一步都给出**验证命令 + 期望输出**，跑完必须自己验证再进下一步。
> 3. 每节末尾有「本 agent 的坑」，都是上一次真实部署踩出来的，**必须按它做，不要自行发挥**。
> 4. 出现错误先查「常见故障」小节，不要盲目重试或重装。
> 5. 所有长命令用 shell 工具跑，后台服务用 `manage.py` 统一管，不要手动起一堆进程。

---

## 0. 总览（先读完再动手）

### 0.1 交付目标

部署完成后，本机 `I:\GitHub\audio-models\` 下应有 **5 个监听端口**，全部可用：

| 服务 | 端口 | venv | 说明 |
|---|---|---|---|
| Kokoro-82M | 8898 | `kokoro\.venv` | 本地 TTS，GPU（若 CUDA 装好）或 CPU |
| SenseVoice-Small | 8899 | `sensevoice\.venv` | 本地 ASR |
| EdgeTTS | 8896 | `edge\.venv` | 微软神经音色，**需联网**，14 中文 Neural |
| CosyVoice2-0.5B | 8897 | `cosyvoice\.venv` | 本地零样本声音克隆，CPU 可跑（慢） |
| Web 客户端 | 8890 | 复用 `kokoro\.venv` | 反代 + 前端，proxy 模式 |

全部就绪后，`http://127.0.0.1:8890` 能开，TTS 页可在 Kokoro/Edge/Cosy 三引擎间切换。

### 0.2 环境假设

- **OS**：Windows 10/11 + PowerShell。
- **Python**：3.12（`py -3.12`）。若没有 3.12，安装它再开 venv。
- **路径**：项目根 `I:\GitHub\audio-models\`。下文所有路径以此为基准。
- **显存**：RTX 3060 12GB 可全跑；只有 8GB 或无 GPU 时，Kokoro/CosyVoice 走 CPU（能跑但慢，见 §5.4）。
- **网络**：**直连 github.com / huggingface.co 的 443 会被重置**。
  - GitHub 源码/zip → `ghproxy.net`（`https://ghproxy.net/https://github.com/<owner>/<repo>.zip`）
  - HF 权重 → `hf-mirror.com`，且**必须设** `HF_ENDPOINT=https://hf-mirror.com`
  - pip → 阿里云镜像 `-i https://mirrors.aliyun.com/pypi/simple/`
- **ffmpeg**：本机在 `C:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe`（Edge 的 mp3→wav 用它）。
  若你机器上路径不同，先 `where.exe ffmpeg` 确认，并让 ffmpeg 在 PATH 或改 `edge\server.py` 里的调用。

### 0.3 执行顺序（严格按此）

> **先判断现场**：clone 下来 / venv 全丢 → 先跑根目录 `rebuild_venvs.bat`（一键重建 4 个
> venv + 装好全部依赖，含 CosyVoice 的 `patch_loadwav.py` 补丁）。它**不下载** CosyVoice
> 源码包 / 权重 / Matcha——那三步仍按 §4.2/§4.3/§4.5 手动做（走 ghproxy / hf-mirror）。
> 跑完再进入下面的顺序。venv 都在时这步可跳过，直接 `[1]` 起。

```
[0] venv 全丢? 先双击 rebuild_venvs.bat  (一键重建 4 个 venv+依赖, 不含权重/源码)
[1] kokoro venv + 模型        (§1)
[2] sensevoice venv + 模型     (§2)
[3] edge venv + 服务          (§3)
[4] cosyvoice venv + 源码 + 权重 + 服务 (§4, 最重, 最后做)
[5] web 客户端（依赖 1-4 全在）  (§5)
[6] 全链路验证                 (§6)
[7] manage.py 一键管理         (§7)
```

§4 最耗时长（权重 ~4.5GB + 一堆依赖），放最后做；前 3 个先让 8898/8899/8896 活起来，web 可以先用「降级」状态跑。
若 `rebuild_venvs.bat` 已跑过，§1-§4 的「建 venv + 装依赖」两步可跳过，直接做「拉源码/权重 + 启动 + 验证」。

---

## 1. Kokoro-82M（TTS :8898）

目标：`kokoro\.venv` 建好，`kokoro\server.py` 能在 8898 跑起来。

### 1.1 建 venv + 装依赖

```powershell
cd I:\GitHub\audio-models\kokoro
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
# GPU: 先装 cu126 的 torch/torchaudio（若 GPU 且网络不稳, 用本地 wheel 兜底, 见下方「坑」）
.\.venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126
# 其余依赖
.\.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
```

**验证：**
```powershell
.\.venv\Scripts\python.exe -c "import kokoro, torch; print('kokoro ok'); print('cuda:', torch.cuda.is_available())"
```
期望：打印 `kokoro ok`。`cuda: True` 为 GPU 可用；`False` 也能继续（CPU 跑）。

### 1.2 启动 + 验证

```powershell
# 启动（后台, 日志到 logs\kokoro.log）
.\.venv\Scripts\python.exe I:\GitHub\audio-models\kokoro\server.py   # 前台先测一次更稳
```

```powershell
curl.exe http://127.0.0.1:8898/health
```
期望：`{"status":"ok","pipelines":["a","z"]}`

**合成验证：**
```powershell
curl.exe -X POST http://127.0.0.1:8898/tts -H "Content-Type: application/json" `
  -d '{"text":"你好，本地语音合成。","voice":"zm_yunxi","lang":"z"}' -o I:\GitHub\audio-models\logs\kokoro_test.wav
# 看是否生成了非空 wav
Get-Item I:\GitHub\audio-models\logs\kokoro_test.wav | Select Length
```
期望：文件几 KB 以上、非 0。

### 1.3 本 agent 的坑

- **GPU torch 装不上 / 走错源**：cu126 官方源有时网络断。仓库里 `kokoro\install_local_torch.py`、
  `kokoro\download_torch.py` / `kokoro\download_torchaudio.py` 是本地 wheel 兜底脚本，
  官方源失败就跑它们。装完务必 `torch.cuda.is_available()` 确认真是 cu 版。
- **Kokoro 中文官方只有 4 个音色**（`zm_yunxi / zm_yunyang / zf_xiaobei / zf_xiaoxiao`）。
  这是**设计如此**，不是 bug——更多中文音色靠 §3 的 EdgeTTS 和 §4 的 CosyVoice 补，不要再去 hf-mirror 拉
  hex10 仓库（会 401，已验证拉不到更多）。
- **espeak-ng 不用装**：Kokoro 0.9.4 用 `phonemizer-fork` + `espeakng_loader` 内置处理，Windows 无需系统级 espeak。
- **写 wav 用 `wave` 模块**，别装 `soundfile`（Windows 上 `libsndfile.dll` 加载有坑，本项目已绕开）。

---

## 2. SenseVoice-Small（ASR :8899）

目标：`sensevoice\.venv` 建好，`sensevoice\server.py` 在 8899 跑起来。

### 2.1 建 venv + 装依赖

```powershell
cd I:\GitHub\audio-models\sensevoice
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
# GPU 版 torch（和 kokoro 同口径, 可共用 cu126）
.\.venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126
.\.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
```

**验证：**
```powershell
.\.venv\Scripts\python.exe -c "import funasr; print('funasr ok', funasr.__version__ if hasattr(funasr,'__version__') else '')"
```

### 2.2 启动 + 验证

```powershell
.\.venv\Scripts\python.exe I:\GitHub\audio-models\sensevoice\server.py
```
```powershell
curl.exe http://127.0.0.1:8899/health
```
期望：`{"status":"ok","model_loaded":true}`

**转写验证**（用 §1 生成的 wav 回灌）：
```powershell
curl.exe -F "file=@I:\GitHub\audio-models\logs\kokoro_test.wav" -F "language=zh" http://127.0.0.1:8899/transcribe
```
期望：`{"text":"你好，本地语音合成","language":"zh","time":...}`（文字基本一致即算过）。

### 2.3 本 agent 的坑

- 首次启动会自动从 HF 拉模型到 `~/.cache/huggingface`，**必须设** `HF_ENDPOINT=https://hf-mirror.com`，否则直连被重置。
  若 server.py 没设，手动：`$env:HF_ENDPOINT="https://hf-mirror.com"` 再启动。
- 依赖里 `trust_remote_code` 相关 warning 是正常的，看到 `[INFO] Loading ... All keys matched successfully` 才算加载成功。

---

## 3. EdgeTTS（:8896）

目标：`edge\.venv` 建好，`edge\server.py` 在 8896 跑起来。**这个是走公网的，需要能访问微软 TTS endpoint。**

### 3.1 建 venv + 装依赖

```powershell
cd I:\GitHub\audio-models\edge
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
# edge-tts 必须 >= 7.0（6.x 对微软新 endpoint 会 403，见「坑」）
.\.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ "edge-tts>=7.0" fastapi uvicorn
```

**验证版本：**
```powershell
.\.venv\Scripts\python.exe -c "import importlib.metadata as m; print(m.version('edge-tts'))"
```
期望：`7.x`（当前部署用的是 7.2.8）。**若不是 7.x，回到上面重装。**

### 3.2 启动 + 验证

```powershell
.\.venv\Scripts\python.exe I:\GitHub\audio-models\edge\server.py
```
```powershell
curl.exe http://127.0.0.1:8896/health
```
期望：`{"status":"ok","backend":"edge-tts","voices":14}`

**音色列表：**
```powershell
curl.exe http://127.0.0.1:8896/voices
```
期望：返回 14 个中文 Neural 音色（晓晓/晓懿/云健/云希/云夏/云阳/晓北辽宁/小妮陕西/港·希嘉希雯文龙/台·晓辰晓宇云哲）。

**合成验证：**
```powershell
curl.exe -X POST http://127.0.0.1:8896/tts -H "Content-Type: application/json" `
  -d '{"text":"你好，这是 Edge 音色测试。","voice":"zh-CN-XiaoxiaoNeural","rate":"+0%","pitch":"+0Hz","vol":"+0%"}' `
  -o I:\GitHub\audio-models\logs\edge_test.wav
Get-Item I:\GitHub\audio-models\logs\edge_test.wav | Select Length
```
期望：非空 wav（Edge 原生出 mp3，server.py 内部用 ffmpeg 转 wav）。

### 3.3 本 agent 的坑

- **edge-tts 6.x 必挂**：报 `WSServerHandshakeError 403 Invalid response status`。微软 endpoint 变了，**必须 7.x**。
  7.2.8 内置了可用 token，实测能收到 22 个分片。
- **ffmpeg 必须有**：mp3→wav 靠 `C:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe`。缺了合成会 500。
- **需联网**：EdgeTTS 是微软云端，断网时 `/tts` 会失败但 `/health` 仍 ok。别把断网误判成部署错。
- 中文音色就这 14 个，不要期望更多。

---

## 4. CosyVoice2-0.5B（:8897）—— 最重的一节，务必按序

目标：`cosyvoice\.venv` + 源码包 `cosyvoice_pkg/` + 权重 `model/`（~4.5GB）全到位，`cosyvoice\server.py` 在 8897 跑起来。
这是 5 个服务里**依赖链最长、最容易卡**的，请**严格按 4.1→4.6 走，每步验证**。

### 4.1 建 venv + 基础依赖

```powershell
cd I:\GitHub\audio-models\cosyvoice
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
# torch：CPU 版即可跑（当前部署用 torch 2.14.1 CPU + torchaudio 2.11.0）；要提速换 cu126（见 4.5）
.\.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ torch torchaudio
```

### 4.2 拉源码包（ghproxy，直连 GitHub 会重置）

```powershell
.\.venv\Scripts\python.exe -c "
import urllib.request, os, zipfile, io
url = 'https://ghproxy.net/https://github.com/FunAudioLLM/CosyVoice2-0.5B/main.zip'
# 若 main.zip 404, 改为对应分支/commit; 当前部署用的是 main
req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
data = urllib.request.urlopen(req, timeout=600).read()
z = zipfile.ZipFile(io.BytesIO(data))
z.extractall(r'I:\GitHub\audio-models\cosyvoice\cosyvoice_pkg_extract')
print('unzipped', len(z.namelist()), 'files')
"
# 解压后仓库有嵌套一层, 把内层 cosyvoice 源码目录挪成 cosyvoice_pkg
# 具体子目录名以解压结果为准, 通常里层含 cosyvoice/ 与 third_party/
```

> **关键**：最终 `cosyvoice\cosyvoice_pkg\` 下要有 `cosyvoice\`（含 `cli/ dataset/ frontend/`）
> 和 `third_party\Matcha-TTS\matcha\` 两块。缺了 import 会连环炸（见 4.4）。

### 4.3 拉 Matcha-TTS 第三方子模块（ghproxy）

CosyVoice 依赖 `shivammehta25/Matcha-TTS`，官方是 git submodule，直连会挂：

```powershell
.\.venv\Scripts\python.exe -c "
import urllib.request, os, zipfile, io
url = 'https://ghproxy.net/https://github.com/shivammehta25/Matcha-TTS/main.zip'
req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
data = urllib.request.urlopen(req, timeout=300).read()
z = zipfile.ZipFile(io.BytesIO(data))
z.extractall(r'I:\GitHub\audio-models\cosyvoice\cosyvoice_pkg\third_party\Matcha-TTS_extract')
print('matcha unzipped')
"
# 确保 cosyvoice_pkg\third_party\Matcha-TTS\matcha\ 存在（server.py 的 sys.path 就指向它）
```

### 4.4 装 CosyVoice 依赖（**逐层补，别一次全装**）

上次部署实际顺序是「import 一个缺一个」地补出来的。为省时间直接一次性装下面这批（已验证），
**但 `pynini` 不要装**（本地编译会卡死）：

```powershell
.\.venv\Scripts\python.exe -m pip install -i https://mirrors.aliyun.com/pypi/simple/ `
  hyperpyyaml inflect rich wget phonemizer huggingface_hub==0.34.4 `
  pyarrow pypinyin torch-complex pyworld onnxruntime omegaconf gdown `
  librosa matplotlib ninja numpy umap-learn conformer g2p-en openai-whisper `
  diffusers transformers==4.57.0 peft
```

**验证 import 链（不装模型, 只测 import）：**
```powershell
.\.venv\Scripts\python.exe -c "
import sys, os
sys.path.insert(0, r'I:\GitHub\audio-models\cosyvoice')
import hf_stub
os.environ.setdefault('HF_ENDPOINT','https://hf-mirror.com')
sys.path.insert(0, r'I:\GitHub\audio-models\cosyvoice\cosyvoice_pkg')
sys.path.insert(0, r'I:\GitHub\audio-models\cosyvoice\cosyvoice_pkg\third_party\Matcha-TTS')
from cosyvoice.cli.cosyvoice import CosyVoice2
print('import ok')
"
```
期望：`import ok`。若报 `ModuleNotFoundError: No module named 'X'`，把 X 补进上面 pip 那行重装。
常见连环：`pyarrow` → `pyworld` → `rich` → `wget` → `huggingface_hub` 符号（用 hf_stub 兜）→ `torchcodec`/`soundfile`（见 4.4 坑）。

### 4.5 下载权重（~4.5GB，走 hf-mirror，可续传）

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
# 主权重（llm/flow/hift/campplus/speech_tokenizer 等, 见 dl_model.py 的文件清单）
.\.venv\Scripts\python.exe I:\GitHub\audio-models\cosyvoice\dl_model.py
# GPT 前端 CosyVoice-BlankEN（model.safetensors ~988MB 等, 见 dl_blanken.py）
.\.venv\Scripts\python.exe I:\GitHub\audio-models\cosyvoice\dl_blanken.py
```

**验证权重完整（尤其 llm.pt 别是半截）：**
```powershell
Get-ChildItem I:\GitHub\audio-models\cosyvoice\model -Recurse -File |
  Select Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
```
期望（对齐上次成功部署）：
```
campplus.onnx ~28MB   flow.pt ~450MB   hift.pt ~83MB   llm.pt ~1930MB
flow.decoder.estimator.fp32.onnx ~129MB
speech_tokenizer_v2*.onnx 各 ~496MB
CosyVoice-BlankEN/model.safetensors ~988MB
```
> **llm.pt 必须 ~1.9GB**。上次就因为它下到 600MB 就断过，导致 `PytorchStreamReader failed reading zip archive`。
> 如果 llm.pt 明显偏小，**删掉重跑 `dl_model.py`**（它按 >100 字节判断 skip，断点文件会骗过它，先手动删）。

### 4.6 启动 + 端到端验证（首次会触发模型加载，~2 分钟）

```powershell
.\.venv\Scripts\python.exe I:\GitHub\audio-models\cosyvoice\server.py
```
```powershell
curl.exe http://127.0.0.1:8897/health
```
期望：`{"status":"ok","model":"cosyvoice2-0.5b","presets":["cross_lingual_prompt","zero_shot_prompt"]}`

**preset 合成：**
```powershell
curl.exe -X POST http://127.0.0.1:8897/tts -F "text=你好，这是 CosyVoice 克隆测试。" -F "preset=zero_shot_prompt" `
  -o I:\GitHub\audio-models\logs\cosy_test.wav
```
> **首次 /tts 会加载模型，要 2~4 分钟，别超时误判。** 上次实测一次零样本合成 232s（RTF 8.6，CPU 偏慢但能跑）。

**零样本克隆（上传参考音频）：**
```powershell
curl.exe -X POST http://127.0.0.1:8897/tts -F "text=用你的声音合成" -F "ref_audio=@C:\your\voice.wav" `
  -o I:\GitHub\audio-models\logs\cosy_clone.wav
```
参考音频要 **10~30 秒清晰人声**，`ref_text`（若有）尽量与音频内容一致。

### 4.7 本 agent 的坑（最重要，全来自上次真实部署）

- **依赖要逐层补**：CosyVoice 的 import 链很长，`cosyvoice.dataset.processor` 会连环要
  `pyarrow / pypinyin / pyworld / rich / wget / inflect / phonemizer`。别一次全装完再测，容易漏。
  漏了哪个就 `pip install 那个` 再 import 一次。
- **`pynini` 跳过**：`WeTextProcessing` 依赖 `pynini`，本地编译会卡死且 CPU 推理用不到。
  用 `wetext` 前端（server 日志里会打 `use wetext frontend`）即可，**不要装 pynini / prophetnet / paddlepaddle / paddleocr**。
- **`huggingface_hub` 锁 0.34.4**：匹配 `transformers==4.57` 的 `<1.0` 约束。matcha/diffusers 需要
  新版 huggingface_hub 的符号，但**本地加载用不到**，用仓库里现成的 `cosyvoice\hf_stub.py` monkey-patch 兜底
  （server.py 已 `sys.path` 指向并 `import hf_stub`）。
- **`torchcodec` 别装 / 别依赖它**：torchaudio 2.11 默认走 torchcodec 读 wav，但 torchcodec 的
  `libtorchcodec_core4.dll` 与本机 torch 不匹配会 `OSError: Could not load this library`。
  仓库已用 `cosyvoice\patch_loadwav.py` 把 `cosyvoice_pkg/cosyvoice/utils/file_utils.py` 的 `load_wav`
  改成**直接用 soundfile 读**（绕过 torchaudio backend）。**clone 后必须跑一次**：
  ```powershell
  .\.venv\Scripts\python.exe I:\GitHub\audio-models\cosyvoice\patch_loadwav.py
  ```
  并 `pip install soundfile`。否则一合成就 `ImportError: TorchCodec is required`。
- **`diffusers` 的 LoRA FutureWarning** 是无害的，看到 `install peft` 提示可 `pip install peft`（已含在 4.4）。
- **GPU 提速（可选）**：当前用 CPU torch，RTF 高。若要快，把 `cosyvoice\.venv` 的 torch 换 cu126：
  ```powershell
  .\.venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126
  ```
  换完重跑 4.6 验证仍 ok。
- **model/ 与 cosyvoice_pkg/ 都不入库**（.gitignore 排除）。clone 后这一节 4.2/4.3/4.5 必须重做。

---

## 5. Web 客户端（:8890）

依赖 1-4 的端口都活着才完整可用（否则 health 是 `degraded`，但页面能开，缺的引擎灰着）。

### 5.1 无需单独 venv

`web\` 复用 `kokoro\.venv` 跑（只用到标准库 `http.server` + `urllib`）。

### 5.2 启动（proxy 模式，同源无跨域）

```powershell
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\web\web_server.py 8890 proxy
```

```powershell
curl.exe http://127.0.0.1:8890/__proxy/health
```
期望（5 个全活）：
```json
{"status":"ok","tts":{...},"asr":{...},"edge":{...},"cosy":{...}}
```
有后端没起时 `status` 会是 `"degraded"`，对应字段为 `null`，这是**设计行为**，不是错。

### 5.3 前端多引擎验证（开浏览器或 curl 子路由）

```powershell
# Kokoro 音色（原路由仍在）
curl.exe http://127.0.0.1:8890/__proxy/voices
# Edge 子路由
curl.exe http://127.0.0.1:8890/__proxy/edge/voices
# Cosy 子路由
curl.exe http://127.0.0.1:8890/__proxy/cosy/voices
```
期望：分别返回 Kokoro 音色、14 个 Edge 中文 Neural、Cosy 的 2 个 preset。

浏览器打开 `http://127.0.0.1:8890`，TTS 页顶部有「TTS 引擎」下拉（Kokoro/EdgeTTS/CosyVoice），
选 CosyVoice 会展开「参考音频」上传框（不传则用 preset）。

### 5.4 本 agent 的坑

- **静态模式要 CORS**：`web_server.py 8890 static` 让前端直连各端口，浏览器会拦跨域。**默认用 proxy 模式**。
- **旧 Service Worker 缓存**：前端会自动 `unregister()` 旧 SW（index.html 里有这段），这是解决「合成 405」的
  关键，**别删**。clone 后首次打开若还是旧行为，硬刷新一次（DevTools → 取消勾 Offline）。
- **端口被占**：若 8890 被占，`web_server.py` 会 `EADDRINUSE`。`manage.py stop` 或手动 taskkill 占 8890 的 PID。

---

## 6. 全链路验证（agent 收尾必跑）

5 个服务都起来后，跑一次端到端：

```powershell
# 用 Kokoro 合成 → SenseVoice 转写 → 校验一致
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\test_services.py
```
期望：`[PASS]`。

再快速冒烟其余引擎：
```powershell
curl.exe -s http://127.0.0.1:8896/health
curl.exe -s http://127.0.0.1:8897/health      # 首次会触发模型加载, 等 2-4 分钟
curl.exe -s http://127.0.0.1:8890/__proxy/edge/voices
```

---

## 7. manage.py 一键管理（日常就用这个）

`manage.py` 已纳入全部 5 个服务（启动顺序 kokoro→sensevoice→edge→cosy→web；停止逆序）。

```powershell
# 一键起全部（已运行则跳过, 后台 + 日志到 logs\）
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py start

# 看状态
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py status
# 期望 5 行全「运行中」

# 一键停 / 重启
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py stop
I:\GitHub\audio-models\kokoro\.venv\Scripts\python.exe I:\GitHub\audio-models\manage.py restart
```

> **注意**：`manage.py start` 会等每个端口起来才继续，**CosyVoice 首次启动会卡在「等待就绪」2~4 分钟**（加载模型），
> 这是正常的，别中途 Ctrl-C。日志在 `logs\cosy.log` / `logs\cosy.err.log`。

---

## 8. 常见故障速查（agent 遇错先查这里）

| 现象 | 原因 | 处置 |
|---|---|---|
| `edge /tts` 报 403 / `WSServerHandshakeError` | edge-tts < 7 | `pip install "edge-tts>=7.0"` 重装 |
| `edge` 能连但出 0 字节 / mp3 转 wav 失败 | 缺 ffmpeg | 确认 `C:\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe` 在 |
| `cosy` import 报 `No module named 'pyarrow'/'pyworld'/'rich'...` | 依赖没补全 | 见 §4.4，逐个补 |
| `cosy` 合成报 `TorchCodec is required` | load_wav 走 torchaudio backend | 跑 §4.7 的 `patch_loadwav.py` + 装 soundfile |
| `cosy` 报 `PytorchStreamReader failed reading zip` | llm.pt 下载中断 | 删 `model\llm.pt` 重跑 `dl_model.py` |
| `cosy` 报 `Could not load libtorchcodec_core4.dll` | 装了 torchcodec 但 DLL 不匹配 | 别依赖 torchcodec，走 soundfile patch |
| `cosy` 报 `ModuleNotFoundError: matcha` | Matcha 子模块没拉 | 见 §4.3 |
| Kokoro 只有 4 个中文音色 | 设计如此 | 用 Edge/Cosy 补，别再去拉 hex10（会 401） |
| 直连 github/huggingface 超时/重置 | 本机网络限制 | GitHub 走 ghproxy.net，HF 走 hf-mirror + `HF_ENDPOINT` |
| web 页面「合成 405」 | 旧 Service Worker 缓存了过期 config.js | 硬刷新；index.html 会自动注销旧 SW |
| web health 是 `degraded` | 有后端没起 | 对照 §6 看哪个 889x 没活 |
| `pip` 装包慢 | 用了官方源 | 加 `-i https://mirrors.aliyun.com/pypi/simple/` |

---

## 9. 目录结构（clone 后的实际布局）

```
audio-models/
├─ manage.py                  # 5 服务统一管理 (start/stop/restart/status)
├─ rebuild_venvs.bat          # 一键重建 4 个 venv+依赖 (不含权重/源码, 双击跑)
├─ AGENTS-DEPLOY.md           # 本手册 (给 agent 的无人值守部署指南)
├─ test_services.py           # Kokoro→SenseVoice 端到端自检
├─ .gitignore                 # 排除所有 venv / 权重 / 源码包 / logs
├─ kokoro/    .venv*  server.py  test_kokoro.py
│           install_local_torch.py  download_torch.py  download_torchaudio.py
├─ sensevoice/  .venv*  server.py  test_sensevoice.py
├─ edge/      .venv*  server.py                    # EdgeTTS 8896
├─ cosyvoice/ .venv*  server.py  hf_stub.py  patch_loadwav.py
│           dl_model.py  dl_blanken.py  setup_cosy.py  probe.py  test_http.py
│           cosyvoice_pkg/   (源码+Matcha, 不入库)
│           model/           (权重~4.5GB + CosyVoice-BlankEN, 不入库)
├─ web/       index.html  web_server.py  config.js  sw.js  icon.svg
└─ logs/      *.log / *.err.log (运行时, 不入库)
```

> `*` 表示该目录由 `.gitignore` 排除，clone 后需按本手册 §1-§4 重建。

---

## 10. 给 agent 的最终验收清单（全勾才算部署成功）

```
[ ] kokoro   8898  /health 返回 pipelines [a,z]，/tts 出非空 wav
[ ] sensevoice 8899 /health model_loaded=true，/transcribe 出文本
[ ] edge     8896  /health voices=14，/tts 出非空 wav
[ ] cosy     8897  /health 返回 presets，/tts preset 合成出非空 wav（首次 2-4 分钟）
[ ] web      8890  /__proxy/health 五路全 ok；浏览器 TTS 页能切 Kokoro/Edge/Cosy
[ ] manage.py status 五行全「运行中」
[ ] test_services.py 输出 [PASS]
```

全绿即完成。任何一项不过，回到对应 § 的「本 agent 的坑」小节逐条对照。
