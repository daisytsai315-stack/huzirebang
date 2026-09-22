import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fetch_wechat import classify_article, parse_rss_entries, parse_sogou_candidates, parse_source_html, parse_top_items  # noqa: E402


class ParserTests(unittest.TestCase):
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

    def test_classification_prioritizes_example_text(self):
        self.assertEqual(classify_article("9月21日 知乎风短篇小说热榜", ""), "zhihu_hot")
        self.assertEqual(classify_article("9月22日 编辑收稿例文榜", ""), "example_text")
        self.assertEqual(classify_article("编辑收文方向与要求", ""), "submission_call")

    def test_source_has_stable_four_section_schema(self):
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
            "zhihu_hot", "submission_call", "example_text", "trend_summary"
        ])

    def test_rss_entries_are_a_daily_discovery_layer(self):
        feed = """
        <rss><channel>
          <item><title>今天的知乎热榜</title><link>https://mp.weixin.qq.com/s/today</link><pubDate>Tue, 22 Sep 2026 09:31:00 +0800</pubDate></item>
        </channel></rss>
        """
        entries = parse_rss_entries(feed)
        self.assertEqual(entries[0]["title"], "今天的知乎热榜")
        self.assertEqual(entries[0]["url"], "https://mp.weixin.qq.com/s/today")

    def test_sogou_candidates_keep_title_summary_and_jump_url(self):
        search_html = """
        <h3><a href="/link?url=abc&amp;type=2" id="sogou_vr_11002601_title_0">9月22日 <em>知乎风</em></a></h3>
        <p class="txt-info">TOP 1 《测试作品》 简介片段</p>
        """
        candidates = parse_sogou_candidates(search_html)
        self.assertEqual(candidates[0]["title"], "9月22日 知乎风")
        self.assertEqual(candidates[0]["summary"], "TOP 1 《测试作品》 简介片段")
        self.assertEqual(candidates[0]["jump_url"], "/link?url=abc&type=2")


if __name__ == "__main__":
    unittest.main()
