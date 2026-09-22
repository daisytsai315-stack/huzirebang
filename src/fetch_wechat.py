#!/usr/bin/env python3
"""Fetch selected public WeChat articles and write stable market snapshots.

The parser intentionally stores article-level market material (titles and the
source article's own introductions), not the full text of linked works.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


SECTION_TYPES = ("zhihu_hot", "submission_call", "example_text", "trend_summary")
SECTION_LABELS = {
    "zhihu_hot": "知乎热门",
    "submission_call": "编辑收文",
    "example_text": "例文",
    "trend_summary": "趋势总结",
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)
TAG_RULES = {
    "追妻": ("追妻", "追回", "后悔"),
    "替身": ("替身", "替代"),
    "重生": ("重生", "重来一次"),
    "穿越": ("穿越", "穿成"),
    "弹幕": ("弹幕",),
    "失忆": ("失忆",),
    "白月光": ("白月光",),
    "真假千金": ("假千金", "真千金"),
    "女尊": ("女尊",),
    "古言": ("皇帝", "王爷", "郡主", "太子", "侯府", "入府"),
    "豪门": ("豪门", "富二代", "京圈", "总裁"),
    "网恋": ("网恋",),
    "婚姻": ("结婚", "婚礼", "丈夫", "老公", "离婚"),
    "小青梅": ("青梅",),
}


def fetch_html(url: str, retries: int = 3, timeout: int = 30) -> str:
    """Fetch a public article with bounded retries."""

    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"无法读取 {url}: {last_error}")


def make_session_opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def fetch_with_opener(opener, url: str, timeout: int = 30, referer: str = "") -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        headers["Referer"] = referer
    request = Request(url, headers=headers)
    with opener.open(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def first_group(pattern: str, text: str, flags: int = re.I | re.S) -> str:
    match = re.search(pattern, text, flags)
    return html.unescape(match.group(1)).strip() if match else ""


def decode_js_string(value: str) -> str:
    """Decode the ASCII escapes used by WeChat without corrupting real CJK text."""

    value = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), value)
    value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value)
    replacements = {r"\n": "\n", r"\r": "\r", r"\t": "\t", r"\'": "'", r'\"': '"', r"\\": "\\"}
    for source, target in replacements.items():
        value = value.replace(source, target)
    return html.unescape(value)


def extract_article_fragment(page: str) -> str:
    encoded = first_group(r"content_noencode:\s*'((?:\\.|[^'])*)',\s*create_time", page)
    if encoded:
        return decode_js_string(encoded)

    match = re.search(r'<div[^>]+id=["\']js_content["\'][^>]*>(.*?)</div>\s*</div>', page, re.I | re.S)
    if match:
        return html.unescape(match.group(1))
    raise ValueError("页面中未找到 content_noencode 或 #js_content")


def clean_html_fragment(fragment: str) -> str:
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = html.unescape(fragment)
    fragment = fragment.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in fragment.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def extract_paragraphs(fragment: str) -> list[str]:
    paragraphs = []
    matches = re.findall(r"<p\b[^>]*>(.*?)</p>", fragment, flags=re.I | re.S)
    if not matches:
        text = clean_html_fragment(fragment)
        return [text] if text else []
    for match in matches:
        text = clean_html_fragment(match)
        if text:
            paragraphs.append(text)
    return paragraphs


def classify_article(title: str, body: str) -> str:
    combined = f"{title}\n{body}"
    if "例文" in title or "例文榜" in title:
        return "example_text"
    if any(token in title for token in ("收文", "收稿", "说稿")):
        return "submission_call"
    if any(token in title for token in ("知乎", "热榜", "热文", "开单")):
        return "zhihu_hot"
    if any(token in title for token in ("趋势", "风向", "总结")):
        return "trend_summary"
    if "知乎" in combined:
        return "zhihu_hot"
    return "trend_summary"


def infer_tags(title: str, intro: str) -> list[str]:
    text = f"{title}\n{intro}"
    return [label for label, needles in TAG_RULES.items() if any(needle in text for needle in needles)]


def parse_top_items(fragment: str) -> list[dict]:
    paragraphs = extract_paragraphs(fragment)
    entries: list[dict] = []
    current: dict | None = None
    top_pattern = re.compile(r"^TOP\s*(\d{1,3})\s*(.*)$", re.I | re.S)

    for paragraph in paragraphs:
        match = top_pattern.match(paragraph)
        if match:
            if current:
                current["intro"] = "\n".join(current.pop("_intro_parts")).strip()
                current["tags"] = infer_tags(current["title"], current["intro"])
                entries.append(current)
            rank = int(match.group(1))
            remainder = match.group(2).strip()
            title_match = re.search(r"(《.*?》)", remainder)
            if title_match:
                title = title_match.group(1).strip("《》")
                remainder = remainder[title_match.end():].strip()
            else:
                title, remainder = remainder, ""
            current = {
                "rank": rank,
                "title": title.strip(),
                "author": "",
                "intro": "",
                "tags": [],
                "work_url": "",
                "_intro_parts": [remainder] if remainder else [],
            }
        elif current:
            current["_intro_parts"].append(paragraph)

    if current:
        current["intro"] = "\n".join(current.pop("_intro_parts")).strip()
        current["tags"] = infer_tags(current["title"], current["intro"])
        entries.append(current)
    return entries


def parse_rss_entries(feed_xml: str, limit: int = 10) -> list[dict]:
    """Read a standard RSS/Atom feed used as the daily article discovery layer."""

    root = ET.fromstring(feed_xml)
    entries = []
    nodes = list(root.findall(".//item"))
    if not nodes:
        nodes = list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
    for node in nodes[:limit]:
        def child_text(*names: str) -> str:
            for name in names:
                child = node.find(name)
                if child is not None and child.text:
                    return child.text.strip()
            return ""

        link = child_text("link")
        if not link:
            atom_link = node.find("{http://www.w3.org/2005/Atom}link")
            link = (atom_link.get("href", "") if atom_link is not None else "").strip()
        if link:
            entries.append({
                "title": child_text("title", "{http://www.w3.org/2005/Atom}title"),
                "url": link,
                "published_at": child_text("pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"),
            })
    return entries


def parse_sogou_candidates(search_html: str, limit: int = 3) -> list[dict]:
    """Extract public search-result jump links and snippets from Sogou WeChat search."""

    pattern = re.compile(
        r'<a(?=[^>]*id="sogou_vr_11002601_title_(\d+)")(?=[^>]*href="([^"]+)")[^>]*>(.*?)</a>'
        r'.*?<p[^>]+class="txt-info"[^>]*>(.*?)</p>',
        re.I | re.S,
    )
    candidates = []
    for _, href, title_html, summary_html in pattern.findall(search_html):
        candidates.append({
            "title": clean_html_fragment(title_html),
            "summary": clean_html_fragment(summary_html),
            "jump_url": re.sub(r"\s+", "", html.unescape(href).replace("&amp;", "&")),
        })
        if len(candidates) >= limit:
            break
    return candidates


def resolve_sogou_jump(opener, jump_url: str, search_url: str) -> str:
    """Resolve Sogou's public JS redirect to the original WeChat article URL."""

    absolute = jump_url if jump_url.startswith("http") else "https://weixin.sogou.com" + jump_url
    jump_html = fetch_with_opener(opener, absolute, referer=search_url)
    pieces = re.findall(r"url\s*\+=\s*'([^']*)'", jump_html)
    target = "".join(pieces).replace("@", "")
    if target.startswith("https://mp.weixin.qq.com/"):
        return target
    raise ValueError("搜狗结果未返回可用的公众号文章地址")


