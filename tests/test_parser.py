import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fetch_wechat import USER_AGENT, build_rank_history, build_snapshot, classify_article, detect_platform, discover_sogou_articles, parse_rss_entries, parse_sogou_candidates, parse_source_html, parse_top_items, publish_short_rankings, render_markdown  # noqa: E402


class ParserTests(unittest.TestCase):
    def test_public_fetch_uses_transparent_crawler_identity(self):
        self.assertTrue(USER_AGENT.startswith("huzirebang/1.0 "))
        self.assertNotIn("Mozilla/", USER_AGENT)

    def test_dated_search_retries_empty_first_result(self):
        result = '<h3><a href="/link?url=abc" id="sogou_vr_11002601_title_0">11月11日 小程序短篇榜</a></h3><p class="txt-info">TOP 1 《测试作品》</p>'
        with patch("fetch_wechat.fetch_with_opener", side_effect=["<html></html>", result]) as fetch, \
                patch("fetch_wechat.resolve_sogou_jump", return_value="https://mp.weixin.qq.com/s/today"), \
                patch("fetch_wechat.time.sleep"):
            found = discover_sogou_articles(["{date} 小程序短篇榜"], 1, "2026-11-11", ["小程序"])
        self.assertEqual(len(found), 1)
        self.assertEqual(fetch.call_count, 2)

    def test_dated_search_checks_previous_days_before_dropping_recent_sources(self):
        result = """
        <li><h3><a href="/link?url=yesterday" id="sogou_vr_11002601_title_0">11月17日 番茄风短篇小说热榜</a></h3>
        <p class="txt-info">TOP 1 《前一天真实作品》 公开导语</p>
        <div class="s-p"><span class="all-time-y2">短篇热榜例文-投稿168</span>
        <script>timeConvert('1794879168')</script></div></li>
        """

        def search_page(_opener, search_url):
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(search_url).query).get("query", [""])[0]
            return result if "11月17日" in query else "<html></html>"

        with patch("fetch_wechat.fetch_with_opener", side_effect=search_page) as fetch, \
                patch("fetch_wechat.resolve_sogou_jump", return_value="https://mp.weixin.qq.com/s/yesterday"), \
                patch("fetch_wechat.time.sleep"):
            found = discover_sogou_articles(
                ["{date} 番茄短故事热榜"], 1, "2026-11-18",
                ["番茄风短篇"], "投稿168", 3,
            )

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["query"], "11月17日 番茄短故事热榜")
        self.assertEqual(found[0]["search_published_at"], "2026-11-17")
        self.assertGreater(fetch.call_count, 2)

    def test_dated_search_keeps_candidate_without_exact_date_text(self):
        result = '<h3><a href="/link?url=abc" id="sogou_vr_11002601_title_0">小程序短篇精选榜</a></h3><p class="txt-info">TOP 1 《测试作品》</p>'
        with patch("fetch_wechat.fetch_with_opener", return_value=result):
            with patch("fetch_wechat.resolve_sogou_jump", return_value="https://mp.weixin.qq.com/s/today"):
                found = discover_sogou_articles(["{date} 小程序短篇榜"], 1, "2026-11-17", ["小程序"])
        self.assertEqual(len(found), 1)

    def test_market_export_uses_article_date_and_skips_duplicate(self):
        snapshot = {"sources": [{
            "parse_status": "parsed", "source_name_verified": True,
            "published_at": "2026-11-11", "source_name": "投稿168",
            "article_title": "11月11日 小程序榜", "source_url": "https://mp.weixin.qq.com/s/test",
            "sections": [{"type": "miniprogram_hot", "items": [{"rank": 1, "title": "作品甲"}]}],
        }]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(len(publish_short_rankings(snapshot, root)), 1)
            self.assertEqual(publish_short_rankings(snapshot, root), [])
            self.assertTrue((root / "2026-11-11" / "miniprogram-hot.json").exists())

    def test_top_items_keep_title_intro_and_tags(self):
        fragment = """
        <p>TOP 1 《重回遇见黄毛老公那天，我不要他了》</p>
        <p>将黄毛培养成清冷霸总后的第七年，他回家越来越晚。又一次独守空房后，眼前飘过弹幕。</p>
        <p>TOP 2 《白月光回港》</p>
        <p>女主回港，发现自己是炮灰白月光，男主失忆后再次爱上她。</p>
        """
        items = parse_top_items(fragment)
        self.assertEqual([item["rank"] for item in items], [1, 2])
        self.assertEqual(items[0]["title"], "重回遇见黄毛老公那天，我不要他了")
        self.assertIn("清冷霸总", items[0]["intro"])
        self.assertIn("弹幕", items[0]["tags"])
        self.assertIn("白月光", items[1]["tags"])
        self.assertIn("www.zhihu.com/search", items[0]["work_search_url"])
        self.assertEqual(items[0]["work_url"], "")

    def test_classification_prioritizes_example_text(self):
        self.assertEqual(classify_article("9月21日 知乎风短篇小说热榜", ""), "zhihu_hot")
        self.assertEqual(classify_article("9月22日 编辑收稿例文榜", ""), "example_text")
        self.assertEqual(classify_article("编辑收文方向与要求", ""), "submission_call")

    def test_source_has_stable_six_section_schema(self):
        page = """
        <meta property="og:title" content="9月21日 知乎风短篇小说热榜">
        <meta property="og:article:author" content="荔枝哥">
        <script>nick_name: '示例公众号', create_time: '2026-09-21 09:31',
        content_noencode: '\\x3cp\\x3eTOP 1 \\x3c《测试作品》\\x3e\\x3c/p\\x3e\\x3cp\\x3e简介\\x3c/p\\x3e', create_time</script>
        """
        parsed = parse_source_html("https://example.com/article", page, "兜底名称")
        self.assertEqual(parsed["article_title"], "9月21日 知乎风短篇小说热榜")
        self.assertEqual(parsed["published_at"], "2026-09-21")
        self.assertEqual([section["type"] for section in parsed["sections"]], [
            "zhihu_hot", "miniprogram_hot", "fanqie_short_hot", "submission_call", "example_text", "trend_summary"
        ])

    def test_commercial_short_story_classification(self):
        self.assertEqual(detect_platform("11月1日 小程序短篇热榜"), "miniprogram")
        self.assertEqual(detect_platform("11月1日 番茄短故事热榜"), "fanqie_short")
        self.assertEqual(detect_platform("番茄小说畅销榜"), "unknown")
        self.assertEqual(classify_article("11月1日 小程序短篇热榜", ""), "miniprogram_hot")
        self.assertEqual(classify_article("11月1日 番茄短故事热榜", ""), "fanqie_short_hot")
        self.assertEqual(classify_article("11月1日 编辑收稿例文榜", ""), "example_text")

    def test_commercial_titles_do_not_point_to_zhihu(self):
        source = "<p>TOP 1 《测试商业短篇》</p><p>导语内容</p>"
        mini = parse_top_items(source, "miniprogram")
        fanqie = parse_top_items(source, "fanqie_short")
        self.assertIn("www.baidu.com/s?", mini[0]["work_search_url"])
        self.assertIn("%E5%B0%8F%E7%A8%8B%E5%BA%8F", mini[0]["work_search_url"])
        self.assertIn("www.baidu.com/s?", fanqie[0]["work_search_url"])
        self.assertNotIn("zhihu.com", fanqie[0]["work_search_url"])

    def test_rss_entries_are_a_daily_discovery_layer(self):
        feed = """
        <rss><channel>
          <item><title>今天的知乎热榜</title><link>https://mp.weixin.qq.com/s/today</link><pubDate>Tue, 22 Sep 2026 09:31:00 +0800</pubDate></item>
        </channel></rss>
        """
        entries = parse_rss_entries(feed)
        self.assertEqual(entries[0]["title"], "今天的知乎热榜")
        self.assertEqual(entries[0]["url"], "https://mp.weixin.qq.com/s/today")

    def test_sogou_candidates_support_heading_link_without_legacy_id(self):
        search_html = """
        <div class="vrwrap"><h3><a target="_blank" href="/link?url=abc&amp;type=2">11月18日 小程序短篇榜</a></h3>
        <p class="txt-info">TOP 1 《测试作品》</p></div>
        """
        candidates = parse_sogou_candidates(search_html)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["title"], "11月18日 小程序短篇榜")
        self.assertEqual(candidates[0]["jump_url"], "/link?url=abc&type=2")

    def test_sogou_candidates_support_public_jump_anchor_outside_heading(self):
        search_html = """
        <div class="result"><a href="/link?url=abc&amp;type=2">小程序短篇榜</a>
        <p class="txt-info">TOP 1 《测试作品》</p></div>
        """
        candidates = parse_sogou_candidates(search_html)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["title"], "小程序短篇榜")
        self.assertEqual(candidates[0]["jump_url"], "/link?url=abc&type=2")

    def test_sogou_candidates_keep_title_summary_and_jump_url(self):
        search_html = """
        <h3><a href="/link?url=abc&amp;type=2" id="sogou_vr_11002601_title_0">9月22日 <em>知乎风</em></a></h3>
        <p class="txt-info">TOP 1 《测试作品》 简介片段</p>
        """
        candidates = parse_sogou_candidates(search_html)
        self.assertEqual(candidates[0]["title"], "9月22日 知乎风")
        self.assertEqual(candidates[0]["summary"], "TOP 1 《测试作品》 简介片段")
        self.assertEqual(candidates[0]["jump_url"], "/link?url=abc&type=2")

    def test_sogou_candidates_include_publisher_and_search_timestamp(self):
        search_html = """
        <li><h3><a href="/link?url=abc" id="sogou_vr_11002601_title_0">11月18日 小程序风短篇小说热榜</a></h3>
        <p class="txt-info">TOP 1 《测试作品》 真实摘要片段...</p>
        <div class="s-p"><span class="all-time-y2">短篇热榜例文-投稿168</span>
        <script>document.write(timeConvert('1794965572'))</script></div></li>
        """
        candidate = parse_sogou_candidates(search_html)[0]
        self.assertEqual(candidate["source_name"], "短篇热榜例文-投稿168")
        self.assertEqual(candidate["search_published_at"], "2026-11-18")

    def test_discovery_keeps_only_recent_results_from_the_configured_account(self):
        result = """
        <li><h3><a href="/link?url=older" id="sogou_vr_11002601_title_0">11月16日 番茄风短篇小说热榜</a></h3>
        <p class="txt-info">TOP 1 《较早作品》</p>
        <div class="s-p"><span class="all-time-y2">短篇热榜例文-投稿168</span><script>timeConvert('1794792766')</script></div></li>
        <li><h3><a href="/link?url=old" id="sogou_vr_11002601_title_1">11月15日 番茄风短篇小说热榜</a></h3>
        <p class="txt-info">TOP 1 《旧作品》</p>
        <div class="s-p"><span class="all-time-y2">短篇热榜例文-投稿168</span><script>timeConvert('1794706359')</script></div></li>
        <li><h3><a href="/link?url=foreign" id="sogou_vr_11002601_title_2">11月18日 番茄风短篇小说热榜</a></h3>
        <p class="txt-info">TOP 1 《误匹配作品》</p>
        <div class="s-p"><span class="all-time-y2">其他公众号</span><script>timeConvert('1794965572')</script></div></li>
        <li><h3><a href="/link?url=current" id="sogou_vr_11002601_title_3">11月18日 番茄风短篇小说热榜</a></h3>
        <p class="txt-info">TOP 1 《今日作品》 今日摘要</p>
        <div class="s-p"><span class="all-time-y2">短篇热榜例文-投稿168</span><script>timeConvert('1794965572')</script></div></li>
        """
        with patch("fetch_wechat.fetch_with_opener", return_value=result), \
                patch("fetch_wechat.resolve_sogou_jump", return_value="https://mp.weixin.qq.com/s/current"):
            found = discover_sogou_articles(
                ["番茄风短篇小说热榜"], 1, "2026-11-18", ["番茄风短篇"], "投稿168", 3
            )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["search_title"], "11月18日 番茄风短篇小说热榜")
        self.assertEqual(found[0]["search_source_name"], "短篇热榜例文-投稿168")
        self.assertEqual(found[0]["search_published_at"], "2026-11-18")

    def test_public_search_excerpt_survives_wechat_access_challenge(self):
        source = {
            "source_name_hint": "短篇热榜例文-投稿168",
            "platform_hint": "miniprogram",
            "sogou_queries": ["{date} 小程序风短篇小说热榜"],
            "max_age_days": 3,
            "title_any": ["小程序"],
            "source_name_contains": "投稿168",
        }
        entry = {
            "url": "https://mp.weixin.qq.com/s/public-article",
            "search_url": "https://weixin.sogou.com/weixin?type=2&query=public",
            "search_title": "11月18日 小程序风短篇小说热榜",
            "search_summary": "TOP 1 《真实短篇作品》 这是搜狗公开摘要里的真实导语片段...",
            "search_source_name": "短篇热榜例文-投稿168",
            "search_published_at": "2026-11-18",
        }
        challenge_page = "<html><body>public WeChat access challenge</body></html>"
        blocked_url = "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?target_url=public"
        with patch("fetch_wechat.discover_sogou_articles", return_value=[entry]), \
                patch("fetch_wechat.fetch_html_with_final_url", return_value=(challenge_page, blocked_url)):
            snapshot = build_snapshot([source], "2026-11-18")

        item_source = snapshot["sources"][0]
        self.assertEqual(item_source["parse_status"], "public_search_excerpt")
        self.assertTrue(item_source["source_name_verified"])
        self.assertEqual(item_source["published_at"], "2026-11-18")
        self.assertEqual(item_source["sections"][1]["items"][0]["title"], "真实短篇作品")
        self.assertIn("非完整榜单", render_markdown(snapshot))

    def test_excerpt_is_exported_separately_from_complete_ranking(self):
        snapshot = {"sources": [{
            "parse_status": "public_search_excerpt", "source_name_verified": True,
            "published_at": "2026-11-18", "source_name": "短篇热榜例文-投稿168",
            "article_title": "11月18日 小程序风短篇小说热榜",
            "source_url": "https://mp.weixin.qq.com/s/public-article",
            "search_url": "https://weixin.sogou.com/weixin?type=2&query=public",
            "sections": [{"type": "miniprogram_hot", "items": [{"rank": 1, "title": "作品甲"}]}],
        }]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = publish_short_rankings(snapshot, root)
            self.assertEqual(len(paths), 1)
            self.assertTrue((root / "2026-11-18" / "miniprogram-hot-search-excerpt.json").exists())
            self.assertFalse((root / "2026-11-18" / "miniprogram-hot.json").exists())
            self.assertEqual(build_rank_history(snapshot, root, "miniprogram_hot"), [])


if __name__ == "__main__":
    unittest.main()

