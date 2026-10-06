# -*- coding: utf-8 -*-
"""Kokoro venv 完整依赖下载 + 安装(断点续传+sha256 校验+自动重试)
用法: 直接运行。已下好的 wheel 会跳过, 中断后重跑自动续传。
"""
import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.error
import subprocess

DEST = r"I:\GitHub\audio-models\wheels"
os.makedirs(DEST, exist_ok=True)
PY = sys.executable

# (包名, 版本或 None=latest稳定版)
PKGS = [
    ("kokoro", "0.9.4"),
    ("soundfile", None),
    ("fastapi", None),
    ("uvicorn", None),
    ("huggingface-hub", None),
    ("misaki", None),
    ("numba", None),
    ("einops", None),
    ("g2p-en", None),
    ("tqdm", None),
    ("requests", None),
]

def stable(v):
    return all(c in "0123456789." for c in v)

def keyf(v):
    return [int(x) if x.isdigit() else 0 for x in v.split(".")]

def get_files(name, ver_spec):
    if ver_spec is None:
        url = f"https://pypi.org/pypi/{name}/json"
        data = json.load(urllib.request.urlopen(url, timeout=30))
        ver = data["info"]["version"]
        # 完整索引包含 releases 字典
        files = data.get("releases", {}).get(ver, [])
        if not files:
            # 退化: 用单版本端点
            data2 = json.load(urllib.request.urlopen(
                f"https://pypi.org/pypi/{name}/{ver}/json", timeout=30))
            files = data2.get("urls", [])
    else:
        url = f"https://pypi.org/pypi/{name}/{ver_spec}/json"
        data = json.load(urllib.request.urlopen(url, timeout=30))
        ver = ver_spec
        # 单版本端点用 urls 字段
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
                if t in ("py3", "py2.py3") : return True
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
    for attempt in range(4):
        # 只用本地 wheel(不拉依赖)
        r = subprocess.run([PY, "-m", "pip", "install", "-q", "--no-index",
                            "--no-deps", "--find-links", DEST, final])
        if r.returncode == 0:
            print(f"  {name}=={ver} 安装成功(本地,无依赖)")
            return True
        # 允许从本地 wheels + 阿里云镜像拉依赖
        r = subprocess.run([PY, "-m", "pip", "install", "-q", "--no-index",
                            "--find-links", DEST, final])
        if r.returncode == 0:
            print(f"  {name}=={ver} 安装成功(含本地依赖)")
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

# 最后统一拉取残留依赖(从阿里云镜像, 网络不稳定则忽略)
if ok:
    print("\n拉取残留依赖(可能失败但不影响核心)...")
    subprocess.run([PY, "-m", "pip", "install", "-q",
                    "starlette filelock fsspec typing_extensions tqdm requests"
                    " pydantic pydantic_core python-multipart"],
                   check=False)

# 验证
print("\n=== 验证 import ===")
r = subprocess.run([PY, "-c",
    "import kokoro, soundfile, fastapi, uvicorn;"
    "print('kokoro OK'); print('soundfile OK'); print('fastapi OK'); print('uvicorn OK')"
])
sys.exit(0 if r.returncode == 0 and ok else 1)
