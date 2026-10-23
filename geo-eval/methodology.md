# GEO 检测指南：检测项、流程、检测与校验规则、打分规则、输出规范（v2026.10）

> 本文是 GEO 检测的技术指南：检测什么、按什么流程检测、每项的检测与校验规则、如何打分、如何输出报告。
> 编制依据：`docs/GEO评测权威资料汇编.md`（权威来源汇编）、`geo_ready/GEO_SCORING_RULES_COMPLETE.md`（v5.0）与 `GEO_SCORING_RULES_v4.md`（旧版）、`geo_ready/GEO 论文学习材料：从 Citation Selection 到 Citation Absorption.md`、索菲亚报告复盘（`docs/sofeyia_case_review.md`、`docs/geo_report_problems_and_upgrade.md`），以及 Google / Bing / OpenAI 官方文档与 GEO 学术研究。
> 本文是**检测方法论与规则草案**，不是当前代码复述；落地时逐条转成检测器并用基准站点集校准。
>
> **阈值定位声明（重要）**：本文出现的具体数值阈值（Title 10–60 字符、Meta Description 50–155 字符、自包含答案块长度（仅作参考，不以长度为准）、每页一个 H1、文章数量下限等）均为**本模型内部推荐阈值**，用于统一打分口径，**不是 Google / Bing / OpenAI 公布的硬性标准**。对外报告必须写明“本模型推荐”，不得表述为搜索引擎要求。官方口径依据见 §6。

---

## 0. 检测原则

1. **目标：从“标记在不在”升级为“内容是否正确、建议是否可用”。** 检测存在（presence）是必要不充分条件：页面“有 Schema/有作者/有 Contact”不能证明“可信”。检测回答三件事：**内容是否存在（existence）→ 内容是否正确（correctness）→ 修改建议是否合理（actionable）**。
2. **三层检测 + 语义复核**：L0 可访问与发现（规则）→ L1 结构存在性（规则）→ L2 质量与正确性（规则为主，LLM 做语义复核）；内容质量与吸收潜质属于 L2 的内容侧检测。
3. **“信任上限（Trust Ceiling）”原则**：当站点**未声明实体映射**（品牌写法/邮箱域名冲突，且 Organization 缺少 sameAs / alternateName / parentOrganization 等关联声明）或存在 lorem 占位、伪造经验、复制站等严重问题时，相关维度与总分不得超过上限——索菲亚 E-E-A-T 10/10 就是缺这条规则造成的。**注意**：判定对象是“是否声明了实体关系”，而不是“是否存在多种写法”；集团/上市主体/海外品牌/英文转写可以并存，只要关系被明确声明。
4. **内容统计必须基于“干净正文页口径”**：剔除系统页/演示页/占位页后再算密度、新鲜度、可引用率、对题率；比率类指标一律按唯一页面分母并封顶 100%。
5. **任何结论要带证据与置信度**，修复建议禁止搬运占位/伪造内容（索菲亚 lorem 被写进 Organization 建议即反面教材）。
6. **方法可版本化、可复现**：检测规则、口径、评分权重与 prompt 版本随报告输出；基准站点集用于回归。

---

## 1. 检测对象与总体流程

### 1.1 检测管线

```
可发现性（robots/sitemap/索引资格/权威外链）
  → 访问与理解（可抓取 HTML、结构化数据、清晰语义、无占位/软404）
  → 结构与实体正确性（schema 正确、实体一致、声明可验证、E-E-A-T 真实）
  → 内容质量与吸收潜质（证据块质量、对题、自包含、结构可抽取）
```

| 检测阶段 | 检测内容 | 方法 | 成本/时延 |
|---|---|---|---|
| 可发现性 | robots/sitemap、AI 爬虫可达性、索引资格、权威外链 | HTTP 探测 + 链接分析 | 低 |
| 访问与理解 | 可抓取 HTML、无 JS 内容可读性、结构化数据、语义结构、非正文页识别 | 规则 | 低 |
| 结构与实体正确性 | schema 正确性、品牌/实体一致性、声明可验证、E-E-A-T 真实信号、内容真实 | 规则 + LLM 复核 | 中 |
| 内容质量与吸收潜质 | 证据块质量、对题、自包含、结构可抽取、内容丰富度与新鲜度 | 规则 + LLM | 中 |

### 1.2 检测分层

| 层 | 名称 | 检测什么 | 是否进总分 | 方法 |
|---|---|---|---|---|
| L0 | 可访问与发现 | robots 放行 AI 爬虫、sitemap、HTTPS、重定向、AI UA 可达、无 JS 可读 | 否（作门槛/惩罚与 issue） | 规则 |
| L1 | 结构存在性 | schema/ogp/on-page/内容丰富度/llms.txt 等“有/无” | 是（九维主体） | 规则 |
| L2 | 质量与正确性 | 内容是否可信、自洽、无占位/虚假/矛盾；schema 是否正确且与实体一致；证据块质量与对题 | 是（新增并占相当权重） | 规则为主，LLM 语义复核 |

### 1.3 检测结果形态

