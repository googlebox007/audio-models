# -*- coding: utf-8 -*-
"""EdgeTTS 中文音色扩充服务 (端口 8896)

edge-tts 6.1.11 自带 14 个中文 Neural 音色(晓晓/云希/云阳/云健/晓懿/
云夏/辽北/陕小妮/港 HiuGaai/HiuMaan/WanLung/台 HsiaoChen/HsiaoYu/云哲),
比 Kokoro 中文 4 个音色多得多, 即开即用。

API:
    GET  /voices   -> 可用音色列表 (ShortName + 描述)
    POST /tts      -> 合成 (body: {text, voice, rate, pitch, vol})
                      返回 audio/mp3 (edge-tts 原生输出)
    GET  /health   -> 健康检查

voice 取值: 任意 ShortName, 如 zh-CN-XiaoxiaoNeural
rate/pitch/vol 格式: "+0%", "+10Hz", "-20%"
"""
import os
import sys
import json
import asyncio
import io
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import edge_tts

PORT = int(os.environ.get("PORT", 8896))
app = FastAPI(title="EdgeTTS 中文音色扩充")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 固定中文音色(避免每次 list_voices 走网络)
ZH_VOICES = [
    "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunjianNeural",
    "zh-CN-YunxiNeural", "zh-CN-YunxiaNeural", "zh-CN-YunyangNeural",
    "zh-CN-liaoning-XiaobeiNeural", "zh-CN-shaanxi-XiaoniNeural",
    "zh-HK-HiuGaaiNeural", "zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural",
    "zh-TW-HsiaoChenNeural", "zh-TW-HsiaoYuNeural", "zh-TW-YunJheNeural",
]
VOICE_NAMES = {
    "zh-CN-XiaoxiaoNeural": "晓晓 (中·女)", "zh-CN-XiaoyiNeural": "晓懿 (中·女)",
    "zh-CN-YunjianNeural": "云健 (中·男)", "zh-CN-YunxiNeural": "云希 (中·男)",
    "zh-CN-YunxiaNeural": "云夏 (中·男)", "zh-CN-YunyangNeural": "云阳 (中·男)",
    "zh-CN-liaoning-XiaobeiNeural": "晓北·辽宁 (中·女)", "zh-CN-shaanxi-XiaoniNeural": "小妮·陕西 (中·女)",
    "zh-HK-HiuGaaiNeural": "希嘉 (港·女)", "zh-HK-HiuMaanNeural": "希雯 (港·女)",
    "zh-HK-WanLungNeural": "文龙 (港·男)", "zh-TW-HsiaoChenNeural": "晓辰 (台·女)",
    "zh-TW-HsiaoYuNeural": "晓宇 (台·女)", "zh-TW-YunJheNeural": "云哲 (台·男)",
}


class TTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    vol: str = "+0%"


@app.get("/health")
def health():
    return {"status": "ok", "backend": "edge-tts", "voices": len(ZH_VOICES)}


@app.get("/voices")
def voices():
    out = []
    for v in ZH_VOICES:
        out.append({"id": v, "name": VOICE_NAMES.get(v, v)})
    return {"voices": out}


def _mp3_to_wav_bytes(mp3: bytes) -> bytes:
    """edge-tts 输出 mp3, 浏览器 audio 不保证支持, 统一转 24kHz 单声道 wav。

    优先用 ffmpeg(若装了); 否则回退用 python 内置 mp3 解码器(可能没装)。
    实在都不行就返回原 mp3, 前端加类型头也能播。
    """
    import subprocess, shutil
    if shutil.which("ffmpeg") or shutil.which("ffmpeg.exe"):
        try:
            p = subprocess.run(
                ["ffmpeg", "-i", "pipe:0", "-f", "wav", "-ar", "24000",
                 "-ac", "1", "-acodec", "pcm_s16le", "pipe:1"],
                input=mp3, capture_output=True, timeout=60)
            if p.returncode == 0 and p.stdout:
                return p.stdout
        except Exception:
            pass
    # 没有 ffmpeg: 直接回 mp3, 前端按 mp3 处理
    return None


@app.post("/tts")
async def tts(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(400, "text 不能为空")
    try:
        voice = req.voice if req.voice in ZH_VOICES else "zh-CN-XiaoxiaoNeural"
        communicate = edge_tts.Communicate(
            req.text, voice, rate=req.rate, pitch=req.pitch, volume=req.vol)
        # 收集 mp3 分片
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        mp3 = buf.getvalue()
        if not mp3:
            raise HTTPException(500, "edge-tts 返回空")
        wav = _mp3_to_wav_bytes(mp3)
        if wav:
            return StreamingResponse(io.BytesIO(wav), media_type="audio/wav",
                                     headers={"Content-Disposition": 'attachment; filename="edge.wav"'})
        # 无 ffmpeg: 回 mp3
        return StreamingResponse(io.BytesIO(mp3), media_type="audio/mpeg",
                                 headers={"Content-Disposition": 'attachment; filename="edge.mp3"'})
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
