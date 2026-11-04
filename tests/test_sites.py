import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fetch_sites import parse_rankings, render

class SiteRankingTests(unittest.TestCase):
    def test_heiyan_rankings_and_only_book_links(self):
        markup = '<h5>新书榜</h5><a href="/book/123">纸钱儿</a><a href="/top">更多</a><a href="https://spam.net/book/123">广告</a><h5>点击榜</h5><a href="/book/456">棺香美人</a>'
        r = parse_rankings(markup,"heiyan","https://www.heiyan.com/top/")
        self.assertEqual([x["ranking"] for x in r],["新书榜","点击榜"])
        self.assertEqual([x["items"][0]["title"] for x in r],["纸钱儿","棺香美人"])

    def test_jiuzhou_female_rankings(self):
        markup = '<h2>新书榜·女频</h2><a href="/book/abc">她和遗像团圆</a><h2>畅销榜·女频</h2><a href="/novel/xy">豆腐美人</a>'
        r = parse_rankings(markup,"jzzwxs","https://jzzwxs.com/")
        self.assertEqual([x["ranking"] for x in r],["新书榜·女频","畅销榜·女频"])

    def test_empty_results_are_not_fabricated(self):
        self.assertEqual(parse_rankings("<h1>榜单</h1><p>加载中</p>","jzzwxs","https://jzzwxs.com/"),[])

    def test_failure_status_visible(self):
        s={"snapshot_date":"2026-11-04","sources":[{"name":"黑岩","url":"https://www.heiyan.com/top/","status":"fetch_error","error":"blocked","sections":[]}]}
        self.assertIn("fetch_error",render(s))
if __name__ == "__main__":
    unittest.main()
