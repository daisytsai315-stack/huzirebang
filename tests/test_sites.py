import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fetch_sites import parse_rankings, render

class SiteRankingTests(unittest.TestCase):
    def test_site_registry_rejects_unconfigured_heiyan(self):
        with self.assertRaises(KeyError):
            parse_rankings("<h5>新书榜</h5>", "heiyan", "https://www.heiyan.com/top/")

    def test_jiuzhou_female_rankings(self):
        markup = '<h2>新书榜·女频</h2><a href="/book/abc">她和遗像团圆</a><h2>畅销榜·女频</h2><a href="/novel/xy">豆腐美人</a>'
        r = parse_rankings(markup,"jzzwxs","https://jzzwxs.com/")
        self.assertEqual([x["ranking"] for x in r],["新书榜·女频","畅销榜·女频"])

    def test_empty_results_are_not_fabricated(self):
        self.assertEqual(parse_rankings("<h1>榜单</h1><p>加载中</p>","jzzwxs","https://jzzwxs.com/"),[])

    def test_failure_status_visible(self):
        s={"snapshot_date":"2026-11-04","sources":[{"name":"九州","url":"https://jzzwxs.com/","status":"fetch_error","error":"blocked","sections":[]}]}
        self.assertIn("fetch_error",render(s))
if __name__ == "__main__":
    unittest.main()