| 输出 | 内容 |
|---|---|
| 总分与等级 | `overall_score`（0–100）、`grade`（A+~D）、`score_adjustments`（base/penalty/bonus） |
| 分维分数 | `category_scores`：每维 `score/max/percentage/grade/双语名` |
| 问题清单 | `issues[]`：双语 title/description/recommendation、`priority`、`impact`、`category`、`evidence`（URL+引文/字段）、`confidence` |
| 修复建议 | `improvement_suggestions` 与代码/文案建议（evidence 驱动、经内容清洗与真实性自检） |
| 方法与口径 | `methodology_version`、检测时间、页数、正文页/系统页口径、`scoring_version` |

### 1.4 权威依据清单（从依据到检测方向的推导）

| # | 来源 | 关键主张（对评测的意义） | 推导出的检测方向/规则 |
|---|---|---|---|
| A1 | Google Search Central《AI features and your website》+《Optimizing your website for generative AI features on Google Search》（developers.google.com/search/docs/appearance/ai-features，2026-05 新增） | AI Overviews/AI Mode 基于核心排名+RAG+query fan-out；**不需要 llms.txt、不需要专门 schema、不需要把内容切块**；要做的是“非商品化内容/一手经验、可抓取语义化 HTML、页面体验、权威与 E-E-A-T 基础”；Search Console 可管理与衡量 generative AI 曝光（含 search generative AI 设置与 Generative AI performance report） | 评测不应把 llms.txt/“AI 专用文件”当必须项（最多做加分/可选项）；应测：可抓取 HTML、语义化结构、内容独特性与一手经验、页面体验、索引/曝光控制 |
| A2 | Microsoft Bing Webmaster Guidelines（2026-02 改写） | 把 GEO（内容被 grounding/引用的资格）写入官方指南；grounding 优化规则=**事实直接陈述、实体名称一致清晰、一个 URL 一个主题、关键信息置于页面顶部**；Schema（Article/FAQPage/HowTo/Product）是重要输入；NOARCHIVE/NOCACHE/data-nosnippet/data-snippet 控制 | 直接产出可检测规则：实体/名称一致性、单 URL 单主题、顶部关键信息、可验证直接陈述、结构化数据正确性、引用资格规则 |
| A3 | OpenAI Crawler 官方文档（openai.com/searchbot、developers.openai.com/api/docs/bots） | OAI-SearchBot（搜索索引）与 GPTBot（训练）独立配置；屏蔽 OAI-SearchBot=不出现在 ChatGPT 搜索；常见被挡四层：robots/WAF/人机验证/限流 | robots 分段检查需区分“检索爬虫 vs 训练爬虫”；增加对 WAF/CAPTCHA/429 的间接探测（非 HTML 或 challenge 页面） |
| A4 | 中国信通院 AIIA/T 0277-2026《生成式引擎优化（GEO）服务可信基本要求》+《GEO 行业自律公约》 | 三条底线：**事实准确（多源交叉验证、不虚构数据）、来源可溯（关键数据标注来源机构/报告/时间）、结构合规（Schema 合规）**；禁绝对化承诺与黑帽 | 评测维度应含“声明与数据是否可溯源/可交叉验证”；对客户输出避免绝对化效果承诺，增加来源标注 |
| A5 | Princeton GEO-bench（KDD 2024，arXiv:2311.09735） | 位置调整词数/主观印象两类指标；加引文/数据/来源引用是最有效策略；关键词堆砌无效甚至有害；不同领域无万能策略 | 内容侧给“引文/来源/数据”权重；检测时给出“领域差异化提示”而非万能清单 |
| A6 | Stanford《Evaluating Verifiability in Generative Search Engines》（EMNLP 2023 Findings） | **被引用 ≠ 被正确使用**：引用召回与精确率分离；回答“看起来有用”与“引用准”负相关 | 作为“必须测正确性/多源核验”的依据 |
| A7 | 《From Citation Selection to Citation Absorption》（arXiv:2604.25707 + geo-citation-lab） | Selection 与 Absorption 两阶段；高影响力页≈1943 词、结构清晰；定义/数据/对比/步骤是吸收关键（+41%~+62%）；Q&A 无天然加成；**对题 > 泛权威** | 新增“吸收潜质”评分（证据块质量、对题度、结构可抽取）；FAQ 不当万能；页面长度/结构作为上下文而非硬阈值 |
| A8 | Ahrefs AI Overviews 系列研究 | AIO 触发率 20.5%（信息型 21.4%、YMYL 更高、7+ 词 46.4%）；query fan-out 使“被引用来源”与传统 Top10 逐步脱钩 | 内容检测不能只用“传统排名代理”，应覆盖被 AI 理解与抽取所需的正确性/可抽取性 |
| A9 | Google 质量评估指南/helpful content（官方）+ 行业最佳实践 | E-E-A-T/Experience、YMYL、作者与来源真实性、“为什么该信你” | L2 信任维度按“信号-可验证性”给分：作者真实、声明可核、联系真实、负面信息处理 |

