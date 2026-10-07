import subprocess, sys, os

venv = r"I:\GitHub\audio-models\cosyvoice\.venv\Scripts"
pip = os.path.join(venv, "pip.exe")
py = os.path.join(venv, "python.exe")

pkgs = [
    "funasr>=1.3.0",
    "openai-whisper",
    "onnxruntime",
    "hypercorn",
    "lightning",
    "transformers==4.57.1",
    "modelscope",
]

print("=== pip install cosyvoice deps ===")
r = subprocess.run(
    [py, "-m", "pip", "install", "-i", "https://mirrors.aliyun.com/pypi/simple/"] + pkgs,
    capture_output=True, text=True
)
print(r.stdout[-1500:] if r.stdout else "")
if r.returncode != 0:
    print("pip stderr:", r.stderr[-1500:])
print("pip rc:", r.returncode)

# 下载 CosyVoice2 权重到本地
print("\n=== 下载 CosyVoice2-0.5B 权重 ===")
code = """
import os, requests, urllib.request

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
DEST = r"I:\\GitHub\\audio-models\\cosyvoice\\model"
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

for f in files:
    dst = os.path.join(DEST, f)
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        print(f"  skip {f} ({os.path.getsize(dst)/1e6:.0f} MB)")
        continue
    url = f"https://hf-mirror.com/{repo}/resolve/main/{f}"
    print(f"  downloading {f} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as out:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        print(f"  done {f} ({os.path.getsize(dst)/1e6:.0f} MB)")
    except Exception as e:
        print(f"  FAIL {f}: {e}")

# CosyVoice-BlankEN (tokenizer 用)
sub = "CosyVoice-BlankEN"
dst_dir = os.path.join(DEST, sub)
os.makedirs(dst_dir, exist_ok=True)
for f in ["config.json", "configuration.json"]:
    url = f"https://hf-mirror.com/{repo}/resolve/main/{sub}/{f}"
    dst = os.path.join(dst_dir, f)
    if not (os.path.exists(dst) and os.path.getsize(dst) > 100):
        print(f"  downloading {sub}/{f}")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r, open(dst, "wb") as out:
                out.write(r.read())
            print(f"  done {sub}/{f}")
        except Exception as e:
            print(f"  FAIL {sub}/{f}: {e}")

print("=== download complete ===")
"""
with open(r"I:\GitHub\audio-models\cosyvoice\download_model.py", "w", encoding="utf-8") as fh:
    fh.write(code)

r2 = subprocess.run([py, r"I:\GitHub\audio-models\cosyvoice\download_model.py"],
                    capture_output=True, text=True, timeout=600)
print(r2.stdout)
if r2.returncode != 0:
    print("dl stderr:", r2.stderr[-1000:])
