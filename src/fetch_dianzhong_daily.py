"""Archive the public Dianzhong female bestseller daily ranking metadata."""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


URL = "https://www.ishugui.com/ranking/2-2-1"


class RankingRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.row: dict | None = None
        self.active_field = ""
        self.parts: list[str] = []
        self.rows: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class") or ""
        if tag == "div" and self.row is None and "RankBookList_rankItem__" in classes:
            self.row = {"rank": "", "title": "", "category": "", "heat": "", "url": ""}
            self.depth = 1
        elif self.row is not None and tag == "div":
            self.depth += 1
        if self.row is not None and tag == "a":
            self.active_field = ""
            self.parts = []
            if "RankBookList_rankIndex__" in classes:
                self.active_field = "rank"
                self.row["url"] = attrs_dict.get("href") or self.row["url"]
            elif "RankBookList_bookName__" in classes:
                self.active_field = "title"
                self.row["url"] = attrs_dict.get("href") or self.row["url"]
            elif "RankBookList_bookAuthor__" in classes:
                self.active_field = "category"
            elif "RankBookList_bookType__" in classes:
                self.active_field = "heat"

    def handle_data(self, data: str) -> None:
        if self.row is not None and self.active_field:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.row is not None and self.active_field:
            self.row[self.active_field] = re.sub(r"\s+", " ", html.unescape("".join(self.parts))).strip()
            self.active_field = ""
            self.parts = []
        elif tag == "div" and self.row is not None:
            self.depth -= 1
            if self.depth == 0:
                self.rows.append(self.row)
                self.row = None


def collect(now: dt.datetime) -> dict:
    request = Request(URL, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"})
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError(f"Dianzhong ranking HTTP {response.status}")
        page = response.read(2_000_000).decode("utf-8", errors="replace")
    parser = RankingRows()
    parser.feed(page)
    works = []
    for row in parser.rows:
        rank = len(works) + 1
        if row["rank"] != str(rank):
            continue
        if not row["title"] or not row["heat"] or not row["url"].startswith("/book/"):
            raise ValueError(f"incomplete Dianzhong daily rank {rank}")
        works.append({
            "rank": rank,
            "title": row["title"],
            "category": row["category"],
            "heat_display": row["heat"],
            "work_url": "https://www.ishugui.com" + row["url"],
        })
        if len(works) == 10:
            break
    if len(works) != 10:
        raise ValueError(f"Dianzhong daily ranking has {len(works)} complete rows; expected 10")
    return {
        "schema_version": "ranking-snapshot/v1",
        "observed_date": now.date().isoformat(),
        "ranking_date": None,
        "source": {
            "name": "点众阅读官网·女生小说畅销日榜",
            "url": URL,
            "authority": "official_platform",
            "platform_covered": "点众阅读",
            "ranking": "女生小说·畅销榜·日榜",
            "metric_note": "官网页面未标注榜单生成日期；仅存公开排名元数据，不抓取作品正文。",
        },
        "works": works,
    }


def main() -> None:
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    snapshot = collect(now)
    path = Path("market-intel") / snapshot["observed_date"] / "dianzhong-female-daily-bestsellers.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("works") == snapshot["works"]:
            print(json.dumps({"status": "unchanged", "path": str(path)}, ensure_ascii=False))
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "published", "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