> **官方口径核对（2026-09）**：① Google 生成式 AI 官方指南（2026-05-15 发布、2026-07-10 更新）明确“为 AI 优化=为搜索优化”：无独立 AI 索引、**无需添加特殊 schema、不读取 llms.txt**；要做的是独特/一手经验内容、可抓取语义化 HTML、写给读者的结构。② Bing 2026-02 改写 Webmaster Guidelines 并把 GEO（被 grounding/引用的资格）写入官方指南，给出 grounding 规则：**事实直接陈述（可独立验证）、实体名称清晰一致、一个 URL 一个主题、关键信息置于页面顶部**；Schema（Article/FAQPage/HowTo/Product）是重要输入；`data-snippet` 可指定可引用文本。③ Google QRG 最新为 **2025-09-11** 版：YMYL 扩至选举/政府/公民议题、把 AI Overviews 纳入评估；helpful content 官方原句 “Of these aspects, trust is most important”（Who/How/Why：署名、AI 披露、以助人而非流量为目的）；scaled content abuse（占位/批量无价值）与“操纵生成式 AI 回答”属垃圾政策打击对象，检测中应对“AI 生成占位/批量内容”直接降权。本表 A1/A2/A9 已据此交叉核对。

---

## 2. 检测方向总览

| 方向 key | 名称 | 主层 | 检测方法 | 主要依据 |
|---|---|---|---|---|
| `access` | 可访问与爬取（robots 语义、AI UA 可达、HTTPS/重定向、sitemap） | L0 | 规则 | A2/A3 |
| `cleanliness` | 页面清洁度（系统/演示页、占位/模板残留、软404、复制页、索引膨胀） | L1/L2 | 规则 + LLM 复核 | 索菲亚复盘 |
| `schema` | 结构化数据正确性（类型/属性/嵌套/实体一致/可解析） | L1/L2 | 规则 + LLM 复核 | A1/A2/A4 |
| `entity` | 品牌与实体一致性（站名/公司名/邮箱/电话/地址/子品牌关系） | L2 | 规则 + LLM 复核 | A2/A4/A9 |
| `onpage` | 页面主题呈现（title/meta/H1/层级/顶部关键信息/单主题） | L1 | 规则（+LLM 语义） | A2 |
| `ogp` | 开放图谱与社交呈现（og:title/description/image/url + Twitter Card） | L1 | 规则 | A2 |
| `kg` | 知识图谱/实体权威（sameAs、knowsAbout、foundingDate、位置/服务区域、正文权威外链、内链） | L1/L2 | 规则 | A4/A9 |
| `richness` | 内容丰富度与真实新鲜度 | L1 | 规则 | 索菲亚复盘 |
| `absorption` | 证据可吸收性（定义/数据/对比/步骤/对题/自包含） | L1+L2 | 规则 + LLM | A5/A6/A7 |
| `trust` | E-E-A-T 与信任（作者/信任页/资质/经验 + 一致性真实性） | L2 | 规则 + LLM 复核 | A4/A9 |
| `citations` | 引用与来源（外链权威、声明出处、可交叉验证） | L2 | 规则 + LLM | A4/A6 |
| `quality` | 内容质量与 helpfulness（一手经验、独特性、可信声明） | L2 | LLM 复核 | A1/A9 |
| `tech` | 技术/性能/安全代理（HTTPS/体积/CSR/规范） | L1 | 规则 | 现 SEO/UX |

---

## 3. 检测规则明细

> 通用定义：**正文页**=内容承载页（home/about/article/product/service/faq/listing 等）；**系统页**（login/cart/checkout/account/search/archive/tag/404/thanks/legal）；**演示页**（主题/建站残留，如 `pabriz-*`、`elementor-*`、`/page/`）；**占位内容**=lorem/示例文本/`under construction`/重复填充。
> 每条规则给：输入、判定、阈值草案、输出/证据、实现层、是否 LLM。

### 3.1 `access` 可访问与爬取（L0/L1）

| 检测项 | 输入 | 判定与阈值草案 | 输出 | LLM |
|---|---|---|---|---|
| AI 检索爬虫放行 | robots.txt（解析 UA 段与 allow/disallow，区分检索/训练，参考 OpenAI A3 语义） | 任一流检索爬虫（OAI-SearchBot、GPTBot、ChatGPT-User、ClaudeBot、anthropic-ai、PerplexityBot、Google-Extended/GoogleExtendedCrawler、Bingbot 等）被 `Disallow:/` 或专属段限制 → critical；仅训练爬虫（CCBot/Bytespider…）被挡不 critical | issue+惩罚/提示；区分“搜索可见性”与“训练”两类说明 | 否 |
| 可访问性探测 | 首页与关键页 GET | WAF/CAPTCHA/challenge 页（HTML 里含 cloudflare/captcha/challenge/verify）→ 提示“真实爬虫可能被挡”；429/403 记录 | 警告+URL | 否 |
| AI 爬虫 UA 可达性 | 用主流 AI 检索爬虫 UA 实抓关键页 | 以 OAI-SearchBot、GPTBot、ClaudeBot、PerplexityBot 等 UA 抓取首页/About/代表性内容页；被 WAF/挑战页/403/429 拦截 → 可达性问题（区别于 robots 文本放行） | 每 UA 的可达结果与证据 | 否 |
| 无 JS 内容可读性 | 禁用 JS 的 HTML | 关键内容（正文主体、可索引文本、结构化数据）是否存在于服务端 HTML；纯 CSR 空壳 → 可读性问题 | issue + 页面证据 | 否 |
| sitemap | /sitemap 族+robots 声明 | 存在且包含正文页；若 sitemap 只有系统/演示页则提示 | 覆盖统计 | 否 |
| HTTPS/重定向 | 技术探测 | 同现有 technical；重定向链、http→https | 惩罚项 | 否 |

### 3.2 `cleanliness` 页面清洁度（L1/L2）

