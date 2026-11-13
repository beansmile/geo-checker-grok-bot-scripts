# 评分规则（scoring）

> 10 维 100 分制，口径 **v1.3**（2026-11）。规则来源见 `rules.md`；方法论依据见 `methodology.md`；
> SEO 维度细则见 `seo_scoring.md`。相对 v1.2：**维度权重不变**，加强可抽取性、URL 卫生、主张证据、实体可核验性等子启发式与 findings。

## 1. 维度权重

| 维度 | 规则域 | 满分 |
|---|---|---|
| 结构化数据 | SCH-00~10 | 12 |
| 品牌与实体一致性 | ENT-01~08 | 12 |
| 开放图谱与分享 | OGP-01/02 | 5 |
| 内容覆盖与新鲜度 | RCH-01~04 | 12 |
| 站内实体信号 | KG-01~06 | 10 |
| 答案可吸收性 | ABS-01~06 + ABS-IMG | 12 |
| 信任度 | TRU-01~07 | 12 |
| 页面主题与元数据 | ONP-01~06 | 5 |
| 内容质量 | QLT-01~03 | 5 |
| **SEO 内容可发现性** | SEO / `seo_scoring.md` | **15** |
| **基础合计** | | **100** |

加减分（搜索/按需抓取爬虫不可达 −15、ItemList +3 等）**不**并入上表，见第 3 节；报告先展示基础分 /100，再单独展示 `score_adjustments`。**llms.txt 已移出核心 100 分**，仅作实验/辅助展示。OG/Twitter 仍占 5 分槽位，但 Twitter 权重降低、文案按分享预览卫生处理。

**GEO 口径：** Generative Engine Optimization（AI 理解 / 信任 / 引用就绪）。**不是**地理、本地地图包、NAP-as-GEO 或 LocalBusiness 核心产品叙事。

## 2. 分维计分口径（v1.3）

相对 v1.1：原满分 15 的五维（schema / entity / richness / absorption / trust）按 **×12/15** 折算到满分 12；检查项与取样方式不变。SEO 为 v1.2 起纳入的维度。v1.3 在 ABS / SEO / ENT·KG·Trust findings 上加厚子启发式，**满分表不变**。

| 维度 | 计分方式 | 满分可达 |
|---|---|---|
| schema | 内部仍按 v1.1 满分 15 口径累计，再 ×12/15；**发布的维度分按 0 或 0.5 取整**。Organization 节点存在计 5（展示 4/12）；缺节点是计分项（SCH-ABSENT / SCH-ABSENT-BODY-CLEAR），不是建议项。正文已能识别主体时，不把实体/KG 维打成 0。 | 12 |
| entity | 内部 15 − 实体扣分，再 ×12/15；发布值按 0 或 0.5 取整 | 12 |
| ogp | 只评**首页分享预览卫生**：`og:title/description/image` 各 1.25 + `og:url` 0.75 + `twitter:card` 0.5。不是 AI 理解或信任门槛；内页缺标签只作建议项 | 5 |
| richness | FAQ / 文章 / 正文体量三项内部满分 15，再 ×12/15；发布值按 0 或 0.5 取整；`llms.txt` 不计入本维 | 12 |
| kg | 正文与 schema **去重后**计：社交/档案（含页脚与 sameAs 并集）上限 4；主题 3；成立信息 1；地址/联系 2。缺 schema 不把本维打成 0 | 10 |
| absorption | **Citability 五子项（20 分制，×0.6 折算）**：可引用块率 7 + 证据块覆盖 7 + 直接回答 3 + 结构化答案资产 2 + 对题度 1；v1.3 对图片化/不可抽取样本软降 raw（最多 −2/20）；发布值按 0 或 0.5 取整 | 12 |
| trust | About / Contact / 合规 / 作者 / 正文体量内部满分 15，再 ×12/15；发布值按 0 或 0.5 取整 | 12 |
| on_page | 以是否有 title / meta / H1 为主。title 略长于 60 字、并非恰好一个 H1，只作提示，不等于缺标题或缺正文 | 5 |
| quality | 5 − 清洁度扣分（不变） | 5 |
| **seo** | 启发式先打 `/25`（`seo_analyze.py`），再 `dim = snap_half(raw×15/25)` 封顶 15；子信号见 `seo_scoring.md`（含 URL 卫生、图片化薄页） | 15 |

