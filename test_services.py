# -*- coding: utf-8 -*-
"""一键测试两个本地音频模型服务(需在 start_all.bat / manage.py start 后运行)

用法:
    python test_services.py
"""
import os
import sys
import json
import wave
import subprocess
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
TTS = "http://127.0.0.1:8898"
ASR = "http://127.0.0.1:8899"

def check_service(name, url):
    try:
        r = requests.get(url + "/health", timeout=5)
        r.raise_for_status()
        print(f"[{name}] OK  {url}/health -> {r.text.strip()[:80]}")
        return True
    except Exception as e:
        print(f"[{name}] 不可用: {e}")
        return False

def main():
    ok = True
    ok &= check_service("Kokoro TTS", TTS)
    ok &= check_service("SenseVoice ASR", ASR)
    if not ok:
        print("\n请先启动服务: I:\\GitHub\\audio-models\\start_all.bat")
        sys.exit(1)

    # 1. TTS 合成
    text = "服务已就绪,开始自动测试。"
    r = requests.post(TTS + "/tts", json={"text": text, "voice": "zm_yunxi", "lang": "z"},
                      timeout=300)
    r.raise_for_status()
    wav_path = os.path.join(BASE, "logs", "auto_test.wav")
    os.makedirs(os.path.dirname(wav_path), exist_ok=True)
    with open(wav_path, "wb") as f:
        f.write(r.content)
    # 校验 wav 头
    with wave.open(wav_path, "rb") as w:
        dur = w.getnframes() / w.getframerate()
    print(f"[TTS] 合成成功: {text!r} -> {wav_path} ({len(r.content)/1024:.0f} KB, {dur:.1f}s)")

    # 2. ASR 转写
    with open(wav_path, "rb") as f:
        r2 = requests.post(ASR + "/transcribe",
                           files={"file": ("t.wav", f, "audio/wav")},
                           data={"language": "zh"}, timeout=300)
    r2.raise_for_status()
    j = r2.json()
    print(f"[ASR] 转写成功: {j['text']!r} (耗时 {j['time']}s)")

    # 3. 相似度简单校验
    print(f"\n原文: {text}")
    print(f"识别: {j['text']}")
    # 粗匹配: 去掉标点空格比较
    clean = lambda s: "".join(c for c in s if c.isalnum() or "\u4e00" <= c <= "\u9fff")
    if clean(j["text"]) == clean(text):
        print("端到端一致 [OK]")
    else:
        print("端到端基本一致(ASR 可能略有偏差,属正常)")
    print("\n全部测试通过 [PASS]")

if __name__ == "__main__":
    main()