| 检测项 | 输入 | 判定与阈值草案 | 输出 | LLM |
|---|---|---|---|---|
| 系统/演示页识别 | 路径+页面特征 | 命中系统页规则集（cart/checkout/account/search/404/thanks/cookie/privacy/terms/archive/tag/feed）+ 演示前缀（pabriz/elementor/page_id/wp 模板名）→ 标记 `role` | 页面角色清单；正文页/系统页计数 | 否 |
| 索引膨胀/垃圾页 | sitemap 与扫描页 | 系统页+演示页可索引占比 > X%（草案 20%）→ issue“索引垃圾稀释正文”，建议 noindex/移除 | issue | 否 |
| 占位/伪内容 | 正文文本 | lorem 匹配、示例占位词（`your-`、`example.com`、`xxx`、`under construction`、`Primis …` 模式）命中页/段落 → 计入“内容真实性问题” | 段落证据 | 否 |
| 软 404/空页 | 状态码+正文 | 200 但正文极短/含 404/not found 模板 → 软404 | 警告 | 否 |
| 重复/复制 | 段落 n-gram 或相似度 | 跨页高相似正文（草案 5-gram 重复率>0.5 且占比高）→ “复制/模板内容” | issue | 可选 |
| 模板残留文案（Elementor/Demo/Boilerplate） | 正文/字段文本 | 命中已知模板残留特征（`Lorem ipsum… Ut elit tellus…`、`Primis non dignissim…`、`0 Years Experience`、`0 Projects`、`Read more`、`Information`、`Dedicated for best quality innovations`、`under construction` 等）→ 计数并产出 **Template Residue Score** | issue + 段落证据 + Score | 否 |
| 模板源指纹 | 路径/资源/页面结构/meta | `pabriz-*`/`elementor-*`/模板残留页路径与资源名、主题作者 metadata（如 `moxcreative`）、结构化模板指纹与公开 Template Kit 特征比对 → 提示“疑似基于 XX 模板二开”（低置信标注） | LLM 复核提示 + 指纹证据 | 可选 |
| 默认合规/占位物 | 法律页/CTA/链接 | 默认 Privacy Policy 模板句式、Placeholder CTA（`Click here`/空锚文本）、空链接、0 值 JS 计数器 → 内容治理提示 | issue | 否 |

> 案例：索菲亚首页保留 `Create. Enhance. and Sustain.`/`Primis non dignissim…`（Pabriz Elementor Template Kit 的 Demo 文案）并残留模板演示页，属于典型“模板残留”发现；对客户话术应避免攻击技术栈，而指向内容治理/QA/AI 可读性（见 `geo_report_problems_and_upgrade.md` §2.3、§P2-5）。

### 3.3 `schema` 结构化数据正确性（L1+L2）

在现有“类型覆盖(14)/属性(6)/嵌套(5)”之上增加**正确性**检查（否则出现 Organization 缺 sameAs/description/contactPoint、name 与展示品牌不一致却满分的情况）：

| 检测项 | 判定（草案） | 输出 |
|---|---|---|
| name/url 与站点一致 | Organization/WebSite/Product 的 `name` 不得是占位/拼接（`homepage - x`、`site name`），`url` 应与页面同源 | 一致性 issue + 证据（schema 原文 vs 期望） |
| logo/image 可解析 | schema image/logo URL HTTP 200 且为图片 | 属性级 issue |
| sameAs 真实性 | 目标 URL 非站内拼造（`/facebook` 等）、域名与声明平台匹配、可解析（≥200 或知名平台主页） | 属性级 issue |
| contactPoint/telephone | 非占位（`+86-xxx`、`000`、`your-`）；邮箱域名与站点域名一致 | 属性级 issue |
| author/date 合理性 | datePublished ≤ dateModified ≤ now；author 实体存在且与页面 byline 一致；Article.publisher 与 Organization 一致 | 属性级 issue |
| @id/引用完整性 | 跨 script 的 `@id` 引用可解析；WebSite.publisher 指向的 Organization 存在于同页/站点 | 关系 issue |
| 覆盖与质量分层 | 保持“存在性给分+质量扣分”双轨：先按现有规则算存在分，再按上面正确性项扣“虚假/占位/不一致”分，扣完为维度实际分 | 分维分 |

### 3.4 `entity` 品牌与实体一致性（L2）

这是索菲亚案例的核心缺口（两个拼写品牌、两个邮箱、Sogal/源自法国混乱）。

| 检测项 | 输入 | 判定（草案） | 输出 | LLM |
|---|---|---|---|---|
| 品牌写法一致性 | 首页/全站的 Organization.name、og:site_name、`<title>`、footer/copyright、logo alt | 归一化（小写、去 legal 后缀、去空格/连字符/全半角）后存在 ≥2 个显著不同品牌写法且出现多次 → issue（列出写法与出现位置） | issue+证据 | 否 |
| 域名与邮箱一致性 | `mailto:`、页面公开邮箱、schema email | 邮箱域名 ≠ 站点主域名，或同一联系页出现多个不同邮箱域名 → issue；若明显子域/企业邮箱白名单则忽略 | issue+证据 | 否 |
| 联系方式真实性 | 电话/地址文本 | 占位模式（xxx/000/your-/123）或与地址不一致 → issue | issue+证据 | 否 |
| 子品牌/代理关系清晰 | 正文与 schema 中“品牌 X 与 Y 关系” | 出现代理/引入/合作/源自等关系动词而主体不明确（无法对应到已有 Organization/实体） → 提示“实体关系需澄清” | 语义复核 issue | 推荐 |
| 声明与历史一致性 | About/历史文本 | 同页或跨页自相矛盾（如不同成立年份、不同发源地、不同归属主体） → issue | issue+证据 | 可选 |
| 社交真实性 | sameAs 链接 | 目标 404/非平台/伪造 → issue | issue | 否 |

