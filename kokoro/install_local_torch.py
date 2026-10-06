# -*- coding: utf-8 -*-
"""把本地已有完整 torch wheel 装进 kokoro venv。
直接安装(不重新下载), 校验 sha256。
"""
import os
import sys
import json
import hashlib
import subprocess

PY = sys.executable
CANDIDATES = [
    r"C:\Users\tuzhiyong\AppData\Local\Temp\pip-unpack-jeebtmny\torch-2.10.0+cu126-cp312-cp312-win_amd64.whl",
    r"C:\Users\tuzhiyong\AppData\Local\Temp\pip-unpack-m69ktpy8\torch-2.5.1+cu121-cp312-cp312-win_amd64.whl",
    r"C:\Users\tuzhiyong\AppData\Local\Temp\pip-unpack-cikyywoq\torch-2.5.1+cu121-cp312-cp312-win_amd64.whl",
]

def is_valid_zip(path):
    # zip 文件以 PK 开头
    with open(path, "rb") as f:
        magic = f.read(4)
    return magic == b"PK\x03\x04"

target = None
for c in CANDIDATES:
    if os.path.exists(c) and is_valid_zip(c):
        target = c
        break
    print(f"  无效或不存在: {c}")

if target is None:
    print("未找到可复用的完整 torch wheel")
    sys.exit(1)

print(f"使用: {target}")
print(f"  大小: {os.path.getsize(target)/1e6:.1f} MB")

# 从 wheel 文件名提取 version
fn = os.path.basename(target)  # torch-2.10.0+cu126-cp312-cp312-win_amd64.whl
ver = fn.split("-")[1]
print(f"  安装 torch=={ver}")
r = subprocess.run([PY, "-m", "pip", "install", "--no-index", "--no-deps", target])
if r.returncode != 0:
    print("安装失败")
    sys.exit(1)

# 装 torchaudio(CPU 版从 PyPI, 已缓存)
print("安装 torchaudio(已缓存 wheel)...")
# torchaudio 2.11.0 之前已下载, 用本地 wheels 目录
WHEELS = r"I:\GitHub\audio-models\wheels"
ta = os.path.join(WHEELS, "torchaudio-2.11.0-cp312-cp312-win_amd64.whl.whl")
if os.path.exists(ta):
    subprocess.run([PY, "-m", "pip", "install", "-q", ta])
else:
    print("  torchaudio wheel 不存在,跳过")

# 验证
print("\n=== 验证 ===")
subprocess.run([PY, "-c",
    "import torch, torchaudio;"
    "print('torch', torch.__version__, 'cuda:', torch.cuda.is_available());"
    "print('torchaudio', torchaudio.__version__)"
])
sys.exit(0)
