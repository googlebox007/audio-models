# -*- coding: utf-8 -*-
"""补齐 Kokoro venv 缺失的依赖: 逐个下载 wheel 并安装(支持断点续传+重试)。
运行后会自动验证 import kokoro。
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

# 需要补齐的包(名称, 版本或 None=latest稳定版)
PKGS = [
    ("kokoro", "0.9.4"),
    ("fastapi", None),
    ("huggingface-hub", None),
]

def stable(v):
    return all(c in "0123456789." for c in v)

def keyf(v):
    return [int(x) if x.isdigit() else 0 for x in v.split(".")]

def get_latest(name):
    url = f"https://pypi.org/pypi/{name}/json"
    data = json.load(urllib.request.urlopen(url, timeout=30))
    vs = [v for v in data["releases"].keys() if stable(v)]
    if not vs:
        vs = list(data["releases"].keys())
    vs.sort(key=keyf)
    return data["info"]["version"], data["releases"]

def get_files(name, ver_spec):
    if ver_spec is None:
        latest, releases = get_latest(name)
        return latest, releases[latest]
    url = f"https://pypi.org/pypi/{name}/{ver_spec}/json"
    data = json.load(urllib.request.urlopen(url, timeout=30))
    return ver_spec, data["releases"][ver_spec]

def pick_wheel(files):
    def score(u):
        fn = u["filename"]
        if fn.endswith(".whl"):
            if "cp312" in fn and "win_amd64" in fn: return 100
            if "py3" in fn and "none" in fn and "any" in fn: return 50
            return 10
        return 1
    return sorted(files, key=score, reverse=True)[0]

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
                            "--find-links", DEST, final])
        if r.returncode == 0:
            print(f"  {name}=={ver} 安装成功(本地)")
            return True
        print(f"  {name} 本地安装第{attempt+1}次失败,尝试允许网络拉依赖...")
        r = subprocess.run([PY, "-m", "pip", "install", "-q", final])
        if r.returncode == 0:
            print(f"  {name}=={ver} 安装成功(含网络依赖)")
            return True
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
    print(f"  {name}=={ver} -> {u['filename']}")
    final = download(u, u["digests"]["sha256"])
    if not install_wheel(final, name, ver):
        ok = False

# 验证
print("\n=== 验证 import ===")
r = subprocess.run([PY, "-c",
    "import kokoro, soundfile, fastapi, uvicorn;"
    "print('kokoro', getattr(kokoro,'__version__','?')); print('fastapi OK'); print('uvicorn OK')"
])
sys.exit(0 if r.returncode == 0 and ok else 1)
