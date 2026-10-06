# -*- coding: utf-8 -*-
"""SenseVoice-Small ASR 测试脚本

用法:
    python test_sensevoice.py <音频文件> [language]
language 可选: auto / zh / en / yue / ja / ko / nospeech
输出: 识别文本写入 output/<音频名>.txt,并打印带情绪/事件标记的结果
"""
import os
import sys
import time
import logging
import torch

logging.disable(logging.INFO)

AUDIO = sys.argv[1] if len(sys.argv) > 1 else ""
LANG = sys.argv[2] if len(sys.argv) > 2 else "auto"

if not AUDIO or not os.path.exists(AUDIO):
    print(f"用法: python test_sensevoice.py <音频文件> [language]")
    sys.exit(1)

device = "cuda:0" if torch.cuda.is_available() else "cpu"
print(f"加载 SenseVoice-Small(首次自动下载 FunAudioLLM/SenseVoiceSmall 约 900MB)... 设备={device}", flush=True)
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess

model = AutoModel(
    model="FunAudioLLM/SenseVoiceSmall",
    vad_model="fsmn-vad",
    vad_kwargs={"max_single_segment_time": 30000},
    device=device,
    hub="hf",
)
print("模型就绪", flush=True)

t0 = time.time()
res = model.generate(
    input=AUDIO,
    cache={},
    language=LANG,
    use_itn=True,
    batch_size_s=60,
    merge_vad=True,
    merge_length_s=15,
)
elapsed = time.time() - t0

text = rich_transcription_postprocess(res[0]["text"])
print(f"耗时 {elapsed:.1f}s")
print(f"识别文本: {text}")

os.makedirs("output", exist_ok=True)
out_name = os.path.splitext(os.path.basename(AUDIO))[0] + ".txt"
with open(os.path.join("output", out_name), "w", encoding="utf-8") as f:
    f.write(text)
print(f"已保存到 output/{out_name}")
