# -*- coding: utf-8 -*-
"""Kokoro-82M TTS 测试脚本(不依赖 soundfile,用 wave 写 wav)

用法:
    python test_kokoro.py "要朗读的文本" [voice]
默认 voice=am_michael(美国男声),输出到 output/sample.wav

常用音色:
    am_michael  美男  am_santa  美男
    af_bella    美女  af_heart  美女(模型卡片推荐)
    zm_yunxi    中文女声(普通话)
    zm_yunyang  中文男声
    bm_lewis    英男  bf_isabella 英女
"""
import os
import sys
import wave
import numpy as np
from kokoro import KPipeline

VOICE = sys.argv[2] if len(sys.argv) > 2 else "am_michael"
TEXT = sys.argv[1] if len(sys.argv) > 1 else "Hello! Kokoro runs locally on your GPU. No cloud, no API key."

# 选择语言:按文字判断;想强制某语言可改 lang_code
if any("\u4e00" <= c <= "\u9fff" for c in TEXT):
    lang_code = "z"  # 普通话
else:
    lang_code = "a"  # 美式英语

print(f"语言={lang_code} 音色={VOICE}")
print("加载模型(首次运行会自动下载 hexgrad/Kokoro-82M,约 320MB)...")
pipeline = KPipeline(lang_code=lang_code)

os.makedirs("output", exist_ok=True)
out = "output/sample.wav"
chunks = []
for i, (gs, ps, audio) in enumerate(pipeline(TEXT, voice=VOICE)):
    chunks.append(audio)
audio = np.concatenate(chunks)
print(f"已生成 {out} ({len(audio) / 24000:.1f}s)")

pcm = np.clip(audio * 32767, -32768, 32767).astype("<i2")
with wave.open(out, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(24000)
    w.writeframes(pcm.tobytes())
print(f"完成: {out} ({os.path.getsize(out)/1e6:.2f} MB)")
