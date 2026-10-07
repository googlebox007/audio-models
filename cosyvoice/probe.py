import requests
r = requests.get('https://hf-mirror.com/api/models/FunAudioLLM/CosyVoice2-0.5B/tree/main', timeout=25)
if r.status_code == 200:
    for it in r.json():
        sz = it.get('size', 0)
        print(f"  {sz/1e9:6.2f} GB  {it['path']}")
else:
    print('tree status:', r.status_code, r.text[:120])
