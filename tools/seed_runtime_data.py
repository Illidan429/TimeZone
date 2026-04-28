#!/usr/bin/env python3
"""将 web/data/*.example.json 种子复制到 web/runtime-data/（若目标尚不存在）。"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME = REPO_ROOT / "web" / "runtime-data"
DATA = REPO_ROOT / "web" / "data"

PAIRS = [
    ("admin-config.json", "admin-config.example.json"),
    ("mallow-posts.json", "mallow-posts.example.json"),
    ("news-posts.json", "news-posts.example.json"),
    ("vod-events.json", "vod-events.example.json"),
    ("vod-input.json", "vod-input.example.json"),
]


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    for runtime_name, example_name in PAIRS:
        dst = RUNTIME / runtime_name
        src = DATA / example_name
        if dst.exists():
            print(f"skip (exists): {dst.relative_to(REPO_ROOT)}")
            continue
        if not src.exists():
            print(f"missing example: {src.relative_to(REPO_ROOT)}")
            return 1
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"seeded: {dst.relative_to(REPO_ROOT)}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
