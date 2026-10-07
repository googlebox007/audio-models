import urllib.request, os, time

DEST = r"I:\GitHub\audio-models\cosyvoice\model\CosyVoice-BlankEN"
os.makedirs(DEST, exist_ok=True)
repo = "FunAudioLLM/CosyVoice2-0.5B"

# 列出子目录所有文件
url = f"https://hf-mirror.com/api/models/{repo}/tree/main/CosyVoice-BlankEN"
print("listing:", url)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
data = urllib.request.urlopen(req, timeout=60).read()
import json
files = json.loads(data)
t0 = time.time()
for it in files:
    if it.get("type") != "file":
        continue
    f = it["path"].split("CosyVoice-BlankEN/")[1]
    sz = it.get("size", 0)
    dst = os.path.join(DEST, f)
    if os.path.exists(dst) and os.path.getsize(dst) == sz:
        print(f"  skip {f} ({sz//1e6:.0f} MB)")
        continue
    furl = f"https://hf-mirror.com/{repo}/resolve/main/CosyVoice-BlankEN/{f}"
    print(f"  downloading {f} ({sz//1e6:.0f} MB) ...", flush=True)
    rreq = urllib.request.Request(furl, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(rreq, timeout=600) as r, open(dst, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    print(f"  done {f} ({os.path.getsize(dst)//1e6:.0f} MB)")
print(f"all done in {time.time()-t0:.0f}s")
