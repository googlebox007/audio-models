# -*- coding: utf-8 -*-
"""从 PyPI 按单个包下载 wheel(支持断点续传+sha256 校验),
然后用 --no-index --no-deps 逐个安装到当前 venv。
用法: python pypi_fetch.py [包名=版本 ...] (默认列表见 PKGS)
"""
import os
import sys
import json
import hashlib
import urllib.request
import subprocess

DEST = r"I:\GitHub\audio-models\wheels"
os.makedirs(DEST, exist_ok=True)

PKGS = sys.argv[1:] or [
    "kokoro", "soundfile", "fastapi", "uvicorn",
]

def fetch(pkg_spec: str):
    # 解析 name==ver
    if "==" in pkg_spec:
        name, ver = pkg_spec.split("==")
    else:
        name, ver = pkg_spec, None
    url = f"https://pypi.org/pypi/{name}/{ver or 'latest'}/json"
    try:
        data = json.load(urllib.request.urlopen(url, timeout=30))
        version = data["info"]["version"]
    except urllib.error.HTTPError:
        # latest 端点 404 时退回 json 索引
        url = f"https://pypi.org/pypi/{name}/json"
        data = json.load(urllib.request.urlopen(url, timeout=30))
        # 取最新的 version
        ver_list = sorted(data["releases"].keys(), key=lambda v: [int(x) if x.isdigit() else x for x in v.replace("-", ".").split(".")])
        version = ver_list[-1]
        data = dict(data, info={"version": version})
        candidates = data["releases"][version]
        data["urls"] = candidates
    # 优先找 cp312 win_amd64,其次 py3-none-any
    candidates = [u for u in data["urls"] if u["filename"].endswith(".whl") or u["filename"].endswith(".tar.gz")]
    def score(u):
        fn = u["filename"]
        s = 0
        if "cp312" in fn and "win_amd64" in fn: s += 100
        elif "py3" in fn and "none" in fn and "any" in fn: s += 50
        elif "py3" in fn and "none" in fn: s += 20
        return s
    candidates.sort(key=score, reverse=True)
    target = candidates[0]
    print(f"  {name}=={version} -> {target['filename']} ({target['url']})")
    want_sha = target["digests"]["sha256"]
    part = os.path.join(DEST, target["filename"] + ".part")
    final = os.path.join(DEST, target["filename"])
    if os.path.exists(final):
        h = hashlib.sha256()
        with open(final, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        if h.hexdigest() == want_sha:
            print(f"  已有完整 wheel,跳过下载")
        else:
            os.remove(final)
    if not os.path.exists(final):
        existing = os.path.getsize(part) if os.path.exists(part) else 0
        req = urllib.request.Request(target["url"], headers={"User-Agent": "Mozilla/5.0"})
        if existing:
            req.add_header("Range", f"bytes={existing}-")
            resp = urllib.request.urlopen(req, timeout=120)
            mode = "ab"
            print(f"  续传,已有 {existing/1e6:.1f} MB")
        else:
            resp = urllib.request.urlopen(req, timeout=120)
            mode = "wb"
            total = int(resp.headers.get("Content-Length", 0))
            print(f"  下载约 {total/1e6:.1f} MB")
        chunk = 1 << 20
        with open(part, mode) as f:
            got = existing if mode == "ab" else 0
            while True:
                b = resp.read(chunk)
                if not b:
                    break
                f.write(b)
                got += len(b)
                print(f"\r  {got/1e6:8.1f} MB", end="", flush=True)
        print()
        h = hashlib.sha256()
        with open(part, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        if h.hexdigest() != want_sha:
            print(f"  校验失败!保留 {part} 稍后重试")
            return False
        os.replace(part, final)
    # 安装
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                        "--no-index", "--find-links", DEST,
                        f"{name}=={version}"])
    if r.returncode != 0:
        print(f"  {name} 安装失败")
        return False
    print(f"  {name}=={version} 安装成功")
    return True

ok = True
for p in PKGS:
    print(f"处理 {p}")
    if not fetch(p):
        ok = False
print("全部完成!" if ok else "部分失败,重新运行本脚本可续传")
sys.exit(0 if ok else 1)
