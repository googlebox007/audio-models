# -*- coding: utf-8 -*-
"""本地音频模型 Web 客户端 — 静态服务 + 反向代理

启动:
    python web_server.py            # 默认 0.0.0.0:8890, 静态模式
    python web_server.py 8891       # 自定义端口(静态)
    python web_server.py 8890 proxy # 反向代理模式(同源, 最稳)

两种模式:
  静态: 前端直连 8898(TTS)/8899(ASR), 依赖 CORS。
  代理: 前端同源访问 /__proxy/*, 本服务转发到两个后端。

代理路由(本服务直接响应, 不转发):
    /__proxy/tts         POST -> TTS /tts
    /__proxy/voices      GET  -> TTS /voices
    /__proxy/transcribe  POST -> ASR /transcribe
    /__proxy/health      GET  -> 聚合两个后端 /health
"""
import os
import sys
import json
import http.server
import socketserver
import urllib.request
import urllib.error

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8890
MODE = sys.argv[2] if len(sys.argv) > 2 else "static"

TTS = "http://127.0.0.1:8898"
ASR = "http://127.0.0.1:8899"
EDGE = "http://127.0.0.1:8896"   # EdgeTTS 14 个中文 Neural 音色
COSY = "http://127.0.0.1:8897"   # CosyVoice2-0.5B 零样本克隆

# 代理路由: 短路径 -> (后端 base, 真实路径, 允许的方法)
PROXY = {
    "/__proxy/tts":           (TTS, "/tts",        {"POST", "GET"}),  # GET: 回放最近一次合成(带 Range 拖动)
    "/__proxy/voices":        (TTS, "/voices",     {"GET"}),
    "/__proxy/transcribe":    (ASR, "/transcribe", {"POST"}),
    "/__proxy/health":        ("",  None,          {"GET"}),          # 聚合健康, 特殊处理
    "/__proxy/edge/tts":      (EDGE, "/tts",       {"POST"}),
    "/__proxy/edge/voices":   (EDGE, "/voices",    {"GET"}),
    "/__proxy/edge/health":   (EDGE, "/health",    {"GET"}),
    "/__proxy/cosy/tts":      (COSY, "/tts",       {"POST"}),
    "/__proxy/cosy/voices":   (COSY, "/voices",    {"GET"}),
    "/__proxy/cosy/health":   (COSY, "/health",    {"GET"}),
}

BODY_CACHE = os.path.join(WEB_DIR, "last_tts.bin")  # 最近一次 TTS 结果, 供 GET Range 回放


def parse_range(range_header, total):
    """解析 'bytes=a-b' / 'bytes=-N', 返回 (start, end)。非法返回 (None, None)。"""
    if not range_header or not range_header.startswith("bytes="):
        return None, None
    spec = range_header[6:].split(",")[0]
    if "-" in spec:
        a, _, b = spec.partition("-")
        a = int(a) if a.strip() else 0
        b = int(b) if b.strip() else total - 1
    else:
        a = int(spec)
        b = total - 1
    a = max(0, min(a, total - 1)) if total else 0
    b = max(0, min(b, total - 1)) if total else 0
    if a > b or total == 0:
        return None, None
    return a, b


def write_config():
    """生成前端 config.js。base 只含前缀, 动作由前端拼接。"""
    if MODE == "proxy":
        cfg = {"mode": "proxy", "tts_base": "/__proxy", "asr_base": "/__proxy",
               "edge_base": "/__proxy/edge", "cosy_base": "/__proxy/cosy"}
    else:
        cfg = {"mode": "static", "tts_base": TTS, "asr_base": ASR,
               "edge_base": EDGE, "cosy_base": COSY}
    with open(os.path.join(WEB_DIR, "config.js"), "w", encoding="utf-8") as f:
        f.write("window.__APICFG__ = " + json.dumps(cfg, ensure_ascii=False) + ";\n")
    return cfg


def health_aggregate():
    """聚合所有后端的 /health, 返回 (status_code, json_bytes)。"""
    result = {"tts": None, "asr": None, "edge": None, "cosy": None}
    for key, base in (("tts", TTS), ("asr", ASR), ("edge", EDGE), ("cosy", COSY)):
        try:
            with urllib.request.urlopen(base + "/health", timeout=5) as r:
                result[key] = json.loads(r.read())
        except Exception:
            result[key] = None
    ok = result["tts"] is not None and result["asr"] is not None
    body = json.dumps({"status": "ok" if ok else "degraded", **result}).encode()
    return (200 if ok else 503), body


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_DIR, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    # ---------- 代理路由 ----------
    def _proxy_handle(self):
        path = self.path.split("?")[0]
        if path not in PROXY:
            return False  # 不是代理路径, 交给静态处理

        base, real, methods = PROXY[path]
        if self.command not in methods:
            # 方法不允许: 回 405 + Allow 头(浏览器可识别)
            self.send_response(405)
            self.send_header("Allow", ", ".join(sorted(methods)))
            self.end_headers()
            return True

        if path == "/__proxy/health":
            code, body = health_aggregate()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return True

        # /__proxy/tts 的 GET: 从本地缓存回放最近一次合成结果, 支持 Range 拖动播放
        if path == "/__proxy/tts" and self.command == "GET":
            self._serve_tts_body()
            return True

        # 读请求体
        cl = self.headers.get("Content-Length")
        body = self.rfile.read(int(cl)) if cl else None
        headers = {}
        for h in ("Content-Type", "Authorization", "Accept"):
            v = self.headers.get(h)
            if v:
                headers[h] = v
        target = base + real
        method = self.command
        req = urllib.request.Request(target, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                out = r.read()
                ctype = r.headers.get("Content-Type", "application/octet-stream")
                self.send_response(r.status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(out)))
                cd = r.headers.get("Content-Disposition")
                if cd:
                    self.send_header("Content-Disposition", cd)
                self.end_headers()
                self.wfile.write(out)
                # 缓存 TTS 结果, 供后续 GET range 播放(拖动进度条)
                if path == "/__proxy/tts" and self.command == "POST":
                    with open(BODY_CACHE, "wb") as f:
                        f.write(out)
        except urllib.error.HTTPError as e:
            err = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)
        except Exception as e:
            msg = str(e).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
        return True

    def _serve_tts_body(self):
        """GET /__proxy/tts 带 Range: 从 last_tts.bin 切片, 支持音频播放器拖动。"""
        if not os.path.exists(BODY_CACHE):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        with open(BODY_CACHE, "rb") as f:
            data = f.read()
        total = len(data)
        start, end = parse_range(self.headers.get("Range"), total)
        if start is None:
            # 无 Range 或非法: 全量 200
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(total))
            self.end_headers()
            self.wfile.write(data)
        else:
            chunk = data[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
            self.send_header("Content-Length", str(len(chunk)))
            self.end_headers()
            self.wfile.write(chunk)

    def do_GET(self):
        if self._proxy_handle():
            return
        # PWA 已下线: 一律 404, 让残留旧 SW 自毁
        if self.path in ("/sw.js", "/manifest.webmanifest"):
            self.send_response(404)
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        if self._proxy_handle():
            return
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.end_headers()

    def log_message(self, *a):
        pass


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    write_config()
    print(f"音频模型 Web 客户端  模式={MODE}  http://127.0.0.1:{PORT}")
    print(f"  TTS(Kokoro): {TTS}  ASR: {ASR}  Edge: {EDGE}  Cosy: {COSY}")
    if MODE == "proxy":
        print("  代理路由: " + " ".join(sorted(PROXY)))
    httpd = ThreadingServer(("0.0.0.0", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
