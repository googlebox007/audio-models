import urllib.request, os, time

DEST = r"I:\GitHub\audio-models\cosyvoice\model"
os.makedirs(DEST, exist_ok=True)

repo = "FunAudioLLM/CosyVoice2-0.5B"
files = [
    "campplus.onnx",
    "flow.decoder.estimator.fp32.onnx",
    "flow.pt",
    "hift.pt",
    "llm.pt",
    "speech_tokenizer_v2.batch.onnx",
    "speech_tokenizer_v2.onnx",
    "cosyvoice2.yaml",
    "config.json",
    "configuration.json",
]

t0 = time.time()
for f in files:
    dst = os.path.join(DEST, f)
    if os.path.exists(dst) and os.path.getsize(dst) > 100:
        print(f"  skip {f} ({os.path.getsize(dst)/1e6:.0f} MB)")
        continue
    url = f"https://hf-mirror.com/{repo}/resolve/main/{f}"
    print(f"  downloading {f} ...", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=600) as r, open(dst, "wb") as out:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        print(f"  done {f} ({os.path.getsize(dst)/1e6:.0f} MB, {time.time()-t0:.0f}s total)")
    except Exception as e:
        print(f"  FAIL {f}: {e}")

print(f"\n=== all done in {time.time()-t0:.0f}s ===")
