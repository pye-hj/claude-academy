#!/usr/bin/env python3
"""test.html をローカル配信し、回答を講座フォルダに直接保存するサーバー。

使い方:
    python3 serve-test.py <講座フォルダ> [--no-open] [--timeout 秒]
    python3 serve-test.py <講座フォルダ> --stop     # 起動中のサーバーを停止

test.html の「回答を保存」ボタンが POST /save を叩くと、
<講座フォルダ>/kaitou.json に直接書き出す。ダウンロードフォルダを経由しない。
一定時間アクセスがなければ自動終了する。
"""

import argparse
import http.server
import json
import os
import signal
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

PORT_RANGE = range(8765, 8786)
MAX_BODY = 5 * 1024 * 1024  # 5MB
PID_FILE = ".serve-test.pid"


def build_handler(root: Path, state: dict):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def end_headers(self):
            # 開き直したときに古い test.html が出ないようにする
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_GET(self):
            state["last_activity"] = time.time()
            super().do_GET()

        def do_POST(self):
            state["last_activity"] = time.time()
            if self.path.split("?")[0] != "/save":
                self.send_error(404, "Not Found")
                return

            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                self.send_error(400, "Bad Request")
                return

            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_error(400, "Invalid JSON")
                return

            # 書き出し先は固定。リクエストからパスは受け取らない。
            target = root / "kaitou.json"
            target.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"[saved] {target}", flush=True)

            body = json.dumps({"ok": True, "path": str(target)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def bind(root: Path, state: dict):
    handler = build_handler(root, state)
    last_error = None
    for port in PORT_RANGE:
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as exc:  # ポート使用中
            last_error = exc
            continue
        return httpd, port
    raise SystemExit(f"空きポートが見つかりません ({PORT_RANGE.start}-{PORT_RANGE.stop - 1}): {last_error}")


def stop(root: Path):
    """PIDファイル経由で停止する。pkill -f はシェル自身にもマッチして誤爆するため使わない。"""
    pid_path = root / PID_FILE
    if not pid_path.is_file():
        print("[stop] 起動中のサーバーはありません", flush=True)
        return

    try:
        pid = int(pid_path.read_text().strip())
    except ValueError:
        pid_path.unlink(missing_ok=True)
        print("[stop] PIDファイルが壊れていたため削除しました", flush=True)
        return

    # PID使い回しで無関係なプロセスを殺さないよう、コマンドラインを検証する
    try:
        cmdline = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)],
            capture_output=True, text=True, check=False,
        ).stdout
    except OSError:
        cmdline = ""

    if "serve-test.py" not in cmdline:
        pid_path.unlink(missing_ok=True)
        print(f"[stop] PID {pid} は既に終了していました", flush=True)
        return

    os.kill(pid, signal.SIGTERM)
    pid_path.unlink(missing_ok=True)
    print(f"[stop] PID {pid} を停止しました", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", help="test.html のある講座フォルダ")
    parser.add_argument("--no-open", action="store_true", help="ブラウザを開かない")
    parser.add_argument("--timeout", type=int, default=3600, help="無操作で終了するまでの秒数 (0で無効)")
    parser.add_argument("--stop", action="store_true", help="起動中のサーバーを停止して終了する")
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()

    if args.stop:
        stop(root)
        return

    if not (root / "test.html").is_file():
        raise SystemExit(f"test.html が見つかりません: {root}")

    state = {"last_activity": time.time()}
    stop(root)  # 同じ講座の古いサーバーが残っていれば片付ける
    httpd, port = bind(root, state)
    url = f"http://127.0.0.1:{port}/test.html"
    (root / PID_FILE).write_text(f"{os.getpid()}\n", encoding="utf-8")
    print(f"[serving] {root}", flush=True)
    print(f"[ready] {url}", flush=True)

    if args.timeout > 0:
        def watchdog():
            while True:
                time.sleep(10)
                if time.time() - state["last_activity"] > args.timeout:
                    print("[idle] タイムアウトのため終了します", flush=True)
                    threading.Thread(target=httpd.shutdown, daemon=True).start()
                    return

        threading.Thread(target=watchdog, daemon=True).start()

    if not args.no_open:
        webbrowser.open(url)

    # --stop からの SIGTERM でも finally を通って後片付けする
    def on_sigterm(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, on_sigterm)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        pid_path = root / PID_FILE
        if pid_path.is_file() and pid_path.read_text().strip() == str(os.getpid()):
            pid_path.unlink(missing_ok=True)
        print("[stopped]", flush=True)


if __name__ == "__main__":
    main()
