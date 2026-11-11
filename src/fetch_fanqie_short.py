"""Collect the dated public Fanqie short-story ranking from Novelcatch."""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


URL = "https://novelcatch.com/short"


class Rows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.rows = []
        self.cells = []
        self.cell = None
        self.links = []
        self.row_links = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells, self.row_links = [], []
        elif tag == "td":
            self.cell, self.links = [], []
        elif tag == "a" and self.cell is not None:
            href = dict(attrs).get("href", "")
            if href:
                self.links.append(href)

    def handle_data(self, data):
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.cells.append(re.sub(r"\s+", " ", html.unescape("".join(self.cell))).strip())
            self.row_links.append(self.links)
            self.cell = None
        elif tag == "tr" and self.cells:
            self.rows.append((self.cells, self.row_links))


def parse(page: str, now: dt.datetime) -> dict:
    parser = Rows()
    parser.feed(page)
    visible = re.sub(r"\s+", " ", " ".join(parser.text))
    match = re.search(r"数据更新日\s*(\d{4}-\d{2}-\d{2})", visible)
    if not match:
        raise ValueError("short-story ranking has no source data date")
    data_date = match.group(1)
    age = now.date() - dt.date.fromisoformat(data_date)
    if age.days not in (0, 1):
        raise ValueError(f"short-story ranking is stale: {data_date}")
    works = []
    for cells, links in parser.rows:
        if not cells or cells[0] != str(len(works) + 1):
            continue
        if len(cells) < 10 or len(cells[1]) < 2:
            raise ValueError(f"incomplete short-story ranking row {len(works) + 1}")
        work_url = next((x for x in links[1] if re.fullmatch(r"/short/\d+", x)), None)
        if not work_url:
            raise ValueError(f"missing work link in row {len(works) + 1}")
        works.append({
            "rank": len(works) + 1,
            "title": cells[1],
            "author": cells[4],
            "category": cells[2],
            "readers_10k": cells[5],
            "words_10k": cells[6],
            "seven_day_delta_10k": cells[9],
            "source_work_url": "https://novelcatch.com" + work_url,
        })
        if len(works) == 5:
            break
    if len(works) != 5:
        raise ValueError("short-story ranking has fewer than five complete rows")
    return {
        "schema_version": "ranking-snapshot/v1",
        "data_date": data_date,
        "observed_date": now.date().isoformat(),
        "source": {
            "name": "网文情报站·番茄短篇排行",
            "url": URL,
            "authority": "third_party_aggregator",
            "platform_covered": "番茄短故事",
            "ranking": "近期在读 · 7天 · 按在读排序",
            "metric_note": "仅记录来源公开榜单展示的数据；未与番茄官方逐项核对。",
        },
        "works": works,
    }


def main():
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    request = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        page = response.read(2_000_000).decode("utf-8", errors="replace")
    snapshot = parse(page, now)
    path = Path("market-intel") / snapshot["data_date"] / "fanqie-short-reading.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("works") == snapshot["works"]:
            print(json.dumps({"status": "unchanged", "path": str(path)}))
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "published", "path": str(path)}))


if __name__ == "__main__":
    main()

