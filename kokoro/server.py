# -*- coding: utf-8 -*-
"""Kokoro-82M 本地 FastAPI 服务

启动:
    python server.py            # 默认 0.0.0.0:8898
    python server.py 9000       # 自定义端口

API:
    POST /tts   {"text": "...", "voice": "am_michael", "lang": "auto"}
                 -> audio/wav
    GET  /voices                          -> 音色列表
    GET  /health                          -> 健康检查

lang 取值: auto(按文字自动判断) 或 a/b/j/z/e/f/h/i/p 单字母语言码
"""
import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import io
import wave
import numpy as np
from kokoro import KPipeline

PORT = int(os.environ.get("PORT", 8898))

app = FastAPI(title="Kokoro-82M TTS")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LANGS = {"a": "American English", "b": "British English", "j": "Japanese",
         "z": "Mandarin", "e": "Spanish", "f": "French", "h": "Hindi",
         "i": "Italian", "p": "Brazilian Portuguese"}

_pipelines: dict = {}

def get_pipeline(lang: str) -> KPipeline:
    if lang not in _pipelines:
        _pipelines[lang] = KPipeline(lang_code=lang)
    return _pipelines[lang]

class TTSRequest(BaseModel):
    text: str
    voice: str = "am_michael"
    lang: str = "auto"
    speed: float = 1.0

@app.on_event("startup")
def _load_default():
    # 预加载常用管道,避免首个请求卡顿
    for lang in ("a", "z"):
        get_pipeline(lang)
    print("Kokoro 管道就绪:", list(_pipelines))

@app.get("/health")
def health():
    return {"status": "ok", "pipelines": list(_pipelines)}

@app.get("/voices")
def voices():
    """返回可用的音色列表。本地缓存 + Kokoro 内置官方音色。"""
    import glob
    # 1) 用户自定义音色(本地缓存)
    cache = os.path.join(os.path.expanduser("~"), ".kokoro")
    local = [os.path.basename(p) for p in glob.glob(os.path.join(cache, "voices", "*.pt"))]
    # 2) Kokoro 内置官方音色(随包下载)
    builtin = {
        "a": ["am_michael", "am_santa", "am_echo", "am_kore",
              "am_onyx", "am_river", "af_bella", "af_heart",
              "af_alva", "af_nicole", "am_santa_2"],
        "b": ["bm_george", "bm_lewis", "bm_frankie", "bm_santa",
              "bf_isabella", "bf_xenophy"],
        "j": ["js_speech"],
        "z": ["zm_yunxi", "zm_yunyang", "zf_xiaobei", "zf_xiaoxiao"],
    }
    available = set(local)
    for lang, names in builtin.items():
        # 只列出该语言管道已加载的音色,避免推荐未下载的
        if lang in _pipelines:
            available.update(names)
    return {"voices": sorted(available)}

@app.post("/tts")
async def tts(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(400, "text 不能为空")
    lang = req.lang
    if lang == "auto":
        if any("\u4e00" <= c <= "\u9fff" for c in req.text):
            lang = "z"
        elif any("\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff" for c in req.text):
            lang = "j"
        else:
            lang = "a"
    if lang not in LANGS:
        raise HTTPException(400, f"不支持的 lang={lang},可选: auto 或 {list(LANGS)}")
    try:
        pipeline = get_pipeline(lang)
        # 生成可能较慢,放到线程池避免阻塞
        def gen():
            chunks = []
            for gs, ps, audio in pipeline(req.text, voice=req.voice, speed=req.speed):
                chunks.append(audio)
            return chunks
        chunks = await asyncio.to_thread(gen)
        # 拼接 24kHz float32 mono,转 int16 wav
        arr = np.concatenate(chunks)
        pcm = np.clip(arr * 32767, -32768, 32767).astype("<i2")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm.tobytes())
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/wav",
                                 headers={"Content-Disposition": 'attachment; filename="tts.wav"'})
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
