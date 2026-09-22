# 每日信息站读取规则

每天分析前，先读取：

```text
https://raw.githubusercontent.com/<OWNER>/<REPOSITORY>/main/data/latest.md
```

如果需要去重、比较连续出现天数，再读取：

```text
https://raw.githubusercontent.com/<OWNER>/<REPOSITORY>/main/data/latest.json
```

规则：

1. 先报告快照的抓取日期和抓取错误，不要把“没有读取到”伪装成“没有更新”。
2. 优先看 `zhihu_hot`、`submission_call`、`example_text`、`trend_summary` 四类栏目。
3. 热门作品必须至少保留标题、导语/简介、公众号发布时间；如果存在 `work_url`，它才是已验证的知乎原文，否则使用 `work_search_url` 进入知乎站内标题检索。
4. 优先读取 `rank_history` 和 `rank_changes`，判断哪些作品连续上榜、哪些掉榜、哪些是新上榜或排名明显上升；单日出现只能称为样本，不能直接称为趋势。
5. 公众号文章中的简介是市场样本，不等于完整作品正文；需要作品级核验时，优先打开 `work_url`，没有直链时再打开 `work_search_url`，不要把公众号文章地址当成作品原文。
6. `example_text` 表示编辑收稿例文/参考稿；只有文章明确提出投稿要求时，才归入 `submission_call`。
7. 如果 `latest.json` 有 `errors`，先报告错误来源；不要把抓取失败解释为公众号当天没有更新。
8. 快照由 GitHub Actions 自动发现并更新；如果 `snapshot_date` 没有变化，先检查 `errors`，不要把旧快照当成当天的新样本。