### 3.5 `onpage` 页面主题呈现（L1）

现有规则保留；按 Bing A2 增加“顶部关键信息/单 URL 单主题”启发式：首页与内容页首屏（HTML 前部与 H1 后段落）应包含对页面主题的直接陈述；title 与 H1 主体语义一致（规则：词重叠/相似度低于阈值 → medium issue，草案为可选语义检查）。演示页（如 `og:title=homepage`）应在占位清洗后判不合格。OGP/社交呈现另按规则手册 `OGP-01/02` 检测（og:title/description/image/url 各 0.75 + Twitter Card 2，占位内容另记质量提示）。

### 3.6 `richness` 内容丰富度与真实新鲜度（L1）

沿用 v5 权重框架（FAQ/blog/knowledge/freshness），但执行三条修复：
1. **口径**：所有统计基于正文页（剔除系统/演示/legal 页）。FAQ 仍以“1 个高质量 FAQ 页即可满分”为理念（答案资产+schema 覆盖），但 **FAQPage Schema 覆盖率必须真实**（索菲亚 FAQ 页 schema 覆盖 0% 却因 answer_asset 100% 拿 5/6 → 应补扣）。
2. **freshness 修复**：分母=含日期的唯一正文页数；rate=覆盖页数/正文页数，封顶 100%；日期字段仅统计一次/页；datePublished>dateModified 或未来日期 → 不计并提示。
3. **knowledge 收紧**：guide/tech 页必须有文档性证据（路径 `/docs|/guides|/help|/tutorial` 或结构化标题），排除演示/系统页（索菲亚 `tech_pages≈40` 为反面）。

### 3.7 `absorption` 证据可吸收性（L1+L2）

**现行口径（v1.1）**：沿用 citability 的 20 分制五子项，维度按 ×0.75 折算到 15 分；
与 `geo_ready` 的 `CitabilityAnalyzer` 是同一模型（skill 侧实现 `scripts/citability.py`）。

| 子项 | 原始分 | 现行实现 | 说明 |
|---|---|---|---|
| 可引用内容块率 | 7 | 块级抽块 + 词数窗口（段落英文 100–200 / 中文 60–220；结构化块 30–220）+ 自包含 + 非空泛（含数据可豁免）；锚点 10→3 / 25→5 / 40→7 | 块级抽取保证不被整页压成一块 |
| 证据块覆盖 | 7 | 定义 / 数据 / 对比 / 步骤四类，各需 ≥2 块且密度 ≥2%；4/3/2/1 类 → 7/5/3/1 | 数量与密度同时看，避免长文被单块带偏 |
| 直接回答 | 3 | 每页首个正文段 40–150 词且含数据或定义；覆盖率 ≥60 / ≥30 / >0 → 3/2/1 | BLUF 的启发式近似 |
| 结构化答案资产 | 2 | 摘要小标题 + 数据表格 + 答案列表 + FAQ 答案块；≥5 → 2、>0 → 1 | 可被直接切走的单元 |
| 对题度 | 1 | title/H1 与首段主题词重合，或存在提问式小标题；覆盖率 ≥50 计 1 | 修 query_alignment 误报 |

**未实现（设计项，不计分）**：数据可验证（ABS-03，W 警告项只报不评）、权威引用数、
「40–60 词 BLUF」这类未经验证的阈值。方法论文档与 rubric 只描述引擎实际执行的部分。

### 3.8 `trust` E-E-A-T 与信任（L1 presence + L2 truth）

分两层给分：
- **L1 presence（沿用并修正）**：作者 Schema/byline、About/团队/使命、隐私/联系/条款、资质/经验关键词。**修正**：作者名若是主题/建站商默认（`admin/theme/ehaitech`）或与站点主体无关，则不记“作者真实性”分；信任页内容必须匹配页名（否则软 404 处理）。
- **L2 truth（新）**：
  - 作者可验证性：作者是否在站内有个人页/简介/社交；同一作者名是否跨页一致；
  - 经验与一手证据（Experience）：站内是否有一手内容（案例/数据/真实项目/图片），而非纯模板（对应 Google Experience/helpful content）；
  - 联系与公司真实性：见 3.4；
  - 负面与一致性：联系方式/地址与商标注册信息、地图/商业平台一致性（人工核验，可选）；
  - **信任上限（v2026.10 实现口径）**：
    - 触发：**未声明实体映射** —— 品牌写法与邮箱域名不一致 **且** Organization 缺少 sameAs / alternateName 等声明（触发规则 `ENT-01`、`ENT-02`、`SCH-02`）；lorem 占位、伪造经验、复制站另行触发。
    - 约束（整数口径）：`trust` ≤ 7（满分的 50%）、`entity` ≤ 4（满分的 30%）、总分 ≤ 70。
    - 解除条件：在 About/Contact 与 Organization schema 中声明实体关系（name / legalName / alternateName / sameAs / parentOrganization）后，上限解除，两个维度按实际得分计分。
    - 实现（整数口径）：先按规则扣分，再施加上限，再套维度下限（`entity` ≥ 4、`quality` ≥ 1、`on_page` ≥ 2），最后扣内容治理处罚；所有扣分/上限/下限/惩罚均为整数。

