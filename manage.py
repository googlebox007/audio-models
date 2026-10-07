# -*- coding: utf-8 -*-
"""管理本地音频服务: Kokoro(TTS :8898)、SenseVoice(ASR :8899)、
EdgeTTS(:8896)、CosyVoice2(:8897) 与 Web 客户端(:8890)。

用法:
    python manage.py start      # 启动全部服务(已运行则跳过,Web 最后起)
    python manage.py stop       # 停止全部服务(Web 先停)
    python manage.py restart    # 重启全部服务
    python manage.py status     # 查看运行状态
"""
import os
import sys
import time
import subprocess
import socket
import signal
import multiprocessing

BASE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

SERVICES = {
    "kokoro": {
        "name": "Kokoro TTS",
        "port": 8898,
        "venv": os.path.join(BASE, "kokoro", ".venv", "Scripts", "python.exe"),
        "script": os.path.join(BASE, "kokoro", "server.py"),
        "log": os.path.join(LOG_DIR, "kokoro.log"),
    },
    "sensevoice": {
        "name": "SenseVoice ASR",
        "port": 8899,
        "venv": os.path.join(BASE, "sensevoice", ".venv", "Scripts", "python.exe"),
        "script": os.path.join(BASE, "sensevoice", "server.py"),
        "log": os.path.join(LOG_DIR, "sensevoice.log"),
    },
    "edge": {
        "name": "EdgeTTS",
        "port": 8896,
        "venv": os.path.join(BASE, "edge", ".venv", "Scripts", "python.exe"),
        "script": os.path.join(BASE, "edge", "server.py"),
        "log": os.path.join(LOG_DIR, "edge.log"),
    },
    "cosy": {
        "name": "CosyVoice2",
        "port": 8897,
        "venv": os.path.join(BASE, "cosyvoice", ".venv", "Scripts", "python.exe"),
        "script": os.path.join(BASE, "cosyvoice", "server.py"),
        "log": os.path.join(LOG_DIR, "cosy.log"),
    },
    "web": {
        "name": "Web 客户端",
        "port": 8890,
        "venv": os.path.join(BASE, "kokoro", ".venv", "Scripts", "python.exe"),
        "script": os.path.join(BASE, "web", "web_server.py"),
        "log": os.path.join(LOG_DIR, "web.log"),
        "args": ["8890", "proxy"],   # web_server.py 接受端口+模式两个参数
    },
}

def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False

def port_listener(port):
    """返回占用该端口的 PID(若为 LISTENING 状态)"""
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].startswith("TCP"):
            local = parts[1]
            state = parts[3]
            pid = parts[4]
            if local.endswith(f":{port}") and state == "LISTENING":
                pids.add(pid)
    return pids

def start_service(key):
    svc = SERVICES[key]
    if port_open(svc["port"]):
        print(f"  [{svc['name']}] 已在运行 (port {svc['port']})")
        return True
    log = open(svc["log"], "ab", buffering=0)
    log.write(f"\n===== {time.ctime()} 启动 {svc['name']} =====\n".encode("gbk", "replace"))
    # Windows 下用 CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS 让子进程独立
    CREATE_NO_WINDOW = 0x08000000
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    proc = subprocess.Popen(
        [svc["venv"], svc["script"]] + svc.get("args", []),
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
        close_fds=True,
        cwd=os.path.dirname(svc["script"]),
    )
    print(f"  [{svc['name']}] 启动 PID={proc.pid}, 等待就绪...")
    # 等端口起来(模型加载可能 30s+)
    for _ in range(120):
        if port_open(svc["port"]):
            print(f"  [{svc['name']}] 就绪 port={svc['port']}")
            return True
        time.sleep(1)
    print(f"  [{svc['name']}] 启动后端口 {svc['port']} 仍未监听,见日志 {svc['log']}")
    return False

def stop_service(key):
    svc = SERVICES[key]
    pids = port_listener(svc["port"])
    if not pids:
        print(f"  [{svc['name']}] 未运行 (port {svc['port']})")
        return True
    for pid in pids:
        print(f"  [{svc['name']}] 停止 PID={pid}")
        try:
            p = multiprocessing.Process()  # 仅用于取 OS 调用
        except Exception:
            pass
        # 用 taskkill /F /T 杀进程树
        subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                       capture_output=True)
    # 等待端口释放
    for _ in range(30):
        if not port_open(svc["port"]):
            print(f"  [{svc['name']}] 已停止")
            return True
        time.sleep(1)
    print(f"  [{svc['name']}] 停止超时,请手动检查 PID {pids}")
    return False

def status():
    print(f"{'服务':<20} {'端口':<6} {'状态':<10} PID")
    print("-" * 50)
    for key, svc in SERVICES.items():
        pids = port_listener(svc["port"])
        state = "运行中" if pids else "未运行"
        pid_str = ",".join(sorted(pids)) if pids else "-"
        print(f"{svc['name']:<20} {svc['port']:<6} {state:<10} {pid_str}")

def main():
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "status"
    # 启动顺序:后端先起,Web 客户端最后(它要反代到各后端)
    # CosyVoice 模型加载最久,放在最后给足时间
    start_order = ("kokoro", "sensevoice", "edge", "cosy", "web")
    stop_order = ("web", "cosy", "edge", "sensevoice", "kokoro")
    if cmd == "start":
        for k in start_order:
            start_service(k)
    elif cmd == "stop":
        for k in stop_order:
            stop_service(k)
    elif cmd == "restart":
        for k in stop_order:
            stop_service(k)
        for k in start_order:
            start_service(k)
    elif cmd == "status":
        status()
    else:
        print(__doc__)
        sys.exit(1)

if __name__ == "__main__":
    main()
