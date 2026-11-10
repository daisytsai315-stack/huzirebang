"""Save the public metadata in Zhihu's official Salt Story ranking.

This reads only the ranking endpoint. It does not open or copy paid chapters.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from urllib.request import Request, urlopen


SOURCE_URL = "https://www.zhihu.com/xen/market/salt-ranking-list?tab=story"
API_URL = "https://api.zhihu.com/market/tab_list/story"


def parse(payload: dict, observed_at: dt.datetime) -> dict:
    rows = payload.get("data")
    if not isinstance(rows, list) or len(rows) < 5:
        raise ValueError("Zhihu story ranking has fewer than five rows")

    works = []
    for rank, row in enumerate(rows[:5], 1):
        if not isinstance(row, dict):
            raise ValueError(f"invalid Zhihu ranking row {rank}")
        title = row.get("title")
        url = row.get("url")
        if not isinstance(title, str) or len(title.strip()) < 2:
            raise ValueError(f"missing title in Zhihu ranking row {rank}")
        if not isinstance(url, str) or not url.startswith(
            ("https://zhihu.com/", "https://www.zhihu.com/")
        ):
            raise ValueError(f"invalid URL in Zhihu ranking row {rank}")
        authors = row.get("authors") or []
        names = [author.get("name", "") for author in authors if isinstance(author, dict)]
        works.append(
            {
                "rank": rank,
                "title": title.strip(),
                "authors": [name for name in names if name],
                "zhihu_url": url,
                "product_type": row.get("product_type"),
                "reading_status": "UNVERIFIED",
            }
        )

    return {
        "schema_version": "ranking-snapshot/v1",
        "observed_at": observed_at.isoformat(timespec="seconds"),
        "snapshot_date": observed_at.date().isoformat(),
        "ranking_date": None,
        "source": {
            "name": "知乎盐选榜单·故事榜",
            "authority": "official_platform",
            "platform_covered": "知乎",
            "page_url": SOURCE_URL,
            "api_url": API_URL,
            "metric_note": "知乎接口未提供榜单生成日期；snapshot_date 仅为抓取日期，排名可能未在当天更新。",
        },
        "works": works,
    }


def collect(now: dt.datetime) -> dict:
    request = Request(API_URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError(f"Zhihu story ranking HTTP {response.status}")
        payload = json.loads(response.read(500_000).decode("utf-8"))
    return parse(payload, now)


def save(snapshot: dict, root: Path) -> tuple[Path, str]:
    path = root / snapshot["snapshot_date"] / "zhihu-story-ranking.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        without_time = lambda x: {k: v for k, v in x.items() if k != "observed_at"}
        if without_time(previous) == without_time(snapshot):
            return path, "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, "published"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("market-intel"))
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    path, status = save(collect(now), args.output_root)
    print(json.dumps({"status": status, "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