### 3.9 `citations` 引用与来源（L2）

- 权威外链与出处：正文中的数字/声明带出处（站外可验证来源链接、机构名+时间）比例；
- 外部权威引用与背书：被 Wikipedia/.gov/.edu/行业目录/新闻引用（规则手册 `KG-04` 权威域白名单；**排除导航/页脚社交图标**，不按正文外链总数计）；
- 知识图谱实体信号：sameAs/knowsAbout/foundingDate/位置与服务区域（规则手册 `KG-01~06`）；
- 多源交叉验证（对应 A4 事实准确）：关键声明在站外出现且一致。

### 3.10 `quality` 内容质量与 helpfulness（L2，LLM）

用 LLM（或 LLM+规则）评估每类正文页：是否非商品化/有一手经验/有作者署名且真实/有“为什么该信你”/无空洞营销与堆砌/无抄袭痕迹/可读性。输出维度分+代表页证据+置信度。为控制成本只评估“代表页集”。

### 3.11 `tech` 技术/性能/安全代理（L1）

保持现有 SEO technical（HTTPS/canonical/跳转）与 UX performance_proxy（CSR/体积）规则；新增：“JS 渲染关键内容”探测结果提示（对 AI 爬虫与搜索引擎是风险点）。

---

## 4. 评分与奖惩模型（建议草案）

### 4.1 Base 100 分配（草案，需 A/B 校准）

| 维度 | v5 现权重 | v6 建议权重 | 变化与理由 |
|---|---|---|---|
| Schema 存在性（类型14/属性6/嵌套5→正确性内置） | 25 | **15**（v2026.10 由 20 下调） | 结构化数据不是通用排名因子；FAQPage 富媒体自 2023-08 起仅面向权威政府/医疗站点，故 FAQPage 降为辅助项不计分，正确性并入该维扣分 |
| 实体与品牌一致性（`entity`） | 0 | **15**（v2026.10 由 10 上调） | 新增（索菲亚教训）并上调：实体映射不清是本次最主要问题，权重应与其影响匹配 |
| OGP/社交 | 5 | 5 | 保留存在性 |
| 内容丰富度+真实新鲜度 | 20 | 15 | 收紧口径后权重略降 |
| 知识图谱/外部权威 | 15 | 10 | 由“链接数”转向“可验证权威/背书” |
| 证据可吸收性（`absorption`） | 20 | 15 | 保留但改质量口径 |
| 信任（presence+truth，含信任上限） | 10 | 15 | 加入 truth 后权重上调 |
| On-Page/主题呈现 | 5 | 5 | 保留 |
| 内容质量/helpfulness（`quality`，LLM 复核） | 0 | 5 | 新增 |
| **合计** | 100 | 100 | |

**v2026.10 权重（当前生效）**：schema 15 · entity 15 · ogp 5 · richness 15 · knowledge_graph 10 · absorption 15 · trust 15 · on_page 5 · quality 5 = 100。维度内扣分随权重同比例换算，以保持“单条问题在该维度内的严重度”不变。

（该表是**草案**：权重最终由基准站点集 + LLM 复核结果校准，而不是拍脑袋。）

### 4.2 惩罚与加分（草案）

| 项 | 调整 |
|---|---|
| AI 检索爬虫被挡 | 保持 -15（critical） |
| 非 HTTPS / 不跳转 / 重定向过长 | -10 / -3 / -3（与规则手册 ACC-05 一致） |
| **严重一致性/真实性问题** | 新增负向：品牌拼写冲突（critical→-8~-12）、邮箱域名冲突（critical→-5~-10）、lorem/占位正文占比高（按比例 -3~-10）、复制站/纯模板站（-10~-20，规则+LLM 判定） |
| 信任上限 | 触发“未声明实体映射”（见 §3.8）时，`trust` ≤ 7、`entity` ≤ 4、总分 ≤ 70（整数）；完成实体映射声明后解除 |
| llms.txt 等可选文件 | 保留可选项加分（llms.txt +3）；schema/OGP 加分规则沿用。**FAQPage 缺失自 v2026.10 起不再计分**，仅在报告“需确认或补充的信息”中列出 |
| 加分合计 | 维持 clamp（如 +10）并注明“加分不抵消真实性问题” |

### 4.3 打分原则

1. **存在性与质量分离**：存在分只证明“有”，满格存在分不代表满格质量分。
2. **证据驱动**：每条扣分/低分必须可追溯到页面/字段证据；无证据不下结论。
3. **置信度修正**：规则可证明的（拼写、邮箱、占位）给高置信；语义判断（helpfulness、声明可验证）标注中/低置信或“需人工复核”。
4. **比率封顶与分母可见**：所有比率 0–100%，报告标注分母口径（正文页 N）。
5. **版本与口径可见**：scoring_version、口径版本、扫描时间随报告输出。

---

## 5. 现有实现差异对照与落地清单

