# -*- coding: utf-8 -*-
"""分块下载 torch 2.5.1 (CPU 版, cp312 win_amd64)
支持断点续传(检查已有 .part 文件),下载完校验并安装。
用法: python download_torch.py
"""
import os
import sys
import json
import hashlib
import urllib.request
import subprocess

# 从 PyPI 查询 torch 2.5.1 cp312 win_amd64 的下载地址与 sha256
url = "https://pypi.org/pypi/torch/2.5.1/json"
data = json.load(urllib.request.urlopen(url, timeout=30))
target = None
for u in data["urls"]:
    if u["filename"] == "torch-2.5.1-cp312-cp312-win_amd64.whl":
        target = u
        break
assert target, "未找到 torch-2.5.1-cp312-cp312-win_amd64.whl"
dl_url = target["url"]
want_sha = target["digests"]["sha256"]
print(f"目标: {target['filename']}  预期 sha256={want_sha}")

dest = r"I:\GitHub\audio-models\wheels"
os.makedirs(dest, exist_ok=True)
part = os.path.join(dest, "torch-2.5.1-cp312-cp312-win_amd64.whl.part")
final = part.replace(".part", ".whl")

existing = os.path.getsize(part) if os.path.exists(part) else 0
print(f"已有进度: {existing/1e6:.1f} MB / 约 700 MB (如中断会续传)")

req = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
if existing:
    req.add_header("Range", f"bytes={existing}-")
    resp = urllib.request.urlopen(req, timeout=120)
    status = resp.status
    mode = "ab"
    print(f"续传 HTTP {status}")
else:
    resp = urllib.request.urlopen(req, timeout=120)
    status = resp.status
    mode = "wb"
    total = int(resp.headers.get("Content-Length", 0))
    print(f"HTTP {status}  总大小约 {total/1e6:.1f} MB")

chunk = 1 << 20  # 1 MB
with open(part, mode) as f:
    got = existing
    while True:
        b = resp.read(chunk)
        if not b:
            break
        f.write(b)
        got += len(b)
        print(f"\r{got/1e6:8.1f} MB", end="", flush=True)
print(f"\n下载完成: {got/1e6:.1f} MB")

# 校验 sha256
h = hashlib.sha256()
with open(part, "rb") as f:
    for b in iter(lambda: f.read(1 << 20), b""):
        h.update(b)
actual = h.hexdigest()
print(f"实际 sha256={actual}")
if actual != want_sha:
    print("校验失败!保留 .part 文件,稍后重试")
    sys.exit(1)

os.replace(part, final)
print(f"已移动到 {final}")

# 安装 torch + torchaudio + kokoro 依赖 + 本地 torch wheel
py = sys.executable
print("开始安装 torch(本地 wheel)+ kokoro ...")
r = subprocess.run([py, "-m", "pip", "install", "-q", "--no-index", "--no-deps", final])
if r.returncode != 0:
    print("torch wheel 安装失败")
    sys.exit(1)
r = subprocess.run([py, "-m", "pip", "install", "-q", "torchaudio==2.5.1"])
if r.returncode != 0:
    print("torchaudio 安装失败(若网络不稳可重试本脚本)")
    sys.exit(1)
r = subprocess.run([py, "-m", "pip", "install", "-q", "kokoro>=0.9.2", "soundfile"])
if r.returncode != 0:
    print("kokoro 安装失败")
    sys.exit(1)
print("安装完成!")
subprocess.run([py, "-c", "import torch, kokoro; print('torch', torch.__version__); print('kokoro OK')"])
