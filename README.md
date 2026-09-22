# WeChat Market Snapshot

这是一个轻量的微信公众号短篇市场快照器，面向每日定时读取的网页版 GPT。

它会：

- 抓取指定的公开公众号文章；
- 保留文章标题、公众号名称、发布时间、原文链接；
- 提取 `TOP N` 作品的标题、导语/简介和简单标签；
- 固定输出 `zhihu_hot`、`submission_call`、`example_text`、`trend_summary` 四类栏目；
- 生成 `data/latest.md`、`data/latest.json` 和 `data/archive/YYYY-MM-DD.json`；
- 通过 GitHub Actions 每天北京时间 10:00 运行一次，也支持手动运行。

## 每日自动发现新文章

当前 `sources.json` 已改为通过搜狗微信搜索按固定栏目关键词发现公众号的新文章，再解析搜索结果返回的原公众号链接；两条固定样本链接仍保留在 Git 历史中用于回归验证。

如果搜狗搜索源在 GitHub Actions 的运行环境中被限制，可以切换到一个一次性配置的 RSS/文章订阅地址：

```json
[
  {
    "source_name_hint": "短篇热榜例文-投稿168",
    "feed_url": "https://你的订阅服务/your-feed.xml",
    "max_items": 10
  }
]
```

`feed_url` 可以来自一次性配置的 Wechat2RSS、RSSHub 可用路由，或你有权限使用的官方数据源。GitHub Actions 会先读订阅源发现新文章，再抓取每篇公众号正文。公众号主页如果返回验证页，不能把它当作稳定的每日入口，也不应通过绕过验证来维持爬取。

当前两篇样本：

- `9月21日 知乎风短篇小说热榜` → `zhihu_hot`
- `9月22日 编辑收稿例文榜` → `example_text`

第二篇是“编辑收稿例文榜”，不是明确的投稿征集要求，因此不会被错误地伪装成 `submission_call`。

## 本地运行

```text
py -m unittest discover -s tests -v
py src/fetch_wechat.py --sources sources.json --output data --date 2026-09-22
```

## 发布前注意

仓库如果公开，`latest.md` 和 `latest.json` 也会公开。为了让无需登录的定时任务能读取稳定的 raw 地址，最简单的部署是公开仓库，但建议只保存市场层的标题、简介、日期和链接，不要把完整作品正文复制进仓库。若需要私有仓库，则定时任务必须具备相应的 GitHub 读取权限。
