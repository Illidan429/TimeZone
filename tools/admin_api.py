#!/usr/bin/env python3
import json
import os
import cgi
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "web" / "data"
RUNTIME_DIR = REPO_ROOT / "web" / "runtime-data"
ADMIN_CFG = RUNTIME_DIR / "admin-config.json"
ADMIN_CFG_EXAMPLE = DATA_DIR / "admin-config.example.json"
ADMIN_CFG_LEGACY = DATA_DIR / "admin-config.json"
MALLOW_SEED = DATA_DIR / "mallow-posts.example.json"
NEWS_POSTS = RUNTIME_DIR / "news-posts.json"
MALLOW_POSTS = RUNTIME_DIR / "mallow-posts.json"
VOD_EVENTS = RUNTIME_DIR / "vod-events.json"
VOD_INPUT = RUNTIME_DIR / "vod-input.json"
MALLOW_UPLOAD_DIR = RUNTIME_DIR / "mallow-files"
MAX_MALLOW_FILE_SIZE = 20 * 1024 * 1024
NGINX_ACCESS_LOG = Path("/var/log/nginx/access.log")
IP_LOCATION_CACHE: dict[str, str] = {}


def ensure_admin_config():
    """运行时口令文件仅存在于 runtime-data；支持从旧路径 web/data 迁移一次。"""
    ensure_runtime_dir()
    if ADMIN_CFG.exists():
        return
    if ADMIN_CFG_LEGACY.exists():
        ADMIN_CFG.write_text(ADMIN_CFG_LEGACY.read_text(encoding="utf-8"), encoding="utf-8")
        return
    if ADMIN_CFG_EXAMPLE.exists():
        ADMIN_CFG.write_text(ADMIN_CFG_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")


def load_passcode() -> str:
    ensure_admin_config()
    try:
        data = json.loads(ADMIN_CFG.read_text(encoding="utf-8"))
        value = data.get("archiveEditPasscode")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception:
        pass
    return "ljx960429?"


def load_admin_config() -> dict:
    ensure_admin_config()
    try:
        data = json.loads(ADMIN_CFG.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_admin_config(data: dict):
    ensure_runtime_dir()
    ADMIN_CFG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_runtime_dir():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def ensure_seed_file(runtime_path: Path, fallback: Path):
    ensure_runtime_dir()
    if runtime_path.exists():
        return
    if fallback.exists():
        runtime_path.write_text(fallback.read_text(encoding="utf-8"), encoding="utf-8")


def run_vod_refresh() -> tuple[bool, dict]:
    """执行一次录播抓取刷新，供接口与定时任务共用。"""
    ensure_runtime_dir()
    cmd = [
        "python3",
        "tools/build_vod_events.py",
        "--input",
        str(VOD_INPUT),
        "--output",
        str(VOD_EVENTS),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, {"ok": False, "message": "抓取超时（>180s）"}
    except Exception as exc:
        return False, {"ok": False, "message": f"服务异常: {exc}"}

    if proc.returncode != 0:
        return (
            False,
            {
                "ok": False,
                "message": "脚本执行失败",
                "stderr": (proc.stderr or "")[-1000:],
            },
        )
    return (
        True,
        {
            "ok": True,
            "message": "录播已更新",
            "stdout": (proc.stdout or "")[-1000:],
        },
    )


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


def _parse_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except Exception:
        return default


def _normalize_auto_refresh(raw: dict | None, defaults: dict) -> dict:
    item = raw if isinstance(raw, dict) else {}
    enabled = item.get("enabled", defaults["enabled"])
    hour = item.get("hour", defaults["hour"])
    minute = item.get("minute", defaults["minute"])
    startup_run = item.get("startupRun", defaults["startupRun"])
    try:
        hour = int(hour)
    except Exception:
        hour = defaults["hour"]
    try:
        minute = int(minute)
    except Exception:
        minute = defaults["minute"]
    return {
        "enabled": bool(enabled),
        "hour": max(0, min(23, hour)),
        "minute": max(0, min(59, minute)),
        "startupRun": bool(startup_run),
    }


def get_auto_refresh_settings() -> dict:
    defaults = {
        "enabled": _parse_bool_env("TZ_VOD_AUTO_REFRESH_ENABLED", True),
        "hour": max(0, min(23, _parse_int_env("TZ_VOD_AUTO_REFRESH_HOUR", 4))),
        "minute": max(0, min(59, _parse_int_env("TZ_VOD_AUTO_REFRESH_MINUTE", 15))),
        "startupRun": _parse_bool_env("TZ_VOD_AUTO_REFRESH_STARTUP_RUN", False),
    }
    cfg = load_admin_config()
    return _normalize_auto_refresh(cfg.get("autoRefresh"), defaults)


def set_auto_refresh_settings(next_settings: dict) -> dict:
    cfg = load_admin_config()
    current = cfg.get("autoRefresh")
    normalized = _normalize_auto_refresh(next_settings, _normalize_auto_refresh(current, get_auto_refresh_settings()))
    cfg["autoRefresh"] = normalized
    save_admin_config(cfg)
    return normalized


def start_daily_vod_refresh_worker():
    """按本机时区每天定时刷新录播。"""
    def _worker():
        settings = get_auto_refresh_settings()
        print(
            "[auto-vod] scheduler started, "
            f"enabled={settings['enabled']} daily at {settings['hour']:02d}:{settings['minute']:02d}"
        )
        if settings["enabled"] and settings["startupRun"]:
            ok, payload = run_vod_refresh()
            print(f"[auto-vod] startup run: {'ok' if ok else 'fail'} - {payload.get('message', '')}")
        while True:
            settings = get_auto_refresh_settings()
            if not settings["enabled"]:
                print("[auto-vod] disabled, recheck in 60s")
                time.sleep(60)
                continue
            now = datetime.now()
            next_run = now.replace(hour=settings["hour"], minute=settings["minute"], second=0, microsecond=0)
            if next_run <= now:
                next_run = next_run + timedelta(days=1)
            print(f"[auto-vod] next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            while True:
                now2 = datetime.now()
                if now2 >= next_run:
                    break
                time.sleep(min(60, max(1, int((next_run - now2).total_seconds()))))
                # 支持从管理员页面动态修改时间/开关，下一轮等待立即生效。
                new_settings = get_auto_refresh_settings()
                if new_settings != settings:
                    settings = new_settings
                    if not settings["enabled"]:
                        print("[auto-vod] switched to disabled")
                        break
                    now3 = datetime.now()
                    next_run = now3.replace(
                        hour=settings["hour"],
                        minute=settings["minute"],
                        second=0,
                        microsecond=0,
                    )
                    if next_run <= now3:
                        next_run = next_run + timedelta(days=1)
                    print(
                        "[auto-vod] schedule updated, "
                        f"next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
            if not settings["enabled"]:
                continue
            ok, payload = run_vod_refresh()
            print(f"[auto-vod] daily run: {'ok' if ok else 'fail'} - {payload.get('message', '')}")

    threading.Thread(target=_worker, name="daily-vod-refresh", daemon=True).start()


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
    if ip in IP_LOCATION_CACHE:
        return IP_LOCATION_CACHE[ip]
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
            loc = f"{prov}{city}".strip()
            IP_LOCATION_CACHE[ip] = loc
            return loc
    except Exception:
        pass
    IP_LOCATION_CACHE[ip] = "未知"
    return "未知"


def read_access_logs(limit: int = 200) -> list[dict]:
    if not NGINX_ACCESS_LOG.exists():
        return []
    try:
        lines = NGINX_ACCESS_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    rows: list[dict] = []
    pattern = re.compile(r'^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"(\S+)\s+([^"]+)\s+\S+"\s+(\d{3})')
    for line in reversed(lines):
        m = pattern.search(line)
        if not m:
            continue
        ip, time_str, method, path, status = m.groups()
        if path.startswith("/api/"):
            continue
        rows.append(
            {
                "time": time_str,
                "method": method,
                "path": path,
                "status": int(status),
                "ip": ip,
                "ipLocation": resolve_ip_location(ip),
            }
        )
        if len(rows) >= limit:
            break
    return rows


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
        if self.path not in (
            "/api/admin/refresh-vod",
            "/api/admin/news-posts",
            "/api/admin/mallow-delete",
            "/api/admin/auto-refresh-config",
            "/api/mallow/submit",
        ):
            self._send_json(404, {"ok": False, "message": "Not found"})
            return

        if self.path == "/api/mallow/submit":
            try:
                ensure_seed_file(MALLOW_POSTS, MALLOW_SEED)
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
                            "url": f"/runtime-data/mallow-files/{stored}",
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
                ensure_seed_file(MALLOW_POSTS, MALLOW_SEED)
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

        if self.path == "/api/admin/auto-refresh-config":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                payload = json.loads(raw.decode("utf-8"))
                saved = set_auto_refresh_settings(payload or {})
                self._send_json(200, {"ok": True, "message": "自动抓取设置已保存", "config": saved})
                return
            except Exception as exc:
                self._send_json(500, {"ok": False, "message": f"保存失败: {exc}"})
                return

        ok, payload = run_vod_refresh()
        self._send_json(200 if ok else 500, payload)

    def do_GET(self):
        if self.path == "/api/admin/auto-refresh-config":
            admin_pass = self.headers.get("X-Admin-Passcode", "")
            if admin_pass != load_passcode():
                self._send_json(403, {"ok": False, "message": "口令错误"})
                return
            self._send_json(200, {"ok": True, "config": get_auto_refresh_settings()})
            return

        if self.path.startswith("/api/admin/access-logs"):
            admin_pass = self.headers.get("X-Admin-Passcode", "")
            if admin_pass != load_passcode():
                self._send_json(403, {"ok": False, "message": "口令错误"})
                return
            logs = read_access_logs(limit=200)
            self._send_json(200, {"ok": True, "items": logs})
            return

        if self.path == "/api/admin/mallow-list":
            admin_pass = self.headers.get("X-Admin-Passcode", "")
            if admin_pass != load_passcode():
                self._send_json(403, {"ok": False, "message": "口令错误"})
                return
            try:
                ensure_seed_file(MALLOW_POSTS, MALLOW_SEED)
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
    start_daily_vod_refresh_worker()
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"TimeZone admin API listening on http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
