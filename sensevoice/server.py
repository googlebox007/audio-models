# -*- coding: utf-8 -*-
"""SenseVoice-Small 本地 FastAPI 服务(ASR)

启动:
    python server.py            # 默认 0.0.0.0:8899
    python server.py 9001       # 自定义端口

API:
    POST /transcribe  上传音频文件(MP3/WAV/FLAC/OGG/任意 ffmpeg 可读格式)
                      参数: language(auto/zh/en/yue/ja/ko), itn(true/false)
                      返回: {"text": "...", "language": "...", "time": 1.2}
    GET  /health       -> 健康检查

示例:
    curl -F "file=@test.mp3" -F "language=auto" http://127.0.0.1:8899/transcribe
"""
import os
import time
import torch
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

PORT = int(os.environ.get("PORT", 8899))

app = FastAPI(title="SenseVoice-Small ASR")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

model = None

@app.on_event("startup")
def _load():
    global model
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"加载 SenseVoice-Small,设备={device} (首次运行自动下载约 900MB)...")
    model = AutoModel(
        model="FunAudioLLM/SenseVoiceSmall",
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device=device,
        hub="hf",
    )
    print("SenseVoice 就绪")

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    itn: bool = Form(True),
):
    if model is None:
        raise HTTPException(503, "模型尚未加载")
    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")
    tmp = f"upload_{int(time.time())}_{file.filename}"
    with open(tmp, "wb") as f:
        f.write(data)
    t0 = time.time()
    try:
        res = model.generate(
            input=tmp,
            cache={},
            language=language,
            use_itn=itn,
            batch_size_s=60,
            merge_vad=True,
            merge_length_s=15,
        )
        text = rich_transcription_postprocess(res[0]["text"])
        return {"text": text, "language": language, "time": round(time.time() - t0, 2)}
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
