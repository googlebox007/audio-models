# -*- coding: utf-8 -*-
"""CosyVoice2-0.5B TTS 服务 (端口 8897)
零样本克隆: 传 10~30 秒参考音频 + 文本, 用该声音合成。
内置 preset 音色(无需参考音频, 直接合成)。
"""
import os
import sys
import json
import time
import wave
import io
import tempfile
import shutil
import subprocess

MODEL_DIR = r"I:\GitHub\audio-models\cosyvoice\model"
PKG_DIR = r"I:\GitHub\audio-models\cosyvoice\cosyvoice_pkg"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.path.insert(0, PKG_DIR)
sys.path.insert(0, os.path.join(PKG_DIR, "third_party", "Matcha-TTS"))
# matcha 的 diffusers 需要 huggingface_hub 新符号; 本地加载用不到, stub 掉
sys.path.insert(0, r"I:\GitHub\audio-models\cosyvoice")
import hf_stub  # noqa: F401

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
import numpy as np
import torch

PORT = int(os.environ.get("PORT", 8897))
app = FastAPI(title="CosyVoice2-0.5B TTS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_cosyvoice = None
_lock = None

def get_model():
    global _cosyvoice, _lock
    import threading
    _lock = threading.Lock()
    if _cosyvoice is None:
        with _lock:
            if _cosyvoice is None:
                print("Loading CosyVoice2 model...", flush=True)
                from cosyvoice.cli.cosyvoice import CosyVoice2
                _cosyvoice = CosyVoice2(MODEL_DIR, load_jit=False, load_trt=False, load_vllm=False)
                print("CosyVoice2 model loaded.", flush=True)
    return _cosyvoice

# 内置 preset 参考音频(模型自带)
ASSET_DIR = os.path.join(PKG_DIR, "asset")
PRESETS = {}
if os.path.isdir(ASSET_DIR):
    for f in sorted(os.listdir(ASSET_DIR)):
        if f.endswith(".wav"):
            PRESETS[f.replace(".wav", "")] = os.path.join(ASSET_DIR, f)
print(f"Preset voices: {list(PRESETS.keys())}", flush=True)


def synth(text, ref_audio=None, preset=None, speed=1.0):
    """合成 text, 返回 24kHz mono float32 ndarray。"""
    model = get_model()
    # 选参考音频
    if ref_audio is not None:
        audio_path = ref_audio
    elif preset is not None:
        if preset not in PRESETS:
            raise HTTPException(400, f"未知 preset: {preset}, 可选: {list(PRESETS.keys())}")
        audio_path = PRESETS[preset]
    else:
        raise HTTPException(400, "ref_audio 或 preset 必选其一")

    results = []
    for chunk in model.inference_zero_shot(
        text, "你好",  # 目标文本 + prompt 文本(CosyVoice2 固定用 "你好" 即可)
        audio_path,
        speed=speed,
    ):
        results.append(chunk)
    if not results:
        raise HTTPException(500, "CosyVoice 未生成音频")

    # results: list of dict, 每个有 'tts_speech' (Tensor [1, samples])
    wave_chunks = []
    for item in results:
        w = item["tts_speech"]
        if w.ndim == 2:
            w = w[0]
        wave_chunks.append(w.detach().cpu().numpy())
    audio = np.concatenate(wave_chunks)
    return audio


def audio_to_wav_bytes(audio, sr=24000):
    pcm = np.clip(audio * 32767, -32768, 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    buf.seek(0)
    return buf


@app.get("/health")
def health():
    model = get_model()
    return {"status": "ok", "model": "cosyvoice2-0.5b", "presets": list(PRESETS.keys())}


@app.get("/voices")
def voices():
    """返回可用 preset 音色列表。"""
    out = []
    for name, path in PRESETS.items():
        out.append({"id": name, "name": name, "type": "preset"})
    return {"voices": out, "note": "零样本克隆: 传 ref_audio 可用任意人声"}


@app.post("/tts")
async def tts(
    text: str = Form(...),
    preset: str = Form(None),
    speed: float = Form(1.0),
    ref_audio: UploadFile = File(None),
):
    """
    零样本克隆合成:
    - text: 要合成的文本
    - preset: 内置音色 ID (如 "zero_shot_sp1")
    - speed: 语速倍率
    - ref_audio: 可选, 上传参考音频(10~30秒)覆盖 preset 音色
    返回 audio/wav
    """
    ref_path = None
    if ref_audio is not None:
        # 保存临时文件
        suffix = os.path.splitext(ref_audio.filename)[1] or ".wav"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(await ref_audio.read())
        tmp.close()
        ref_path = tmp.name

    try:
        audio = synth(text, ref_audio=ref_path, preset=preset, speed=speed)
        buf = audio_to_wav_bytes(audio)
        return StreamingResponse(buf, media_type="audio/wav",
                                 headers={"Content-Disposition": 'attachment; filename="cosyvoice.wav"'})
    finally:
        if ref_path and os.path.exists(ref_path):
            os.unlink(ref_path)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
