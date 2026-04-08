#!/usr/bin/env python3
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
ADMIN_CFG = REPO_ROOT / "web" / "data" / "admin-config.json"
NEWS_POSTS = REPO_ROOT / "web" / "data" / "news-posts.json"


def load_passcode() -> str:
    try:
        data = json.loads(ADMIN_CFG.read_text(encoding="utf-8"))
        value = data.get("archiveEditPasscode")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        pass
    return "timezone-admin-please-change"


class Handler(BaseHTTPRequestHandler):
    server_version = "TimeZoneAdminAPI/1.0"

    def _send_json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path not in ("/api/admin/refresh-vod", "/api/admin/news-posts"):
            self._send_json(404, {"ok": False, "message": "Not found"})
            return

        admin_pass = self.headers.get("X-Admin-Passcode", "")
        if admin_pass != load_passcode():
            self._send_json(403, {"ok": False, "message": "口令错误"})
            return

        if self.path == "/api/admin/news-posts":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                posts = payload.get("posts")
                if not isinstance(posts, list):
                    self._send_json(400, {"ok": False, "message": "posts 必须是数组"})
                    return
                clean = []
                for item in posts:
                    if not isinstance(item, dict):
                        continue
                    date = str(item.get("date", "")).strip()
                    title = str(item.get("title", "")).strip()
                    content = str(item.get("content", "")).strip()
                    if not (date and title and content):
                        continue
                    clean.append({"date": date[:20], "title": title[:120], "content": content[:5000]})
                NEWS_POSTS.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self._send_json(200, {"ok": True, "message": "开发日记已保存", "count": len(clean)})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "message": f"保存失败: {exc}"})
                return

        try:
            cmd = ["python3", "tools/build_vod_events.py"]
            proc = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
            if proc.returncode != 0:
                self._send_json(
                    500,
                    {
                        "ok": False,
                        "message": "脚本执行失败",
                        "stderr": (proc.stderr or "")[-1000:],
                    },
                )
                return
            self._send_json(
                200,
                {
                    "ok": True,
                    "message": "录播已更新",
                    "stdout": (proc.stdout or "")[-1000:],
                },
            )
        except subprocess.TimeoutExpired:
            self._send_json(504, {"ok": False, "message": "抓取超时（>180s）"})
        except Exception as exc:
            self._send_json(500, {"ok": False, "message": f"服务异常: {exc}"})

    def do_GET(self):
        if self.path != "/api/live/status":
            self._send_json(404, {"ok": False, "message": "Not found"})
            return
        # 先通过主播 UID 查询直播间信息，再返回直播状态与可直达链接。
        uid = "3493089362577527"
        try:
            api = f"https://api.live.bilibili.com/room/v1/Room/getRoomInfoOld?mid={uid}"
            req = Request(
                api,
                headers={
                    "User-Agent": "Mozilla/5.0 TimeZoneBot/1.0",
                    "Referer": "https://www.bilibili.com/",
                },
            )
            with urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data") or {}
            room_id = data.get("roomid")
            live_status = data.get("liveStatus", 0)
            room_url = f"https://live.bilibili.com/{room_id}" if room_id else f"https://space.bilibili.com/{uid}"
            self._send_json(
                200,
                {
                    "ok": True,
                    "uid": uid,
                    "roomId": room_id,
                    "roomUrl": room_url,
                    "liveStatus": live_status,
                },
            )
        except Exception as exc:
            self._send_json(502, {"ok": False, "message": f"直播状态查询失败: {exc}"})

    def log_message(self, fmt, *args):
        return


def main():
    host = os.environ.get("TZ_ADMIN_API_HOST", "127.0.0.1")
    port = int(os.environ.get("TZ_ADMIN_API_PORT", "8010"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"TimeZone admin API listening on http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
