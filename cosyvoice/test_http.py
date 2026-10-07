import urllib.request, time, uuid
t0 = time.time()
boundary = "----CosyBoundary" + uuid.uuid4().hex
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="text"\r\n\r\n'
    f"你好，这是 CosyVoice 中文克隆测试，声音来自零样本参考音频。\r\n"
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="preset"\r\n\r\n'
    f"zero_shot_prompt\r\n"
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="speed"\r\n\r\n'
    f"1.0\r\n"
    f"--{boundary}\r\n"
).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:8897/tts",
    data=body,
    method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
try:
    r = urllib.request.urlopen(req, timeout=300)
    out = r.read()
    print("POST /tts ->", r.status, r.headers.get("Content-Type"), len(out) // 1024, "KB")
    print("took", round(time.time() - t0, 1), "s")
except Exception as e:
    import traceback
    traceback.print_exc()
