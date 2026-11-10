import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fetch_zhihu_story_ranking import parse, save


class ZhihuStoryRankingTests(unittest.TestCase):
    def test_rejects_incomplete_ranking(self):
        with self.assertRaises(ValueError):
            parse({"data": [{"title": "Only one"}]}, None)

    def test_cross_day_unchanged_ranking_does_not_create_new_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = {"snapshot_date": "2026-11-10", "observed_at": "first", "works": [{"rank": 1, "title": "甲"}]}
            old_path, status = save(first, root)
            self.assertEqual(status, "published")

            next_day = copy.deepcopy(first)
            next_day["snapshot_date"] = "2026-11-11"
            next_day["observed_at"] = "second"
            path, status = save(next_day, root)
            self.assertEqual((path, status), (old_path, "unchanged"))
            self.assertFalse((root / "2026-11-11" / "zhihu-story-ranking.json").exists())

            next_day["works"][0]["title"] = "乙"
            path, status = save(next_day, root)
            self.assertEqual(status, "published")
            self.assertEqual(path.parent.name, "2026-11-11")


if __name__ == "__main__":
    unittest.main()