def discover_sogou_articles(queries: list[str], max_items_per_query: int = 2, target_date: str = "") -> list[dict]:
    discovered = []
    seen = set()
    target = dt.date.fromisoformat(target_date) if target_date else None
    for query in queries:
        opener = make_session_opener()
        date_query = "{date}" in query
        if target:
            query = query.format(
                date=f"{target.month}月{target.day}日",
                month=target.month,
                day=target.day,
                year=target.year,
            )
        search_url = "https://weixin.sogou.com/weixin?type=2&query=" + quote_plus(query)
        search_html = fetch_with_opener(opener, search_url)
        candidates = parse_sogou_candidates(search_html, max_items_per_query * 5)
        if target and date_query:
            marker = f"{target.month}月{target.day}日"
            dated = [candidate for candidate in candidates if marker in candidate["title"] or marker in candidate["summary"]]
            if dated:
                candidates = dated
        for candidate in candidates[:max_items_per_query]:
            url = resolve_sogou_jump(opener, candidate["jump_url"], search_url)
            if url not in seen:
                seen.add(url)
                discovered.append({"url": url, "query": query, "search_title": candidate["title"], "search_summary": candidate["summary"]})
    return discovered


def empty_sections() -> list[dict]:
    return [{"type": section_type, "items": []} for section_type in SECTION_TYPES]


