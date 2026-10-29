"""web_server - nanocode 的 Web 前端（标准库 http.server，零第三方依赖）

用法：python web_server.py  →  浏览器打开 http://localhost:8000

路由：
  GET  /              聊天页面（web/templates/index.html）
  GET  /static/*      前端静态资源（style.css / app.js）
  GET  /memes/*       表情包图片（限制在 memes/ 目录内，防路径穿越）
  GET  /api/state     当前情感状态（affinity / mood / valence / arousal）
  GET  /api/memories  最近记忆条目；带 ?date= 返回当天全文
  POST /api/chat      发消息 → agent 循环 → 返回 {reply, meme, state}
  POST /api/reset     清空当前会话上下文
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from nanocode import build_system_prompt, run_turn
from function_call.base.memory.memory_store import load_state, recent_entries
from function_call.base.system.meme import pick_meme

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
MEMES_DIR = (ROOT / "memes").resolve()
PORT = 8000

messages = []                     # 当前会话上下文（服务端内存态）
SYSTEM_PROMPT = build_system_prompt()

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class Handler(BaseHTTPRequestHandler):
    """极简路由：够用即可，不做框架抽象"""

    def _send(self, status, content_type, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status=200):
        self._send(status, "application/json; charset=utf-8",
                   json.dumps(data, ensure_ascii=False))

    def _serve_file(self, root, url_path):
        """从 root 下取文件并发送；解析后的路径必须仍在 root 内"""
        target = (root / url_path.lstrip("/")).resolve()
        if root.resolve() not in target.parents or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        ctype = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, ctype, target.read_bytes())

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            page = (WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8")
            self._send(200, CONTENT_TYPES[".html"], page)
        elif path.startswith("/static/"):
            self._serve_file(WEB_DIR / "static", path[len("/static/"):])
        elif path.startswith("/memes/"):
            self._serve_file(MEMES_DIR, path[len("/memes/"):])
        elif path == "/api/state":
            self._json(load_state())
        elif path == "/api/memories":
            if "date=" in self.path:
                date = self.path.split("date=")[1].split("&")[0]
                items = [e for e in recent_entries(limit=50) if e["date"] == date]
                self._json({"items": items})
            else:
                self._json({"items": recent_entries(limit=8)})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/reset":
            messages.clear()
            self._json({"ok": True})
            return
        if path != "/api/chat":
            self._json({"error": "not found"}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            user_input = str(data.get("message", "")).strip()
            if not user_input:
                self._json({"error": "消息不能为空"}, 400)
                return

            messages.append({"role": "user", "content": user_input})
            reply = run_turn(messages, SYSTEM_PROMPT)
            state = load_state()
            self._json({
                "reply": reply,
                "meme": pick_meme(state["mood_label"]),
                "state": state,
            })
        except Exception as err:
            self._json({"error": str(err)}, 500)

    def log_message(self, format, *args):
        # 参数名必须与父类 BaseHTTPRequestHandler.log_message(self, format, *args)
        # 一致，否则 Pylance 会判定"不兼容的签名覆盖"而标红
        pass  # 关掉默认请求日志，避免刷屏


if __name__ == "__main__":
    print(f"nanocode web  →  http://localhost:{PORT}")
    print(f"表情包目录：{MEMES_DIR}")
    print("Ctrl+C 停止")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