| 现有（源码） | 问题（对照复盘） | 新方法论落地 |
|---|---|---|
| `EeatAnalyzer`/`calculate_eeat_score` presence 加和 | 存在≠可信 | 新增 entity/truth 检测 + 信任上限（§3.8/§4.2） |
| `CitabilityAnalyzer` 词数/数字/标点启发式 | 不辨真伪；query_alignment=100% 误报 | 吸收潜质+正文页口径+占位过滤（§3.7） |
| `ContentRichnessAnalyzer` freshness/tech 判定 | 916.7% 比率；tech_pages≈40 演示页 | 分母修复+角色过滤（§3.6） |
| `SchemaCoverageAnalyzer` 存在/属性/嵌套 | Organization 缺 sameAs/description/contactPoint、name 与品牌不一致等正确性不查 | schema 正确性与实体一致（§3.3） |
| `CodeGenerator`（模板，AI 分支失效） | lorem 进建议、假 sameAs/电话 | 输出清洗+真实性门禁+LLM 建议（见 Agent 方案） |
| `PageScanner` URL 发现 | 扫描一半是演示/系统页 | 页面角色分类+正文页口径（§3.2） |
| 报告 issues/evidence | 证据错位、模板话术 | 证据引用规范+置信度（§6） |

落地顺序与工作量见 `docs/geo_report_problems_and_upgrade.md` Phase 0–3；实现方案见 `docs/geo_deep_detection_agent_plans.md`。

---

## 6. 报告输出规范

- **字段扩展**：`methodology_version`、`scoring_version`、`scope`（正文页 N/系统页 M/抽样代表页）、`confidence`（每 issue 级别：high/medium/low/review）、`trust_ceiling_applied`。
- **evidence 规范**：每条结论带 `{type: quote|field|url, url, quote/text, locator}`；affected_urls 只能是 URL 字符串（修数据错位）。
- **建议生成规范**：先证据后建议；代码片段禁用页面占位/伪造值；无法确定的值用中性占位并注明需人工确认；文案改写类建议给出“原文引用→改写后→为什么”。
- **多语言**：沿用双语对象；LLM 生成内容同样双语且标注“AI 生成，仅供参考”。

---

## 7. 验证、回归与持续校准

1. **基准站点集**：建立 ≥20 个手工标注站点（覆盖电商/SaaS/企业/个人/博客/中英；含索菲亚这类“存在但不可信”样本、复制站、纯模板站、健康站点），作为规则回归与权重校准金标准。
2. **人工抽检**：每周抽检 N 条 LLM 结论与建议（幻觉率、证据正确性），记录并回流 prompt/规则。
3. **人工抽检**：LLM 结论必须经人工抽检（幻觉率、证据正确性、建议可用性），并回流 prompt/规则。
4. **版本治理**：方法/规则版本化；历史对比时提示版本差异，避免误读趋势。

---

## 8. 相关文档

- 规则规格（Step 1，可直接实现）：`docs/geo_detection_rules.md`
- 评测数据结构（eval-1.0）：`docs/geo_evaluation_data_structure.md`
- 问题与优先级：`docs/geo_report_problems_and_upgrade.md`
- 实现方案：`docs/geo_deep_detection_agent_plans.md`
- 现状实现：`docs/geo_report_pipeline.md`、`docs/geo_detection.md`、`docs/seo_detection.md`、`docs/ux_detection.md`、`docs/competitor_detection.md`
- 权威汇编：`docs/GEO评测权威资料汇编.md`
- 旧规则（将被本方法论演进替代）：`geo_ready/GEO_SCORING_RULES_COMPLETE.md`、`GEO_SCORING_RULES_v4.md`
- 论文学习材料：`geo_ready/GEO 论文学习材料：从 Citation Selection 到 Citation Absorption.md`

---

## 6. 官方口径依据（用于约束表述与权重）

