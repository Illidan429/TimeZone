#!/usr/bin/env python3
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ADMIN_CFG = REPO_ROOT / "web" / "data" / "admin-config.json"


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
        if self.path != "/api/admin/refresh-vod":
            self._send_json(404, {"ok": False, "message": "Not found"})
            return

        admin_pass = self.headers.get("X-Admin-Passcode", "")
        if admin_pass != load_passcode():
            self._send_json(403, {"ok": False, "message": "口令错误"})
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
