# 投稿168公众号快照：每日读取和创作用途

## 2026-11-04 黑岩故事会纠错 / 每日商业选题

**纠正信源**：用户说的「黑岩」实际是**黑岩故事会**（短篇/小程序故事），不是黑岩网长篇 `www.heiyan.com`。此前长篇榜单采集已禁用。不要从 `heiyan.com/top/` 获取内容再标注成「黑岩故事会」，不得把两个来源混用。

`data/site_rankings/latest.json` 暂时只有九州中文网独立官网榜单。黑岩故事会目前为 `SOURCE_PENDING / PLATFORM_NOT_VERIFIED`，只在找到官方可核实公开入口、真实作品或合法试读后纳入样本；查不到则当天报告缺口，不能虚构榜单。继续抓投稿168公众号中的小程序、番茄短故事和编辑例文。

每天分析2篇以内可核验作品，注明原文实际已读范围，去私库 `fiction-livewater-vault/INDEX/CREATIVE_QUERY_ENTRY.md` 找能碰撞的真实文本与精矿机制，输出1个原创商业短篇首选题。用户确认后才做粗纲、逐节精纲、3—4场关键对白并交Gemini扩写，作者最终审改投稿。11月商业目标1篇真正过稿；知乎短篇/长篇独立精品创作。无全文访问权不称全文已读，不在公开仓库保存他人收费正文。


读取：
- https://raw.githubusercontent.com/daisytsai315-stack/huzirebang/main/data/latest.md
- https://raw.githubusercontent.com/daisytsai315-stack/huzirebang/main/data/latest.json

先核验 `snapshot_date`、每篇 `published_at`、`parse_status` 和 `errors`，不把旧快照当新样本，不把「没抓到」说成「当天没更新」。

分流：`miniprogram_hot`、`fanqie_short_hot` 以及与之有关的编辑例文，进入**商业短篇实验素材库**。用真实来源日期、作品标题/导语、成熟母题、期待点、主要冲突设计和可变异点形成例文卡；必须进一步阅读原作合法公开正文才可以声称读过前几章或全文。不得将番茄长篇错当番茄短故事。每日最多给1个适合两天完成万字短篇的候选方向，关注可过稿性与复用效率，但不得承诺收入。

`zhihu_hot` 历史榜只作为参考：用户的**知乎短篇及长篇继续走精品路线**，不受两天一篇工作节奏影响，不再机械要求知乎公众号栏目天天更新。

`example_text` 是参考例文，不等于 `submission_call` 编辑真的在收；没有定制编辑，不应把提前找编辑看导语或改稿当启动前提。商业线默认完成稿审校后投稿。

`work_url` 只有经核实才可当作品原文；`work_search_url` 是检索提示，不是已阅读证据。单一公众号榜单只是该公众号的市场采样，不代表官方全平台榜位。没有新增可核验内容，应直说「本期无可用商业例文」并显示最近有效来源日期。