| 结论 | 依据 | 对本文的影响 |
|---|---|---|
| Meta Description 无固定长度限制，过长仅在展示时截断 | [Google: Control your snippets](https://developers.google.com/search/docs/appearance/snippet) | 50–155 字符只作为**本模型推荐区间**，报告中不得写成官方要求 |
| 结构化数据不是通用排名因子 | [Google Search Essentials / 官方表述](https://developers.google.com/search/docs/appearance/structured-data/search-gallery) | schema 权重由 20 下调至 15，并把措辞改为“有助于机器理解与实体消歧” |
| FAQ / HowTo 富媒体结果自 2023-08 起仅面向权威政府与医疗类站点 | [Google: Changes to HowTo and FAQ rich results](https://developers.google.com/search/blog/2023/08/howto-faq-changes) | FAQPage 降为辅助项（W 类，不计分） |
| Organization 的 sameAs / contactPoint 属“适用时推荐”，非必填 | [Google: Organization structured data](https://developers.google.com/search/docs/appearance/structured-data/organization) | 作为实体映射的声明手段使用，缺失触发信任上限；不再表述为“直接影响识别” |
| 支持 `alternateName` 声明别名 | schema.org / Google Organization 文档 | 多名称并存时用 `alternateName` 声明，而非强制统一拼写 |
| scaled content abuse 指“以操纵排名为主要目的的大规模造页” | [Google: Spam policies](https://developers.google.com/search/docs/essentials/spam-policies) | 模板残留/低价值索引页**不得**定性为 spam abuse，改述为“可能稀释站点质量信号，建议 noindex/删除” |

## 7. 口径变更记录

### v2026.09 → v2026.10（2026-09，依据第三方审阅反馈）

| # | 变更 | 理由 |
|---|---|---|
| 1 | Schema 权重 20 → 15，实体一致性 10 → 15；维度内扣分同比例换算 | 结构化数据不是通用排名因子；实体映射不清是本案例最主要问题 |
| 2 | FAQPage 降为辅助项（`SCH-01` 移入 W 类不计分） | Google 自 2023-08 起 FAQ 富媒体仅面向权威政府/医疗站点 |
| 3 | 信任上限触发条件由“存在多种品牌写法”改为“未声明实体映射” | 集团/上市主体/海外品牌/英文转写可以并存；关键是关系是否被声明 |
| 4 | 对外建议由“统一品牌拼写”改为“建立实体映射（Entity Map）” | 用 name / legalName / alternateName / sameAs / parentOrganization 声明关联，更贴合官方能力 |
| 5 | 报告新增“评分方法（可复现）”页：维度得分 → 上限约束 → 治理扣分 → 最终分 | 客户质疑“看起来量化但依据未站稳”；分数必须可逐项核对 |
| 6 | 逐条问题不再给“+N 分”，改为“影响权重”；行动表第三列改为“可恢复空间”（＝维度满分−当前得分，或已计入总分的扣分） | 原 +N 分不可叠加，会出现“单维度 +17 分 > 该维度上限 10 分”的矛盾 |
| 7 | 所有内部阈值加“本模型推荐”标注，并写入 §6 官方口径依据 | 避免把经验规则包装成搜索引擎事实 |
| 8 | 评分命名拆分为“**站内 GEO 准备度**（Technical & Content Readiness）”；实际 AI 引用测试不在本口径内 | 避免客户把准备度分数直接对标 ChatGPT 实际表现；AI 可见性测试作为线下深度服务单独交付 |

### v2026.10 → v2026.11（2026-09，整数化）

| # | 变更 | 理由 |
|---|---|---|
| 1 | 全部扣分、上限、下限、惩罚改为**整数**，取消比例换算（SCALE） | 客户要求评分规则不用小数，便于核对与沟通 |
| 2 | 维度内扣分取整并微调：SCH-04/SCH-07（与 ENT-01/02/SCH-02 重叠）2→1；RCH-01（FAQPage）2→1；KG-06 1.5→1；CLN-05 1.5→1；0.5 档（KG-03/ONP-05/ONP-06）→1 | 消除 0.5/1.5/0.75 档，就近取整并保持维度总分不变 |
| 3 | 上限改为绝对整数：trust ≤ 7、entity ≤ 4、总分 ≤ 70；下限 entity ≥ 4、quality ≥ 1、on_page ≥ 2 | 50%/30%/20%/30% 换算会产生小数，改为绝对整数 |
| 4 | CLN-02 惩罚 −1.5 → −1（从宽） | 整数化 |
| 5 | `category_scores[].score` 一律整数；`percentage` 取整 | 报告页面相加与模型计算严格一致（不再有 42 vs 41 类偏差） |

### v2026.11 → v3.1（2026-09，三份外部评审交叉验证后）

| # | 变更 | 依据 |
|---|---|---|
| 1 | 可引用性指标改向：由“英文 100–200 词段落”改为“**自包含答案块 + 事实/数据密度 + 权威引用数**” | Princeton GEO 研究（数据 +31%、引用 +28%、引语 +41%）；行业实践 40–60 词 BLUF |
| 2 | **重复计罚去重**：模板占位根因只计一次——CLN-03/CLN-10/CLN-02 合并为“模板占位与残留”−5，CLN-09 索引膨胀 −2；CLN-02 从 richness 维度扣分移除 | 同一根因重复扣分会系统性压低总分，失去解释力 |
| 3 | 新增 **JS 渲染检查**：AI 爬虫（GPTBot/ClaudeBot/PerplexityBot）不执行 JS，需验证初始 HTML 即含正文；本站为服务端渲染、通过 | AI 爬虫只读初始 HTML |
| 4 | 新增 **索引存在性检查**：ChatGPT Search 依赖 Bing 索引、AI Overviews 复用 Google 索引；`site:` 收录、Bing 收录列为待确认项 | 不进索引 = 其余维度再好也不会被引用 |
| 5 | “实体权威与知识图谱”维度改名 **“站内实体信号”**；站外实体证据（集团官网互链、交易所披露、行业名录、媒体提及）明确为范围外，列为后续动作 | 知识图谱核心在站外，站内检测不应以“知识图谱”为名 |
| 6 | FAQ 结构化数据确认不计分，RCH-01 改口径为“问答为占位内容” | Google 自 2023-08 起 FAQ 富媒体仅面向权威政府/医疗站点 |
| 7 | llms.txt 确认为“低成本、未证实”可选项，不作为 GEO 因子 | Ahrefs 2026 研究：13.7 万站中 97% 的 llms.txt 零 AI 请求 |
| 8 | 报告呈现：去内部技术细节（四舍五入/整数/规则码/权重换算），面向客户措辞；示例代码改为基于企业信息的**具体建议** | 客户报告应“面向客户”，内部口径只进方法论文档 |

*文档版本 v3.1；检测项、规则与评分权重为草案，最终以基准站点集校准与人工抽检结果为准。*
