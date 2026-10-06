# -*- coding: utf-8 -*-
"""补齐 Kokoro 的 transformers/tokenizers/httpx2(断点续传+sha256 校验)
"""
import os
import sys
import json
import time
import hashlib
import urllib.request
import subprocess

DEST = r"I:\GitHub\audio-models\wheels"
os.makedirs(DEST, exist_ok=True)
PY = sys.executable

# 指定版本(避免 transformers 5.x 与 huggingface-hub 2.1.1 不兼容)
PKGS = [
    ("transformers", "4.57.0"),
    ("tokenizers", "0.21.4"),
    ("httpx2", None),
    ("httpcore2", None),
    ("truststore", None),
    ("anyio", None),
    ("certifi", None),
    ("idna", None),
    ("regex", None),
    ("safetensors", None),
    ("fsspec", None),
    ("filelock", None),
    ("typing_extensions", None),
]

def get_files(name, ver_spec):
    if ver_spec is None:
        url = f"https://pypi.org/pypi/{name}/json"
        data = json.load(urllib.request.urlopen(url, timeout=30))
        ver = data["info"]["version"]
        files = data.get("releases", {}).get(ver, [])
        if not files:
            d2 = json.load(urllib.request.urlopen(
                f"https://pypi.org/pypi/{name}/{ver}/json", timeout=30))
            files = d2.get("urls", [])
    else:
        url = f"https://pypi.org/pypi/{name}/{ver_spec}/json"
        data = json.load(urllib.request.urlopen(url, timeout=30))
        ver = ver_spec
        files = data.get("urls", []) or data.get("releases", {}).get(ver, [])
    if not files:
        raise RuntimeError(f"{name}=={ver} 无发行文件")
    return ver, files

def pick_wheel(files):
    def supported(fn):
        if fn.endswith(".whl"):
            if "cp312" in fn and "win" in fn and "amd64" in fn: return True
            parts = fn.split("-")
            if len(parts) >= 4:
                t = parts[3]
                if t in ("py3", "py2.py3"): return True
                if "none" in t and "any" in t: return True
            if "py3" in fn and "none" in fn and "any" in fn: return True
            return False
        return False
    good = [u for u in files if supported(u["filename"])]
    if not good:
        return None
    def score(u):
        fn = u["filename"]
        if "cp312" in fn and "win" in fn: return 100
        return 50
    return sorted(good, key=score, reverse=True)[0]

def download(u, want_sha, retries=6):
    final = os.path.join(DEST, u["filename"])
    part = final + ".part"
    if os.path.exists(final):
        h = hashlib.sha256()
        with open(final, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        if h.hexdigest() == want_sha:
            print(f"    已存在: {u['filename']}")
            return final
        os.remove(final)
    for attempt in range(1, retries + 1):
        existing = os.path.getsize(part) if os.path.exists(part) else 0
        try:
            req = urllib.request.Request(u["url"], headers={"User-Agent": "Mozilla/5.0"})
            if existing:
                req.add_header("Range", f"bytes={existing}-")
                resp = urllib.request.urlopen(req, timeout=120)
                mode = "ab"
                if attempt == 1:
                    print(f"    续传 {u['filename']}, 已有 {existing/1e6:.1f} MB")
            else:
                resp = urllib.request.urlopen(req, timeout=120)
                mode = "wb"
                total = int(resp.headers.get("Content-Length", 0))
                if attempt == 1:
                    print(f"    下载 {u['filename']} 约 {total/1e6:.1f} MB")
            with open(part, mode) as f:
                got = existing if mode == "ab" else 0
                while True:
                    b = resp.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    print(f"\r    {got/1e6:8.1f} MB", end="", flush=True)
                print()
            break
        except Exception as e:
            print(f"\n    第{attempt}次下载中断: {e}")
            if attempt == retries:
                return None
            time.sleep(2)
    h = hashlib.sha256()
    with open(part, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    if h.hexdigest() != want_sha:
        print(f"    校验失败!保留 {part}")
        return None
    os.replace(part, final)
    return final

def install_wheel(final, name, ver):
    if not (final and os.path.exists(final)):
        print(f"  {name} 无 wheel,跳过")
        return False
    for attempt in range(3):
        r = subprocess.run([PY, "-m", "pip", "install", "-q", "--no-index",
                            "--no-deps", "--find-links", DEST, final])
        if r.returncode == 0:
            print(f"  {name}=={ver} 安装成功")
            return True
        print(f"  {name} 安装第{attempt+1}次失败,重试...")
        time.sleep(2)
    print(f"  {name} 安装失败")
    return False

ok = True
for name, ver_spec in PKGS:
    print(f"处理 {name}")
    try:
        ver, files = get_files(name, ver_spec)
    except Exception as e:
        print(f"  查询 {name} 失败: {e}")
        ok = False
        continue
    u = pick_wheel(files)
    if u is None:
        print(f"  {name} 无本平台可用 wheel,跳过")
        continue
    print(f"  {name}=={ver} -> {u['filename']}")
    final = download(u, u["digests"]["sha256"])
    if not install_wheel(final, name, ver):
        ok = False

# 补 transformers 残留依赖
print("\n补残留依赖...")
subprocess.run([PY, "-m", "pip", "install", "-q", "regex"], check=False)
subprocess.run([PY, "-m", "pip", "install", "-q", "safetensors"], check=False)
subprocess.run([PY, "-m", "pip", "install", "-q", "fsspec"], check=False)
subprocess.run([PY, "-m", "pip", "install", "-q", "filelock"], check=False)
subprocess.run([PY, "-m", "pip", "install", "-q", "typing_extensions"], check=False)

print("\n=== 验证 import kokoro ===")
r = subprocess.run([PY, "-c",
    "import kokoro; print('kokoro', kokoro.__version__)"
])
sys.exit(0 if r.returncode == 0 and ok else 1)
