# -*- coding: utf-8 -*-
"""分块下载 torchaudio 2.11.0 (CPU 版, cp312 win_amd64)
支持断点续传,下载完校验 sha256 并安装到当前 venv。
"""
import os
import sys
import json
import hashlib
import urllib.request

url = "https://pypi.org/pypi/torchaudio/2.11.0/json"
data = json.load(urllib.request.urlopen(url, timeout=30))
target = None
for u in data["urls"]:
    if u["filename"] == "torchaudio-2.11.0-cp312-cp312-win_amd64.whl":
        target = u
        break
assert target, "未找到 torchaudio-2.11.0-cp312-cp312-win_amd64.whl"
dl_url = target["url"]
want_sha = target["digests"]["sha256"]
print(f"目标: {target['filename']}  预期 sha256={want_sha}")

dest = r"I:\GitHub\audio-models\wheels"
os.makedirs(dest, exist_ok=True)
part = os.path.join(dest, "torchaudio-2.11.0-cp312-cp312-win_amd64.whl.part")
final = part.replace(".part", ".whl")

existing = os.path.getsize(part) if os.path.exists(part) else 0
print(f"已有进度: {existing/1e6:.1f} MB")

req = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
if existing:
    req.add_header("Range", f"bytes={existing}-")
    resp = urllib.request.urlopen(req, timeout=120)
    mode = "ab"
    print(f"续传 HTTP {resp.status}")
else:
    resp = urllib.request.urlopen(req, timeout=120)
    mode = "wb"
    total = int(resp.headers.get("Content-Length", 0))
    print(f"HTTP {resp.status}  总大小约 {total/1e6:.1f} MB")

chunk = 1 << 20
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

r = __import__("subprocess").run([sys.executable, "-m", "pip", "install", "-q", "--no-index", "--no-deps", final])
if r.returncode != 0:
    print("torchaudio wheel 安装失败")
    sys.exit(1)
print("torchaudio 安装完成!")
