#!/usr/bin/env python3
"""Fetch public novel ranking metadata; never collect copyrighted full text."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

USER_AGENT = "Mozilla/5.0 (compatible; NovelMarketSnapshot/1.0; public metadata only)"
HEADINGS = {
    "jzzwxs": ["新书榜·女频", "畅销榜·女频", "签约新书", "新书榜·男频", "畅销榜·男频"],
    "heiyan": ["新书榜", "热门榜", "点击榜", "订阅榜"],
}


class PageEvents(HTMLParser):
    """Read heading/link order while ignoring scripts and page furnishings."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events: list[tuple[str, str, str]] = []
        self.heading: list[str] | None = None
        self.anchor: list[str] | None = None
        self.anchor_href = ""
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if self.hidden:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.heading = []
        if tag == "a" and self.anchor is None:
            self.anchor = []
            self.anchor_href = attrs.get("href", "")

    def handle_data(self, data):
        if self.hidden:
            return
        if self.heading is not None:
            self.heading.append(data)
        if self.anchor is not None:
            self.anchor.append(data)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag == "a" and self.anchor is not None:
            label = re.sub(r"\s+", " ", "".join(self.anchor)).strip()
            self.events.append(("link", label, self.anchor_href))
            self.anchor = None
            self.anchor_href = ""
        if re.fullmatch(r"h[1-6]", tag) and self.heading is not None:
            label = re.sub(r"\s+", " ", "".join(self.heading)).strip()
            self.events.append(("heading", label, ""))
            self.heading = None


def normalise(text: str) -> str:
    return re.sub(r"\s+", "", html.unescape(text)).replace("•", "·")


def is_book_link(site: str, url: str) -> bool:
    path = urlparse(url).path.lower()
    if site == "heiyan":
        return bool(re.match(r"^/book/\d+(?:/)?$", path))
    return any(part in path for part in ("/book/", "/novel/", "/story/", "/detail/", "/work/"))


def parse_rankings(page: str, site: str, base_url: str, max_per_rank: int = 10) -> list[dict]:
    parser = PageEvents()
    parser.feed(page)
    sections: dict[str, list[dict]] = {}
    active: str | None = None
    allowed = HEADINGS[site]
    seen: dict[str, set[str]] = {}
    home_host = urlparse(base_url).hostname or ""
    for kind, label, href in parser.events:
        key = normalise(label)
        if kind == "heading":
            matched = next((name for name in allowed if normalise(name) == key), None)
            active = matched
            if matched:
                sections.setdefault(matched, [])
                seen.setdefault(matched, set())
            continue
        if not active or not href or not label or len(label) > 100:
            continue
        url = urljoin(base_url, href)
        host = urlparse(url).hostname or ""
        if host != home_host or not is_book_link(site, url):
            continue
        if url in seen[active] or len(sections[active]) >= max_per_rank:
            continue
        seen[active].add(url)
        sections[active].append({"position": len(sections[active]) + 1, "title": label.strip(), "work_url": url})
    return [{"ranking": name, "items": sections[name]} for name in allowed if sections.get(name)]


def get_public_page(url: str, timeout: int = 18) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    with urlopen(req, timeout=timeout) as response:
        return response.read(2_500_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def run(sources: list[dict], date: str) -> dict:
    out = {"snapshot_date": date, "scope": "official_site_rankings_metadata_only", "sources": []}
    for source in sources:
        item = {"site": source["site"], "name": source["name"], "url": source["url"], "checked_at_date": date, "status": "unverified", "sections": []}
        try:
            page = get_public_page(source["url"])
            item["sections"] = parse_rankings(page, source["site"], source["url"])
            item["status"] = "parsed" if item["sections"] else "no_extractable_ranked_books"
            if not item["sections"]:
                item["error"] = "页面未找到可核实的作品直链与榜单分组；可能是JS动态页面或网页结构已变化"
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            item["status"] = "fetch_error"
            item["error"] = str(exc)[:300]
        out["sources"].append(item)
    return out


def render(snapshot: dict) -> str:
    lines = [f"# {snapshot['snapshot_date']} 官网新书/热榜元信息", "", "> 来源为各站实时公开页面，抓取日不等于作品上架日。排名仅按页面顺序记录，不是全平台销量证据。", ""]
    for s in snapshot["sources"]:
        lines.extend([f"## {s['name']}｜{s['status']}", f"- 官网：{s['url']}", f"- 未完成项：{s.get('error', '无')}", ""])
        for sec in s["sections"]:
            lines.append(f"### {sec['ranking']}")
            lines.extend(f"- {v['position']}. 《{v['title']}》：{v['work_url']}" for v in sec["items"])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sources", type=Path, default=Path("sources.sites.json"))
    p.add_argument("--output", type=Path, default=Path("data/site_rankings"))
    p.add_argument("--date", default=dt.date.today().isoformat())
    args = p.parse_args()
    result = run(json.loads(args.sources.read_text(encoding="utf-8")), args.date)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "archive").mkdir(exist_ok=True)
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    (args.output / "latest.json").write_text(body, encoding="utf-8")
    (args.output / "latest.md").write_text(render(result), encoding="utf-8")
    (args.output / "archive" / f"{args.date}.json").write_text(body, encoding="utf-8")
    print(json.dumps({"date": args.date, "statuses": {x["site"]: x["status"] for x in result["sources"]}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