def parse_source_html(url: str, page: str, source_name_hint: str = "") -> dict:
    title = first_group(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', page)
    if not title:
        title = first_group(r"var msg_title\s*=\s*'((?:\\.|[^'])*)'", page)
    source_name = first_group(r"nick_name:\s*'((?:\\.|[^'])*)'", page) or source_name_hint
    author = first_group(r'<meta[^>]+property=["\']og:article:author["\'][^>]+content=["\'](.*?)["\']', page)
    create_time = first_group(r"create_time:\s*'([^']+)'", page)
    published_at = create_time[:10] if re.match(r"\d{4}-\d{2}-\d{2}", create_time) else ""
    fragment = extract_article_fragment(page)
    body = "\n".join(extract_paragraphs(fragment))
    active_type = classify_article(title, body)
    sections = empty_sections()
    items = parse_top_items(fragment)
    section = next(item for item in sections if item["type"] == active_type)
    section["items"] = items

    if active_type == "submission_call" and not items:
        section["items"] = [{
            "editor": author or source_name,
            "platform": "",
            "request": body,
            "examples": [],
            "notes": "",
        }]

    return {
        "source_name": source_name,
        "article_title": title,
        "author": author,
        "published_at": published_at,
        "source_url": url,
        "sections": sections,
    }


def build_snapshot(sources: list[dict], snapshot_date: str) -> dict:
    parsed_sources = []
    errors = []
    for source in sources:
        discovered = []
        if source.get("sogou_queries"):
            try:
                discovered = discover_sogou_articles(
                    source["sogou_queries"],
                    int(source.get("max_items_per_query", 2)),
                    snapshot_date,
                )
                if not discovered:
                    errors.append({"source_url": "搜狗微信搜索", "error": "没有发现匹配的公众号文章"})
            except Exception as exc:
                errors.append({"source_url": "搜狗微信搜索", "error": str(exc)})
        elif source.get("feed_url"):
            try:
                feed = fetch_html(source["feed_url"])
                discovered = parse_rss_entries(feed, int(source.get("max_items", 10)))
                if not discovered:
                    errors.append({"source_url": source["feed_url"], "error": "订阅源没有返回文章条目"})
            except Exception as exc:
                errors.append({"source_url": source["feed_url"], "error": str(exc)})
        elif source.get("url"):
            discovered = [{"url": source["url"]}]
        else:
            errors.append({"source_url": "", "error": "来源缺少 url 或 feed_url"})

        for entry in discovered:
            url = entry["url"]
            try:
                page = fetch_html(url)
                parsed_sources.append(parse_source_html(url, page, source.get("source_name_hint", "")))
            except Exception as exc:  # keep one failing source from hiding others
                errors.append({"source_url": url, "error": str(exc)})
    snapshot = {"snapshot_date": snapshot_date, "sources": parsed_sources}
    if errors:
        snapshot["errors"] = errors
    return snapshot


def render_markdown(snapshot: dict) -> str:
    lines = [f"# {snapshot['snapshot_date']} 短篇市场快照", ""]
    if snapshot.get("errors"):
        lines.extend(["> 注意：以下来源抓取失败，详见 latest.json 的 errors。", ""])
    for source in snapshot["sources"]:
        lines.extend([
            f"## {source['source_name'] or '未识别公众号'}｜{source['article_title']}",
            f"- 公众号发布时间：{source['published_at'] or '未识别'}",
            f"- 原文链接：{source['source_url']}",
            "",
        ])
        for section in source["sections"]:
            lines.append(f"### {SECTION_LABELS[section['type']]}")
            if not section["items"]:
                lines.extend(["- 今日未检测到该栏目。", ""])
                continue
            for item in section["items"]:
                if section["type"] in ("zhihu_hot", "example_text"):
                    lines.append(f"#### {item.get('rank', '')}.《{item.get('title', '')}》")
                    lines.append(f"- 导语：{item.get('intro', '') or '未提供'}")
                    lines.append(f"- 标签：{'、'.join(item.get('tags', [])) or '未自动识别'}")
                    lines.append(f"- 原文链接：{source['source_url']}")
                else:
                    lines.append(f"#### {item.get('editor', '编辑/工作室')}")
                    lines.append(f"- 平台：{item.get('platform', '') or '未识别'}")
                    lines.append(f"- 最近要：{item.get('request', '') or '未提供'}")
                    lines.append(f"- 例文：{'、'.join(item.get('examples', [])) or '未识别'}")
                    lines.append(f"- 备注：{item.get('notes', '') or '未提供'}")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_snapshot(snapshot: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    (output_dir / "latest.json").write_text(payload, encoding="utf-8")
    (output_dir / "latest.md").write_text(render_markdown(snapshot), encoding="utf-8")
    archive_path = archive_dir / f"{snapshot['snapshot_date']}.json"
    if archive_path.exists():
        old = archive_path.read_text(encoding="utf-8")
        if old != payload:
            raise FileExistsError(f"归档已存在且内容不同，不覆盖：{archive_path}")
    else:
        archive_path.write_text(payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=Path("sources.json"))
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--date", default=dt.date.today().isoformat())
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    snapshot = build_snapshot(sources, args.date)
    write_snapshot(snapshot, args.output)
    print(json.dumps({"snapshot_date": args.date, "sources": len(snapshot["sources"]), "errors": len(snapshot.get("errors", []))}, ensure_ascii=False))
    return 0 if snapshot["sources"] else 1


if __name__ == "__main__":
    sys.exit(main())