**分数粒度：** 十维**发布的维度分**只使用 0 或 0.5 步进（0、0.5、1、…）。内部启发式与折算可保留更细精度，但写入 `dimensions` / `category_scores` 以及用于相加的值，按最接近的 0 或 0.5 取整（恰好在两档中间时远离 0，例如 5.4→5.5、8.1→8.0、1.25→1.5）。**总分 `overall_score` 取整数**，不再按 0.5 取整。

### v1.3 新增 / 加厚（不改权重表）

1. **主内容图片化 / 不可抽取** → ABS findings + absorption 软降；SEO 薄内容信号；Content C-WRITE。附通用产品 / 案例 / 文章字段清单。
2. **入口与 URL 卫生**（SEO 维 + Access 说明；**不**把 ACC HTTPS 罚分再计入 SEO 数字）：软跳转 splash、canonical 缺失/不一致、多首页主机路径变体未见 301。
3. **无证据营销主张** → Content C-AUTH（大额整数 / 最高级且附近无证据链）。
4. **组织地址/联系完整度** → 实体 / 信任 / KG 可核验信号（正文或 schema address），**不是**本地地图包。
5. **意图页类型覆盖** → Content C-IA / C-TAX；多市场表述时可建议独立 market/region/project URL（可答性，不是城市词 SEO）。
6. **可选多 UA 冒烟**（浏览器 + 搜索爬虫 + AI 搜索爬虫）→ 仅 Access 证据（状态/时延），不编造差异分。
7. **CWV / 大资源 / 老旧栈** → 仅建议项（`scored=false`）。
8. **llms.txt** → 移出核心 100 分，仅检测与实验/辅助展示（含伪装 404 / MIME / 二进制误判修复）。

> `llms.txt` 不在 richness / seo / 加减分中计分。Google Search 不使用 llms.txt（该陈述只适用于 Google）。

## 3. 惩罚与加分

| 项 | 规则 | 调整 |
|---|---|---|
| 搜索索引或按需抓取爬虫被屏蔽/实测不可达 | ACC-01/02/03 | -15（只计一次）。要对 AI 友好，访问爬虫与训练爬虫都建议开放：前者是出现在 AI 搜索中的前提，后者用于模型训练语料。训练爬虫（GPTBot、ClaudeBot、Google-Extended）被拦截作为改进建议写出，不扣核心访问分，也不触发综合访问门槛。不得由 GPTBot 推断 ChatGPT 搜索被屏蔽；挡住 Google-Extended 不影响 Google 搜索或 AI Overviews；Claude-SearchBot 未测时 Claude 搜索为未核实。 |
| 严重实体不一致（品牌冲突 / ≥2 个邮箱域） | ENT-01 / ENT-02 | 不走加减分，走 Trust Ceiling 与实体维扣分 |
| 单一邮箱域 ≠ 站点域（含免费邮箱） | ENT-02（W 警告项） | 0（列出不计分） |
| lorem/占位主体内容 | CLN-03 | 不走加减分，走质量维 + 总分上限 ≤75 |
| 复制站/纯模板站 | CLN-08 | 仅相似度 ≥ 0.9 计分（质量维扣分）；0.75–0.9 建议项；0.5–0.75 不计分。不再使用 −10~−20 加减分 |
| llms.txt | ACC-07 | **不计核心分**（检测保留，实验/辅助展示） |
| ItemList Schema | SCH-01 | +3 |
| 加分上限 | — | bonus ≤ +10，不抵消真实性问题 |

