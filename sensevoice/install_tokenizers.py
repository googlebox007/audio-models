# -*- coding: utf-8 -*-
"""从本地 torch wheel 目录安装 tokenizers(与 kokoro venv 兼容)
"""
import os
import sys
import subprocess

PY = sys.executable
WHEEL = r"I:\GitHub\audio-models\wheels\tokenizers-0.22.1-cp312-cp312-win_amd64.whl"

if os.path.exists(WHEEL):
    print(f"安装 {os.path.basename(WHEEL)}")
    r = subprocess.run([PY, "-m", "pip", "install", "-q", "--no-index", "--no-deps", WHEEL])
    print("完成" if r.returncode == 0 else "失败")
else:
    print(f"wheel 不存在: {WHEEL}")
    # 回退到网络
    r = subprocess.run([PY, "-m", "pip", "install", "-q", "tokenizers==0.22.1"])
    print("网络安装完成" if r.returncode == 0 else "网络安装失败")

# 验证
r = subprocess.run([PY, "-c",
    "import tokenizers; print('tokenizers', tokenizers.__version__)"
])
sys.exit(0 if r.returncode == 0 else 1)
