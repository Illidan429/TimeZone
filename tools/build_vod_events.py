import argparse
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (TimeZone-VOD-Builder/1.0)"
}


def http_get_json(url: str) -> dict:
    req = Request(url, headers=DEFAULT_HEADERS)
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_bvid(text: str) -> str | None:
    m = re.search(r"(BV[0-9A-Za-z]{10})", text)
    return m.group(1) if m else None


def normalize_date(ts: int | float | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d")


def build_from_bvid(bvid: str) -> dict:
    api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    payload = http_get_json(api)
    data = payload.get("data") or {}
    return {
        "date": normalize_date(data.get("pubdate")),
        "title": data.get("title") or f"直播回放（{bvid}）",
        "url": f"https://www.bilibili.com/video/{bvid}/",
    }


def build_from_series(mid: int, series_id: int, max_pages: int) -> list[dict]:
    # 注意：该接口在无登录状态下可能受限，失败时脚本会保留手动项并继续。
    events: list[dict] = []
    for pn in range(1, max_pages + 1):
        api = (
            "https://api.bilibili.com/x/series/archives"
            f"?mid={mid}&series_id={series_id}&pn={pn}&ps=30&only_normal=true&sort=desc"
        )
        payload = http_get_json(api)
        data = payload.get("data") or {}
        archives = data.get("archives") or []
        if not archives:
            break
        for item in archives:
            bvid = item.get("bvid")
            if not bvid:
                continue
            events.append(
                {
                    "date": normalize_date(item.get("pubdate")),
                    "title": item.get("title") or f"直播回放（{bvid}）",
                    "url": f"https://www.bilibili.com/video/{bvid}/",
                }
            )
    return events


def parse_space_series_url(url: str) -> tuple[int | None, int | None]:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    mid = None
    series_id = None
    # 期望路径: /{mid}/lists/{series_id}
    if len(parts) >= 3 and parts[1] == "lists":
        try:
            mid = int(parts[0])
            series_id = int(parts[2])
        except ValueError:
            return None, None
    return mid, series_id


def load_items(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("vod-input.json 必须是数组")
    return data


def save_events(path: str, events: list[dict]) -> int:
    valid = [e for e in events if e.get("date") and e.get("title") and e.get("url")]
    dedup: dict[str, dict] = {}
    for event in valid:
        key = event["url"].strip()
        dedup[key] = event
    events = sorted(dedup.values(), key=lambda x: x["date"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return len(events)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build web/data/vod-events.json from manual + bilibili sources.")
    parser.add_argument("--input", default="web/data/vod-input.json")
    parser.add_argument("--output", default="web/data/vod-events.json")
    args = parser.parse_args()

    try:
        items = load_items(args.input)
    except Exception as err:
        print(f"[ERROR] 读取输入失败: {err}")
        return 1

    all_events: list[dict] = []
    for item in items:
        mode = item.get("mode")
        try:
            if mode == "manual":
                all_events.append(
                    {
                        "date": item.get("date", ""),
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                    }
                )
            elif mode == "video":
                raw = item.get("url", "")
                bvid = extract_bvid(raw)
                if not bvid:
                    print(f"[WARN] 未识别 BV 号，跳过: {raw}")
                    continue
                all_events.append(build_from_bvid(bvid))
            elif mode == "series":
                raw = item.get("url", "")
                mid, series_id = parse_space_series_url(raw)
                if not mid or not series_id:
                    print(f"[WARN] 未识别系列页参数，跳过: {raw}")
                    continue
                pages = int(item.get("pages", 2))
                all_events.extend(build_from_series(mid=mid, series_id=series_id, max_pages=pages))
            else:
                print(f"[WARN] 未知 mode，跳过: {mode}")
        except Exception as err:
            print(f"[WARN] 处理条目失败（mode={mode}）: {err}")

    final_count = save_events(args.output, all_events)
    print(f"[OK] 已生成 {args.output}，共 {final_count} 条（已去重并按日期排序）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
