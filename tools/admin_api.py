#!/usr/bin/env python3
import json
import os
import cgi
import re
import subprocess
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
ADMIN_CFG = REPO_ROOT / "web" / "data" / "admin-config.json"
RUNTIME_DIR = REPO_ROOT / "web" / "runtime-data"
NEWS_POSTS = RUNTIME_DIR / "news-posts.json"
MALLOW_POSTS = RUNTIME_DIR / "mallow-posts.json"
VOD_EVENTS = RUNTIME_DIR / "vod-events.json"
MALLOW_UPLOAD_DIR = RUNTIME_DIR / "mallow-files"
MAX_MALLOW_FILE_SIZE = 20 * 1024 * 1024


def load_passcode() -> str:
    try:
        data = json.loads(ADMIN_CFG.read_text(encoding="utf-8"))
        value = data.get("archiveEditPasscode")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        pass
    return "ljx960429?"


def ensure_runtime_dir():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def ensure_seed_file(runtime_path: Path, fallback: Path):
    ensure_runtime_dir()
    if runtime_path.exists():
        return
    if fallback.exists():
        runtime_path.write_text(fallback.read_text(encoding="utf-8"), encoding="utf-8")


def get_client_ip(handler: BaseHTTPRequestHandler) -> str:
    xff = (handler.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    xrip = (handler.headers.get("X-Real-IP") or "").strip()
    if xrip:
        return xrip
    return handler.client_address[0] if handler.client_address else ""


def resolve_ip_location(ip: str) -> str:
    if not ip:
        return "未知"
    if ip.startswith(("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "::1")):
        return "内网/本机"
    try:
        url = f"https://whois.pconline.com.cn/ipJson.jsp?json=true&ip={quote(ip)}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 TimeZoneBot/1.0"})
        with urlopen(req, timeout=6) as resp:
            raw = resp.read()
        try:
            text = raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = raw.decode("gbk", errors="ignore").strip()
        data = json.loads(text)
        prov = (data.get("pro") or "").strip()
        city = (data.get("city") or "").strip()
        if prov or city:
            return f"{prov}{city}".strip()
    except Exception:
        pass
    return "未知"


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
        if self.path not in ("/api/admin/refresh-vod", "/api/admin/news-posts", "/api/admin/mallow-delete", "/api/mallow/submit"):
            self._send_json(404, {"ok": False, "message": "Not found"})
            return

        if self.path == "/api/mallow/submit":
            try:
                ensure_seed_file(MALLOW_POSTS, REPO_ROOT / "web" / "data" / "mallow-posts.json")
                content_type = self.headers.get("Content-Type", "")
                content = ""
                attachment = None
                if content_type.startswith("multipart/form-data"):
                    form = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={
                            "REQUEST_METHOD": "POST",
                            "CONTENT_TYPE": content_type,
                        },
                    )
                    content = str(form.getfirst("content", "")).strip()
                    file_item = form["file"] if "file" in form else None
                    if file_item is not None and getattr(file_item, "filename", ""):
                        filename = os.path.basename(str(file_item.filename))
                        data = file_item.file.read(MAX_MALLOW_FILE_SIZE + 1)
                        if len(data) > MAX_MALLOW_FILE_SIZE:
                            self._send_json(400, {"ok": False, "message": "附件不能超过 20MB"})
                            return
                        safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120] or "file.bin"
                        MALLOW_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                        stored = f"{uuid.uuid4().hex}_{safe}"
                        saved_path = MALLOW_UPLOAD_DIR / stored
                        saved_path.write_bytes(data)
                        attachment = {
                            "name": filename[:200],
                            "size": len(data),
                            "url": f"/data/mallow-files/{stored}",
                            "savedPath": str(saved_path),
                        }
                else:
                    length = int(self.headers.get("Content-Length", "0"))
                    raw = self.rfile.read(length) if length > 0 else b"{}"
                    payload = json.loads(raw.decode("utf-8"))
                    content = str(payload.get("content", "")).strip()
                if not content:
                    self._send_json(400, {"ok": False, "message": "内容不能为空"})
                    return
                if len(content) > 500:
                    self._send_json(400, {"ok": False, "message": "内容不能超过 500 字"})
                    return
                try:
                    existing = json.loads(MALLOW_POSTS.read_text(encoding="utf-8"))
                    if not isinstance(existing, list):
                        existing = []
                except Exception:
                    existing = []
                item = {
                    "id": str(int(time.time() * 1000)),
                    "createdAt": datetime.utcnow().isoformat() + "Z",
                    "content": content,
                    "ip": get_client_ip(self),
                }
                item["ipLocation"] = resolve_ip_location(item["ip"])
                if attachment:
                    item["attachmentName"] = attachment["name"]
                    item["attachmentSize"] = attachment["size"]
                    item["attachmentUrl"] = attachment["url"]
                    item["attachmentSavedPath"] = attachment["savedPath"]
                existing.append(item)
                MALLOW_POSTS.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self._send_json(200, {"ok": True, "message": "投递成功"})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "message": f"投递失败: {exc}"})
                return

        admin_pass = self.headers.get("X-Admin-Passcode", "")
        if admin_pass != load_passcode():
            self._send_json(403, {"ok": False, "message": "口令错误"})
            return

        if self.path == "/api/admin/news-posts":
            try:
                ensure_runtime_dir()
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

        if self.path == "/api/admin/mallow-delete":
            try:
                ensure_seed_file(MALLOW_POSTS, REPO_ROOT / "web" / "data" / "mallow-posts.json")
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                target_id = str(payload.get("id", "")).strip()
                if not target_id:
                    self._send_json(400, {"ok": False, "message": "缺少 id"})
                    return
                try:
                    data = json.loads(MALLOW_POSTS.read_text(encoding="utf-8"))
                    if not isinstance(data, list):
                        data = []
                except Exception:
                    data = []
                kept = []
                removed = None
                for item in data:
                    if str(item.get("id", "")) == target_id and removed is None:
                        removed = item
                        continue
                    kept.append(item)
                if removed is None:
                    self._send_json(404, {"ok": False, "message": "未找到该条棉花糖"})
                    return
                saved = removed.get("attachmentSavedPath")
                if saved:
                    try:
                        Path(saved).unlink(missing_ok=True)
                    except Exception:
                        pass
                MALLOW_POSTS.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self._send_json(200, {"ok": True, "message": "已删除"})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "message": f"删除失败: {exc}"})
                return

        try:
            ensure_runtime_dir()
            cmd = ["python3", "tools/build_vod_events.py", "--output", str(VOD_EVENTS)]
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
        if self.path == "/api/admin/mallow-list":
            admin_pass = self.headers.get("X-Admin-Passcode", "")
            if admin_pass != load_passcode():
                self._send_json(403, {"ok": False, "message": "口令错误"})
                return
            try:
                ensure_seed_file(MALLOW_POSTS, REPO_ROOT / "web" / "data" / "mallow-posts.json")
                data = json.loads(MALLOW_POSTS.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    data = []
                repaired = False
                for item in data:
                    ip = str(item.get("ip", "")).strip()
                    loc = str(item.get("ipLocation", "")).strip()
                    # 历史乱码/空值时按 IP 自动补一次属地。
                    if ip and (not loc or len(loc) <= 1 or "?" in loc or "�" in loc):
                        item["ipLocation"] = resolve_ip_location(ip)
                        repaired = True
                if repaired:
                    MALLOW_POSTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self._send_json(200, {"ok": True, "items": data})
            except Exception as exc:
                self._send_json(500, {"ok": False, "message": f"读取失败: {exc}"})
            return

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
