# -*- coding: utf-8 -*-
"""本地音频模型 Web 客户端 — 静态服务 + 可选反向代理

启动:
    python web_server.py            # 默认 0.0.0.0:8890,静态模式
    python web_server.py 8891       # 自定义端口
    python web_server.py 8890 proxy # 反向代理模式(浏览器同源访问,最稳)

两种模式:
  静态模式: 前端直连 127.0.0.1:8898(TTS)和 127.0.0.1:8899(ASR),依赖 CORS。
  代理模式: 前端请求 8890/tts、8890/transcribe 等,由本服务转发到两个后端,
            同源无跨域,且能拿到真实错误。

前端会自动检测: 若页面来自 8890 端口则走代理,否则直连。
"""
import os
import sys
import json
import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8890
MODE = sys.argv[2] if len(sys.argv) > 2 else "static"

TTS = "http://127.0.0.1:8898"
ASR = "http://127.0.0.1:8899"


def write_config():
    """根据模式生成前端要读的配置。"""
    if MODE == "proxy":
        cfg = {"mode": "proxy", "tts_base": "/__proxy/tts", "asr_base": "/__proxy/asr"}
    else:
        cfg = {"mode": "static", "tts_base": TTS, "asr_base": ASR}
    with open(os.path.join(WEB_DIR, "config.js"), "w", encoding="utf-8") as f:
        f.write("window.__APICFG__ = " + json.dumps(cfg, ensure_ascii=False) + ";\n")
    return cfg


# 转发到后端的路由前缀(代理模式下浏览器只看到这些短路径,经本服务转发)
PROXY_TTS = {"/__proxy/tts": "/tts", "/__proxy/voices": "/voices"}
PROXY_ASR = {"/__proxy/transcribe": "/transcribe"}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_DIR, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    # ---------- 代理模式 ----------
    def do_GET(self):
        if MODE == "proxy" and self.path in PROXY_TTS:
            return self._proxy_to(TTS, PROXY_TTS[self.path])
        if MODE == "proxy" and self.path in PROXY_ASR:
            return self._proxy_to(ASR, PROXY_ASR[self.path])
        return super().do_GET()

    def do_POST(self):
        if MODE == "proxy" and self.path in PROXY_TTS:
            return self._proxy_to(TTS, PROXY_TTS[self.path])
        if MODE == "proxy" and self.path in PROXY_ASR:
            return self._proxy_to(ASR, PROXY_ASR[self.path])
        # 静态模式: POST 没有静态意义
        self.send_response(405)
        self.end_headers()

    def _proxy_to(self, base, path):
        target = base + path
        headers = {}
        for h in ("Content-Type", "Authorization", "Accept"):
            v = self.headers.get(h)
            if v:
                headers[h] = v
        # 读取请求体(POST 上传的 multipart 或 JSON)
        body = None
        cl = self.headers.get("Content-Length")
        if cl:
            body = self.rfile.read(int(cl))
        method = "POST" if body is not None else "GET"
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

    def log_message(self, *a):
        pass  # 静默


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    write_config()
    print(f"音频模型 Web 客户端  模式={MODE}  http://127.0.0.1:{PORT}")
    print(f"  TTS 后端: {TTS}")
    print(f"  ASR 后端: {ASR}")
    if MODE == "proxy":
        print("  代理转发: /__proxy/tts /__proxy/voices /__proxy/transcribe")
    httpd = ThreadingServer(("0.0.0.0", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