引擎**当前未把 ACC-05 HTTPS 罚分写入 `score_adjustments`**（文档曾列 −10/−3/−3）。Checker 不以该项作为本轮新的核心罚分；如需复测 HTTPS，见 Access 观察/建议项。`lastmod` 目前不单独计分，本轮不新增政策。

> CSR/纯前端渲染不设固定罚分：由 ACC-06/TEC-02 以高优先级 issue + 架构警告呈现，避免重复扣分。
>
> 报告展示顺序：**基础分（十维合计，≤100）** → **加减分（`score_adjustments`）** → **最终 `overall_score`**。加减分永不并入维度权重表。

## 4. Trust Ceiling（信任上限，TRU-07）

命中任一 S1 一致性问题（ENT-01 品牌写法不一致 / ENT-02 邮箱域名不一致）时：

| 约束 | 值 |
|---|---|
| trust 维度 | ≤ 50%（=6/12） |
| entity 维度 | ≤ 30%（内部 3.6/12；发布值按 0/0.5 取整后为 3.5） |
| 总分 | ≤ 70 |

命中 S1 占位/模板问题（CLN-03 lorem 主体内容）时：总分 ≤ 75。

## 5. 等级映射

| 总分 | 等级 |
|---|---|
| 90–100 | A+ |
| 80–89 | A |
| 70–79 | B |
| 60–69 | C |
| 0–59 | D |
| 扫描失败（一页未取到） | F |

分维等级按该维 percentage（得分/满分）套用同一等级表。

## 6. 抽样与必检页

1. 角色配额抽样（home 1 / trust 6 / content 12 / legal 3 / system 4 / demo 4，默认 16 页）。
2. 抽样后**强制补入** FAQ / About / Contact / Privacy 各至少一页；超额补入，不挤掉已抽样页。
3. 站点确实没有对应页面时写入 `scope.scope_warnings`，报告「检测范围」页提示相关维度可能被低估。
4. 比率类指标分母仍只用 content 页（含首页）。

## 7. 建议项（scored=false）

只报不评的观察项不进入严重度色带、不扣分：

- 正文缺少权威外部引用（KG-04 / CIT-01）
- 内页 Open Graph 标签不完整
- 单一邮箱域 ≠ 站点域（ENT-02 W 警告项）
- CWV / 大资源 / 老旧栈指纹（v1.3 advisory）
- Multi-UA 冒烟记录（Access 证据）

报告 HTML 显示 `Advisory` / `建议项` 徽标；`scope_warnings` 同样在「检测范围」页展示。

## 8. 打分原则

1. **存在分与质量分分离**：存在通过 ≠ 质量满分（如 FAQ 无 schema 但答案资产满分，不得因答案满分给 schema 分）。
2. **每条扣分可追溯**：规则 ID + 证据；无证据不扣分。
3. **比率封顶 100%**，分母 = content 页（见 `rules.md` §0.3）。
4. **置信度**：R 规则 = high；R+LLM = medium；LLM = medium/low（标 `review` 需人工确认）。
5. **不编造**：抓取失败或 AI 检查未做时披露；需要时标 provisional。

## 9. 输出评分结构

报告 JSON 中的 `dimensions` / `category_scores`（10 维，含 `seo`）+ `overall_score` + `grade`，以及 `score_adjustments` / `adjustments`（base_score / penalty / bonus）。SEO 详情另附 `seo_discoverability`（含 `score_raw_25` 与维度分 /15）。每条 finding 带 `scored`（`false` = 建议项）。完整数据结构见 `output_schema.md`。

### 总分计算

```
published_dim = snap_half(scaled_dim)                 # 仅 0 / 0.5
base_score = sum(published_dim scores)                # 十维；Trust Ceiling 可再封顶
overall_score = clamp(0, 100, int(base_score - penalty + bonus))  # 整数
```

`bonus` 合计 ≤ +10。加减分条目列出在 `adjustments`，不改变维度满分表。
