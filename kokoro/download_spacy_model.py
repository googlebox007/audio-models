# -*- coding: utf-8 -*-
"""下载 spacy en_core_web_sm 模型(从 GitHub spacy release), 断点续传
"""
import os
import sys
import time
import hashlib
import urllib.request
import subprocess

PY = sys.executable

# spacy 3.8.x 对应的 en_core_web_sm 版本
# 从 https://github.com/explosion/spacy-models/releases 下载
# en_core_web_sm-3.8.0.tar.gz
URL = "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
SHA256 = None  # 不校验,直接装
DEST = r"I:\GitHub\audio-models\wheels"
os.makedirs(DEST, exist_ok=True)
final = os.path.join(DEST, "en_core_web_sm-3.8.0-py3-none-any.whl")
part = final + ".part"

if os.path.exists(final):
    print("已存在,跳过下载")
else:
    for attempt in range(1, 8):
        existing = os.path.getsize(part) if os.path.exists(part) else 0
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
            if existing:
                req.add_header("Range", f"bytes={existing}-")
                resp = urllib.request.urlopen(req, timeout=120)
                mode = "ab"
                if attempt == 1:
                    print(f"续传,已有 {existing/1e6:.1f} MB")
            else:
                resp = urllib.request.urlopen(req, timeout=120)
                mode = "wb"
                total = int(resp.headers.get("Content-Length", 0))
                if attempt == 1:
                    print(f"下载约 {total/1e6:.1f} MB")
            with open(part, mode) as f:
                got = existing if mode == "ab" else 0
                while True:
                    b = resp.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    print(f"\r  {got/1e6:8.1f} MB", end="", flush=True)
                print()
            break
        except Exception as e:
            print(f"\n  第{attempt}次中断: {e}")
            if attempt == 7:
                print("下载失败")
                sys.exit(1)
            time.sleep(3)
    os.replace(part, final)

print("安装 en_core_web_sm...")
r = subprocess.run([PY, "-m", "pip", "install", "-q", "--no-index", "--no-deps", final])
if r.returncode != 0:
    # 回退允许网络
    r = subprocess.run([PY, "-m", "pip", "install", "-q", final])
print("完成" if r.returncode == 0 else "安装失败")

# 验证
r = subprocess.run([PY, "-c",
    "import spacy, spacy.util; print('en_core_web_sm:', spacy.util.is_package('en_core_web_sm'))"
])
sys.exit(0)
