"""Save dated, public female new-book rankings from a third-party source.

Only the ranking table is read. No account, novel chapter, or paid content is opened.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://www.fanqiehub.com/ranking"
CATEGORIES = ("豪门总裁", "现言脑洞")
USER_AGENT = "Mozilla/5.0 (compatible; NovelMarketSnapshot/1.0; public metadata only)"


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


class RankingRows(HTMLParser):
    """Read only the first ranking table, excluding page menus and later tables."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tbody_count = 0
        self.in_first_tbody = False
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.cells: list[str] = []
        self.book_id: str | None = None
        self.rows: list[tuple[str | None, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tbody":
            self.tbody_count += 1
            self.in_first_tbody = self.tbody_count == 1
        elif self.in_first_tbody and tag == "tr":
            self.in_row = True
            self.cells = []
            match = re.search(r"showBookDetail\('([0-9]+)'\)", attrs_dict.get("onclick") or "")
            self.book_id = match.group(1) if match else None
        elif self.in_row and tag == "td":
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.cells.append(compact(" ".join(self.cell_parts)))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.cells:
                self.rows.append((self.book_id, self.cells))
            self.in_row = False
        elif tag == "tbody" and self.in_first_tbody:
            self.in_first_tbody = False


def source_url(category: str) -> str:
    return BASE_URL + "?" + urlencode(
        {"platform": "女频", "board_type": "新书榜", "category": category}
    )


def parse_ranking(page: str, category: str) -> tuple[str, list[dict]]:
    date_match = re.search(
        rf"于\s*(\d{{4}}-\d{{2}}-\d{{2}})\s*更新的女频{re.escape(category)}新书榜",
        page,
    )
    if not date_match:
        raise ValueError(f"{category}: page does not show a dated matching ranking")
    data_date = date_match.group(1)
    dt.date.fromisoformat(data_date)

    parser = RankingRows()
    parser.feed(page)
    if len(parser.rows) < 5:
        raise ValueError(f"{category}: fewer than five public ranking rows")

    works = []
    for expected_rank, (book_id, cells) in enumerate(parser.rows[:5], start=1):
        if len(cells) < 6 or not book_id or cells[0] != str(expected_rank):
            raise ValueError(f"{category}: incomplete or unordered rank {expected_rank}")
        title, author = cells[1:3]
        if len(title) < 2 or not author or any(0xE000 <= ord(ch) <= 0xF8FF for ch in title):
            raise ValueError(f"{category}: unreadable title or author at rank {expected_rank}")
        works.append(
            {
                "rank": expected_rank,
                "title": title,
                "author": author,
                "readers_display": cells[3],
                "latest_chapter": cells[4],
                "status": cells[5],
                "source_book_id": book_id,
            }
        )
    return data_date, works


def fetch(category: str) -> tuple[str, list[dict]]:
    request = Request(
        source_url(category),
        headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
    )
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError(f"{category}: HTTP {response.status}")
        page = response.read(2_000_000).decode("utf-8", errors="replace")
    return parse_ranking(page, category)


def collect(now: dt.datetime) -> dict:
    sections = []
    dates = set()
    for category in CATEGORIES:
        data_date, works = fetch(category)
        dates.add(data_date)
        sections.append(
            {
                "category": category,
                "ranking": "女频新书榜",
                "source_url": source_url(category),
                "works": works,
            }
        )
    if len(dates) != 1:
        raise ValueError(f"ranking pages disagree on data date: {sorted(dates)}")
    data_date = dates.pop()
    age = now.date() - dt.date.fromisoformat(data_date)
    if not 0 <= age.days <= 1:
        raise ValueError(f"ranking date is not current: {data_date}")
    return {
        "schema_version": "ranking-snapshot/v1",
        "data_date": data_date,
        "observed_at": now.isoformat(timespec="seconds"),
        "source": {
            "name": "番茄小说趋势分析平台",
            "authority": "third_party_aggregator",
            "platform_covered": "番茄小说",
            "scope": "女频长篇新书榜；不属于番茄短故事榜",
            "metric_note": "排名和在读数按来源公开页面记录，未与番茄官方逐项核对",
        },
        "sections": sections,
    }


def save(snapshot: dict, output_root: Path) -> tuple[Path, str]:
    path = output_root / snapshot["data_date"] / "fanqie-female-new.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        comparable_previous = {k: v for k, v in previous.items() if k != "observed_at"}
        comparable_new = {k: v for k, v in snapshot.items() if k != "observed_at"}
        if comparable_previous == comparable_new:
            return path, "unchanged"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, "published"


def main() -> None:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--output-root", type=Path, default=Path("market-intel"))
    args = argument_parser.parse_args()
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    path, status = save(collect(now), args.output_root)
    print(json.dumps({"status": status, "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
