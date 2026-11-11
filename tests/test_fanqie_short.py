import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fetch_fanqie_short import parse


class FanqieShortTests(unittest.TestCase):
    def test_dated_short_story_table(self):
        rows = "".join(
            f'<tr><td>{n}</td><td><a href="/short/{n}">作品{n}</a></td>'
            f'<td>婚姻家庭</td><td>复仇</td><td>作者{n}</td><td>10.0</td>'
            f'<td>1.2</td><td>1周</td><td>10 · 2</td><td>+1.0</td></tr>'
            for n in range(1, 6)
        )
        page = "数据更新日 2026-11-10<table>" + rows + "</table>"
        now = dt.datetime(2026, 11, 11, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        snapshot = parse(page, now)
        self.assertEqual(snapshot["data_date"], "2026-11-10")
        self.assertEqual(len(snapshot["works"]), 5)
        self.assertEqual(snapshot["works"][0]["source_work_url"], "https://novelcatch.com/short/1")

    def test_stale_date_rejected(self):
        now = dt.datetime(2026, 11, 11, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        with self.assertRaises(ValueError):
            parse("数据更新日 2026-11-01", now)

