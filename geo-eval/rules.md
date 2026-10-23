# GEO 检测规则手册（Step 1：规则规格 v1.0）

> 用途：把 `docs/geo_evaluation_methodology_latest.md`（GEO 检测指南）转成**可直接实现、可逐条执行的检测规则**。开发按本手册实现检测器；专家按本手册逐条核验与出结论；索菲亚案例作为首个 golden case 验收。
> 规则字段：`ID / 规则名 / 目标 / 输入 / 判定与阈值 / 输出与证据 / 严重度 / 分值影响 / 方法 / 页面范围`。
> 本手册只覆盖面向**企业官网 GEO** 的检测；agent 可用性/协议类检测（MCP、OAuth、API、Web Bot Auth 等）不在本手册，归第三方报告解读（`third_party_report`）。
> 配套：方法论文档（检测方向与打分模型）、`docs/sofeyia_case_review.md`（案例证据）、`docs/geo_deep_detection_agent_plans.md`（实现方案与流程）。
>
> **阈值定位（v2026.10）**：本手册中的长度/数量类阈值（Title 10–60 字符、Meta 50–155 字符、段落 100–200 词等）均为**本模型内部推荐阈值**，不是搜索引擎官方硬性要求；官方口径依据见方法论 §6。对外报告中一律标注“本模型推荐”。

---

## 0. 通用约定

### 0.1 规则编号

| 域 | 前缀 | 对应方法论方向 |
|---|---|---|
| 访问与爬取 | `ACC` | access |
| 页面清洁度 | `CLN` | cleanliness |
| 结构化数据 | `SCH` | schema |
| 实体一致性 | `ENT` | entity |
| On-Page/主题 | `ONP` | onpage |
| 开放图谱 | `OGP` | onpage（社交呈现） |
| 知识图谱/实体权威 | `KG` | citations / 知识图谱 |
| 内容丰富度 | `RCH` | richness |
| 吸收潜质 | `ABS` | absorption |
| 信任/E-E-A-T | `TRU` | trust |
| 引用与来源 | `CIT` | citations |
| 内容质量 | `QLT` | quality |
| 技术/性能 | `TEC` | tech |

### 0.2 严重度与分值

| 严重度 | 含义 | issue priority | priority_weight | impact 建议 |
|---|---|---|---|---|
| **S1** | 阻断性/强信任问题（品牌冲突、AI 爬虫被挡、lorem 主体内容） | critical | 9–10 | 30–50 |
| **S2** | 显著影响理解/信任（schema 不一致、缺信任页、吸收率极低） | high | 3–4 | 6–12 |
| **S3** | 一般优化项（title/meta/H1、新鲜度、内链） | medium | 2 | 3–6 |
| **S4** | 锦上添花（轻微缺失、可选项） | low | 1 | 1–3 |
| **W** | 警告/建议项：真实性无法当场考证（外部数据、历史声明、资质、外部实体映射）或品牌策略差异（如社交账号）；**列出但不计分**，供客户确认 | 展示为“建议/警告” | 0 | 0 |

> 警告项（W）示例：`ABS-03`、`CIT-02`、`CIT-03`、`TRU-04`、`ENT-05`（社交账号策略差异）、`ENT-02`（单一邮箱域 ≠ 站点域，如官网挂 126.com 免费邮箱）、`QLT-03`（营销表述）。报告中单独成节，不参与维度扣分与总分。

### 0.3 页面范围标记

| 标记 | 含义 |
|---|---|
| `site` | 站点级（首页/全站聚合） |
| `home` | 首页 |
| `content` | 正文页（home/about/article/product/service/faq/listing） |
| `trust` | 信任页（about/contact/privacy/terms） |
| `system` | 系统页（login/cart/checkout/account/search/archive/tag/404/thanks） |
| `demo` | 模板/演示页（`pabriz-*`、`elementor-*`、`/page/`、`?page_id=` 等） |
| `legal` | cookie/privacy/terms 等合规页 |

> 判定「正文页/系统页/演示页」的优先级：demo > system > legal > trust > content。

### 0.4 方法标记

`R`=确定性规则；`R+LLM`=规则预筛 + LLM 语义判定；`LLM`=LLM 判定（需证据包与结构化输出）。

---

## 1. 前置规则（所有检测共用）

| ID | 规则 | 判定与阈值 | 输出 |
|---|---|---|---|
| PRE-01 | 抓取与页面角色分类 | 抓取可达页面；按 §0.3 标记 role；记录 HTTP 状态/内容类型/渲染模式 | `pages[]`（url/role/status/render） |
| PRE-02 | 正文页口径 | 比率、密度、覆盖率类指标的**分母只用 content 页**；system/demo/legal 页单独计数展示 | `scope{content,system,demo,legal}` |
| PRE-02b | 必检页后置补入 | 角色配额抽样后，强制补入 FAQ/About/Contact/Privacy 各至少一页（超额补入，不挤掉已抽样页）；站点没有对应页时写入 `scope.scope_warnings` | `scope.scope_warnings[]` |
| PRE-03 | 证据包生成 | 每条规则只携带所需页面片段（文本/schema 字段/meta），单包体积上限（如 ≤8KB 文本或 ≤10 页） | `evidence_pack[]` |
| PRE-04 | 比率封顶 | 所有百分比 0–100%，分母为唯一页面数；分子去重 | — |
| PRE-05 | 结论自检 | 输出前校验：证据存在、无可搬运占位串、affected_urls 仅 URL、字段完整 | 违规结论丢弃或降级标 `review` |

---

## 2. 规则明细

### 2.1 ACC 访问与爬取

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| ACC-01 | AI 检索爬虫放行 | 内置 14 UA。**critical 检索类**：OAI-SearchBot、GPTBot、ChatGPT-User、ClaudeBot、anthropic-ai、PerplexityBot、Google-Extended/GoogleExtendedCrawler、Bingbot；**非 critical**：YouBot、Diffbot；**训练类**：CCBot、Bytespider、FacebookBot、cohere-ai、ImagesiftBot。屏蔽判定：① 专属段 `Allow: /` → 放行；② 专属段 `Disallow: /` → 屏蔽；③ 专属段有任意 Disallow 且无 `Allow: /` → 视为屏蔽；④ 无专属段且通配 `*` 有 `Disallow: /` → 屏蔽；⑤ 有专属段时不继承通配屏蔽。任一 critical 命中 → S1；仅非 critical/训练类命中 → S4 提示 | S1/S4 | 总分 -15；issue impact 40 | R | site |
| ACC-02 | AI UA 可达性 | 用 OAI-SearchBot/GPTBot/ClaudeBot/PerplexityBot 四个 UA 实抓首页 + 2 个正文页；命中挑战页（cloudflare/captcha/challenge/verify）、403/429、超时 → 每个 UA 记一条 | S2 | 4/UA 起，累计 ≤12 | R | home+content |
| ACC-03 | WAF/挑战拦截迹象 | 普通 UA 抓取返回挑战页/429/403 或 HTML 含验证脚本 → S2 提示 | S2 | 5 | R | site |
| ACC-04 | sitemap 有效性 | 存在 `sitemap(.xml|_index.xml)` 且可解析；robots 声明一致；content 页占比 <50% → S3 | S3 | 3 | R | site |
| ACC-05 | HTTPS 与重定向 | 非 HTTPS → S1（-10）；HTTPS 但 http 不跳转 → S2（-3）；主 URL 跳数 >2 → S3（-3） | S1/S2/S3 | -10/-3/-3 | R | site |
| ACC-06 | 无 JS 内容可读性 | 服务端 HTML 的 body 文本 <300 字符或关键内容缺失（H1/正文/schema 均在 JS 注入）→ S1；CSR 启发式命中 → issue + 架构警告 | S1 | 6 | R | home+content |
| ACC-07 | llms.txt（可选） | `/llms.txt`、`/llms-full.txt`：200 且 body >10 字符、非 HTML、非软 404（不含 `404`/`not found`/`页面不存在`）→ 存在给可选加分；缺失不扣分（Google 官方不读取该文件） | S4（可选） | +3（bonus） | R | site |

### 2.2 CLN 页面清洁度

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| CLN-01 | 系统页识别 | 路径/页面特征命中 system 规则集（cart/checkout/my-account/search/tag/archive/feed/404/thanks…）→ 标 role，不进正文统计 | S3 | 0（口径） | R | site |
| CLN-02 | 演示/模板页识别 | 路径含 `pabriz-`、`elementor-`、`/page/`、`?page_id=`、主题 demo 名，或页面结构与模板演示一致 → 标 demo | S2 | 5；索引膨胀另计 | R | site |
| CLN-03 | Lorem/占位文案 | 命中特征：`Lorem ipsum`、`Ut elit tellus…`、`Primis non dignissim…`、`Massa volutpat ridiculus…`、`Nisi arcu auctor himenaeos…`、`Dedicated for best quality innovations`、`under construction`、`your-`、`example.com` | S1（正文页） / S3（legal） | 按占位段落占比 -3~-10 | R | content |
| CLN-04 | 0 值/占位计数器 | 数字字段为 0 但语义应为正值（Years Experience / Projects / Staff / Showrooms / Countries / Revenue / Patents 等），且同页其他文本给出非 0 值 → S2 | S2 | 5 | R | content |
| CLN-05 | 默认合规模板 | 隐私/条款页命中 WordPress 默认模板句式（"When visitors leave comments…"/"Gravatar service"/"An anonymized string created from your email address"）→ S2 | S2 | 4 | R | legal |
| CLN-06 | 占位 CTA/空链接 | CTA 文本为 `Discover more`/`Read more`/`Click here`/`Learn more` 且 href 为 `#`/空/`javascript:void(0)` → S3；同页 ≥3 处 → S2 | S3/S2 | 3/5 | R | content |
| CLN-07 | 软 404 | 200 但标题/正文含 `404`/`not found`/`页面不存在`，或正文 <200 字符且无 H1 → S3 | S3 | 4 | R | site |
| CLN-08 | 重复/复制内容 | 跨页 5-gram 重复率 >0.5（去模板/导航后）且占正文 >50% → S2 | S2 | 5 | R | content |
| CLN-09 | 索引膨胀 | (system + demo + legal) 可索引页 / 扫描页 >20% → S2“索引垃圾稀释正文” | S2 | 5 | R | site |
| CLN-10 | Template Residue Score | 按 CLN-02/03/04/05/06 命中数与覆盖页数加权（0–100）；≥30 判“显著模板残留” | S2 | 并入 CLN 各项 | R | site |
| CLN-11 | 模板来源指纹 | 与公开 Template Kit 文案/结构特征比对（如 Pabriz + Elementor Demo 串），给出“疑似基于 XX 模板二开” | S3（提示） | 2 | R+LLM | site |

### 2.3 SCH 结构化数据

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| SCH-00 | 站点类型适用性 | 先判定站点类型（personal/ecommerce/saas/corporate/blog/unknown）；不适用的检查项**从分母剔除**并把分值重分配给适用项（保持子模块满分）；个人站不要求 Product/HowTo/FAQPage 与 Product→Organization 嵌套，可弱化可见作者要求 | S3 | 0（权重重分配） | R | site |
| SCH-01 | 类型覆盖（Tier 权重） | Tier1：Article(BlogPosting) 4 / HowTo 4；基础：Organization 2；辅助：ItemList 1；按站点类型过滤后重分配。**FAQPage 自 v2026.10 起降为辅助项（W 类，不计分）**——Google 自 2023-08 起 FAQ 富媒体结果仅面向权威政府/医疗站点（[依据](https://developers.google.com/search/blog/2023/08/howto-faq-changes)）；缺失仅在报告“需确认或补充的信息”中列出 | S3 | 维度内 10 | R | site |
| SCH-02 | 必需属性 | 命中类型的必需属性完整率（Organization：name/url/logo/sameAs/description/contactPoint；Article：headline/datePublished/dateModified/author；Product：name/image/description/offers） | S3 | 维度内 | R | site |
| SCH-03 | 嵌套/组合 | Article→Organization/Person（2）、Product→Organization（2）、≥4 类型组合（1；3 类 0.7、2 类 0.4）、跨 script `@id` 互引 | S4 | 维度内 5 | R | site |
| SCH-04 | name/url 与站点一致 | schema `name` 命中占位/页面标题（如 `homepage - xxx`、`site name`、`untitled`）或 `url` 与页面不同源 → S2 | S2 | 8 | R | site |
| SCH-05 | logo/image 可解析 | URL 非 200/非图片/明显占位（`logo.png` 不存在）→ S3 | S3 | 3 | R | site |
| SCH-06 | sameAs 真实性 | 站内拼造（`/facebook`）、域与平台不匹配、目标 404/非平台主页 → S3 | S3 | 4 | R | site |
| SCH-07 | contactPoint/email 一致 | `telephone` 占位（`+86-xxx`、`000`、`your-`）；`email` 域名 ≠ 站点域名 → S2 | S2 | 6 | R | site |
| SCH-08 | 日期合理性 | datePublished > dateModified、未来日期、模板日期（如 1970/2000-01-01）→ S3 | S3 | 3 | R | content |
| SCH-09 | @id/引用完整性 | 跨 script `@id` 引用无法解析；WebSite.publisher 指向的 Organization 不存在 → S3 | S3 | 3 | R | site |
| SCH-10 | 作者/publisher 一致 | Article.author 与页面 byline 不一致；publisher 与 Organization.name 不一致 → S3 | S3 | 4 | R | content |

### 2.4 ENT 实体一致性

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| ENT-01 | 品牌写法一致性 | 归一化（小写、去空格/连字符/法律后缀）后，从 schema.name / og:site_name / title 后缀 / 版权 / 页脚公司块 / About H1 收集品牌写法；≥2 个显著不同且各出现 ≥3 次 → S1；拼写近似（编辑距离 ≤2，如 Sofeyia/Suofeiya）→ S1。**排除**：`alternateName` 已声明的别名、与声明名互相包含的标题/页脚噪声（如「品牌名+隐私政策」）、口号/句子，以及**按 locale 分组后不在同一 locale 内共现**的写法（多语言本地化不是写法不一致） | S1 | -8~-12；Trust Ceiling | R | site |
| ENT-02 | 邮箱域名一致性 | 收集 `mailto:` 与正文邮箱。**单一域名 ≠ 站点注册域（含 126/163/qq/gmail 等免费邮箱）→ W 警告项，不计分**，仅在报告中作为建议项列出（主体仍唯一，不构成实体冲突；免费邮箱与外部域名邮箱不区分，修法相同）；**同时出现 ≥2 个不同邮箱域 → S1**（站点自相矛盾） | S1 / W | 0（W）；≥2 域时 -5~-10；Trust Ceiling 仅 S1 | R | site |
| ENT-03 | 电话/地址真实性 | 占位电话（xxx/000/1234567）；地址字段缺失或与页脚不一致 → S3 | S3 | 3 | R | site |
| ENT-04 | 公司法定名一致性 | 含 Co., Ltd/Group/Corporation 的名称在不同位置不一致 → S2 | S2 | 5 | R | site |
| ENT-05 | 社交账号一致性 | sameAs/页脚社交 handle 命名不一致（如 SofeyiaOfficial vs sofeyiahome）→ **W 警告/建议项（不计分）**：品牌可能有多个运营账号与策略，仅提示统一或说明 | W | 0 | R | site |
| ENT-06 | 子品牌/代理关系清晰 | 出现“引入/代理/合作/源自/partner/introduce/distributor”等关系动词，但主体无法对应到已声明 Organization/品牌实体 → S2 | S2 | 5 | R+LLM | site |
| ENT-07 | 声明/历史矛盾 | 跨页或同页矛盾（成立年份、发源地、归属主体、员工/营收数字）→ S2 | S2 | 6 | LLM | site |
| ENT-08 | 信任页内容匹配 | privacy/contact/terms 页面内容与页名不符（空页/软 404/无关内容）→ S2 | S2 | 4 | R+LLM | trust |

### 2.5 ONP On-Page / 主题

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| ONP-01 | Title | 缺失 → S2；>60 或 <10 字符 → S3（demo 页清洗后仍占位 → S2） | S2/S3 | 6/4 | R | content |
| ONP-02 | Meta description | 缺失 → S3；>155 或 <50 → S3；占位（含 lorem）→ S2 | S3/S2 | 5 | R | content |
| ONP-03 | H1 | 0 个 → S2；>1 个 → S3 | S2/S3 | 6/4 | R | content |
| ONP-04 | 标题层级 | H3 先于 H2 或跳级（H1→H3）→ S3；>1/3 content 页命中 → S2 | S3/S2 | 3/4 | R | content |
| ONP-05 | 顶部关键信息 | 首页/内容页首屏（HTML 前部与 H1 后首段）未直接陈述页面主题 → S3 | S3 | 3 | R+LLM | content |
| ONP-06 | 单主题/对题 | title 与 H1/正文语义相似度过低（阈值由 LLM 判定）→ S3 | S3 | 3 | LLM | content |

### 2.6 OGP 开放图谱

> v1.1 计分口径：**只评首页**。内页缺标签或内页有标签都不参与本维计分，只作为建议项列出。

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| OGP-01 | 基础 OGP 标签 | `og:title`/`og:description`/`og:image`/`og:url` 各 0.75（基础 3 分）；内容为占位（`homepage`/lorem/整页拼接）另记 S3 质量提示，但存在性仍计分 | S3 | 维度内 3 | R | home |
| OGP-02 | Twitter Card | `twitter:card` +1（必备）、`twitter:title` +0.5、`twitter:description` +0.5，上限 2 | S4 | 维度内 2 | R | home |

### 2.7 KG 知识图谱 / 实体权威

> v1.1 计分口径：sameAs 每条 1 分（上限 4）+ knowsAbout 3 + foundingDate 1 + 地址/服务区域 2 = 10。
> KG-04（外部权威引用）为**建议项**：只报告、不计分。

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| KG-01 | sameAs 社交链接 | 组织 schema 内 sameAs 去重后每条 1 分，上限 4 | S3 | 维度内 4 | R | site |
| KG-02 | knowsAbout | 存在即 3 分 | S3 | 维度内 3 | R | site |
| KG-03 | foundingDate | 有 =1 | S4 | 维度内 1 | R | site |
| KG-04 | 外部权威引用 | 正文区（排除 nav/header/footer）外链去重；权威域白名单：wikipedia.org、ieee.org、iso.org、iec.ch、europa.eu、gov.cn、gov.uk、.gov、.edu、.ac.、standards.、nist.gov、rfc-editor.org、docs.google.com、developer.mozilla.org、w3.org；**v1.1 起只报不评（scored=false）** | S3 | 0（建议项） | R | content |
| KG-05 | 内部实体链接 | 有效正文内链（去重、排除模板导航/页脚）：≥5=2、≥3=1.5、≥1=1 | S4 | 维度内 2 | R | content |
| KG-06 | 地理位置/服务区域 | schema 含 location/areaServed/address =2 | S3 | 维度内 2 | R | site |

### 2.8 RCH 内容丰富度与新鲜度

> v1.1 引擎计分口径：FAQ 5 + 文章 5（1 篇 2.5）+ 正文体量 5（>8k 得 2.5）= 15。
> 下表为规则判定阈值与历史子分方案；**llms.txt 不在本维计分**，只在加分项 +3。
> 抽样时 FAQ/About/Contact/Privacy 必检页会被强制补入（见 §0.3）。

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| RCH-01 | FAQ 质量 | FAQ 页判定：URL 含 `faq` 或有 FAQPage schema（其他条件不算，避免误判）。子分（历史方案，满分 6）：① 平均每页问题数 ≥5→2、≥3→1；② FAQPage schema 覆盖率 100%→1（覆盖 0% 不得分）；③ 答案资产率（可吸收素材）≥50%→3、>0→1。**v1.1 引擎计分：存在 FAQ 页即 5 分** | S3 | 维度内 FAQ 5 | R | content |
| RCH-02 | 文章/内容资产 | 子分（满分 4）：① 去误判后文章数 ≥20→2、≥10→1（仅 1 个 blog 页且 title 无 blog/文章/博客/news 关键词视为 SPA fallback，剔除）；② Article schema 覆盖率 ≥50%→2、≥25%→1 | S3 | 维度内 blog 4 | R | content |
| RCH-03 | 指南/技术文档 | 子分（满分 4）：guide/HowTo 页存在→2；技术文档/API 页存在→2。仅当路径（/docs、/guides、/help、/tutorial）或页面语义确为文档时计；排除首页与 demo 页 | S3 | 维度内 knowledge 4 | R | content |
| RCH-04 | 真实新鲜度 | 子分（满分 6）：dateModified 覆盖 ≥100%→2、≥50%→1；datePublished 同；近 3 个月有更新→2。分母=含日期的**唯一 content 页数**，rate 封顶 100%，date 字段每页只计一次（避免出现 >100% 的畸形比率） | S3 | 维度内 freshness 6 | R | content |

### 2.9 ABS 吸收潜质（内容侧）

> 维度 15 分 = **Citability 五子项 20 分制 × 0.75**。与 `geo_ready` 的
> `WebsiteAnalyzer::Analyzers::CitabilityAnalyzer` 同一模型，实现见 `scripts/citability.py`。
> 子项原始分：可引用块率 7 + 证据块覆盖 7 + 直接回答 3 + 结构化答案资产 2 + 对题度 1 = 20。

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响（20 分制） | 方法 | 范围 |
|---|---|---|---|---|---|---|
| ABS-01 | 可引用内容块率 | 按块级元素抽块（`p`/`blockquote`/`ul`/`ol`/`table`/`dl`/`details`/FAQ 容器，剔除 nav/header/footer 等容器）；词数窗口：段落英文 100–200、中文等效 60–220，结构化块 30–220；须自包含（英文首字母大写 + 句末标点 + ≥5 词；中文 ≥50 字符 + 句末标点；结构化块默认自包含），且非空泛（`many/some/various/several/etc` 命中时需含数据豁免）。可引用率 = 可引用块 ÷ 全部块，锚点 0→0 / 10→3 / 25→5 / 40→7（线性插值） | S2 | ≤7 | R | all |
| ABS-02 | 证据块覆盖 | 定义 / 数据 / 对比 / 步骤四类：每类 ≥2 块且密度 ≥2% 记有效；有效 4 类→7、3 类→5、2 类→3、1 类→1 | S2 | ≤7 | R | all |
| ABS-03 | 数据可验证 | 数据点需带单位/上下文；过滤模板数字（`9.16%`、`2026`、`123`）与占位；**W 警告项**：无法当场考证的外部数据只列出、不计分 | W | 0 | R+LLM | content |
| ABS-04 | 直接回答 | 每页首个正文段（40–1200 字符）在 40–150 词内且含数据或定义；覆盖率 ≥60→3、≥30→2、>0→1 | S3 | ≤3 | R | all |
| ABS-05 | 结构化答案资产 | 摘要类小标题（summary/tl;dr/要点/总结…）+ 数据表格（≥2 行）+ 答案列表 + FAQ 答案块，合计 ≥5→2、>0→1 | S3 | ≤2 | R | all |
| ABS-06 | 对题度 | title/H1 与首段主题词重合，或存在提问式小标题（what/why/how/什么/如何/区别…）；覆盖率 ≥50 计 1 | S3 | ≤1 | R | all |

> 与旧口径（v1.0）的差异：不再使用「整体段落长度 80–1200 字符 + 句末标点 + 数字/关键词」
> 的单一比率，也不再给 FAQ +3 —— 旧版合计只有 14 分且与产品端两套模型，同一站点两侧分数不一致。

### 2.10 TRU 信任 / E-E-A-T

> 维度 15 分子分（草案）：作者 Schema 3 + 署名真实性 3 + 信任页 3 + 专业资质 3 + About/团队 2 + Experience（一手证据）1。

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| TRU-01 | 作者 Schema | 无 author/Person → S3 | S3 | ≤3 | R | content |
| TRU-02 | 署名真实性 | byline 存在但名称为主题/建站商默认（admin/theme/ehaitech 等）或与站内作者页不符 → S2，该子项不得分 | S2 | ≤3 | R | content |
| TRU-03 | 信任页内容 | privacy/contact/terms 存在且内容匹配（见 ENT-08）；terms 路径识别需覆盖 `_term-of-use` 等变体；每项 1 分，不匹配不计。**v1.1 实质门槛**：About/Contact 还须不在软 404 且正文 >200 字符；合规页命中默认模板不计分 | S2 | ≤3 | R+LLM | trust |
| TRU-04 | 专业资质信号 | 资质/经验关键词（认证、年经验、研究、专家）+ 对应实体/页面；**W 警告项**：自述资质无第三方出处时只提示、不计分 | W | 0 | R | site |
| TRU-05 | About/团队 | About 页存在且含团队/使命/真实信息（非 lorem） | S3 | ≤2 | R+LLM | trust |
| TRU-06 | Experience/一手内容 | 是否存在一手经验证据（真实项目案例、现场数据、原创图片、客户/项目细节）而非通用营销文案 | S2 | ≤1 | LLM | content |
| TRU-07 | Trust Ceiling | 命中任一 S1 一致性问题（ENT-01 品牌冲突 / ENT-02 出现 ≥2 个邮箱域 等）：`trust` 维度 ≤ 50%、`entity` ≤ 30%、总分上限 ≤70；命中 S1 占位/模板问题：总分上限 ≤75。**注意**：ENT-02 的单一 off-domain 邮箱属 W 警告项，不触发本上限 | S1 | 上限压缩 | R | site |

### 2.11 CIT 引用与来源

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| CIT-01 | 外部权威引用 | 正文区（排除导航/页脚）外链去重，权威域（.gov/.edu/wikipedia/标准组织）计权；仅社交图标不计权威。**v1.1 起只报不评（scored=false）** | S3 | 0（建议项） | R | content |
| CIT-02 | 声明出处 | 关键数字/结论是否给出可核验来源（机构+时间/链接）；**W 警告项**：无来源只列出、不计分（提示客户补来源） | W | 0 | R+LLM | content |
| CIT-03 | 多源交叉核验（可选） | 对关键声明做站外一致性抽查，给出“可核验/存疑”标注；**W 警告项**（外部不可完全考证时不扣分） | W | 0 | LLM | site |

### 2.12 QLT 内容质量

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| QLT-01 | Helpfulness | 是否面向读者、一手经验、非商品化；Who/How/Why（谁写的/怎么做的/为什么可信）是否可回答 | S2 | 5 | LLM | content |
| QLT-02 | 批量占位/低价值内容 | 批量同质段落、AI 味模板文、无信息量复述 → S2。**对外表述禁止使用 “scaled content abuse / spam abuse” 定性**：该术语指以操纵排名为主要目的的大规模造页；模板残留与低价值索引页应表述为“可能稀释站点质量信号，建议 noindex 或删除”（依据 [Google spam policies](https://developers.google.com/search/docs/essentials/spam-policies)） | S2 | 5 | LLM | content |
| QLT-03 | 营销空话 | 高频空洞形容词、无事实支撑的“第一/领先/最好”；**W 警告项**（表述风格建议，不计分） | W | 0 | LLM | content |

### 2.13 TEC 技术/性能

| ID | 规则 | 判定与阈值 | 严重度 | 分值影响 | 方法 | 范围 |
|---|---|---|---|---|---|---|
| TEC-01 | Canonical | 缺失页占比 >50% → S2；否则 S3；全缺 → S2 | S2/S3 | 4 | R | content |
| TEC-02 | 渲染模式 | 首页 CSR 判定 → S1（与 ACC-06 合并去重） | S1 | 6 | R | home |
| TEC-03 | HTML 体积/性能代理 | >500KB 页占比 >20% → S3 | S3 | 3 | R | content |
| TEC-04 | 域名/证书一致性 | apex 与 www 的 TLS 证书是否覆盖全部对外域名；apex 证书主机名不匹配仅 **W 警告**（不计分），提示修复或强制 301 到 www | W | 0 | R | site |

---

## 3. 打分规则（规则 → 分数）

### 3.1 维度权重（v6 草案）

| 维度 | 规则来源 | 满分 |
|---|---|---|
| Schema（存在性+正确性） | SCH-00~10 | 20 |
| 实体与品牌一致性 | ENT-01~08 | 10 |
| OGP/社交 | OGP-01/02 | 5 |
| 内容丰富度+新鲜度 | RCH-01~04 | 15 |
| 知识图谱/实体权威 | KG-01~06 | 10 |
| 吸收潜质 | ABS-01~06 | 15 |
| E-E-A-T/信任 | TRU-01~06 | 15 |
| On-Page/主题 | ONP-01~06 | 5 |
| 内容质量 | QLT-01~03 | 5 |
| **合计** | | **100** |

### 3.2 惩罚与加分

| 项 | 规则 | 调整 |
|---|---|---|
| AI 检索爬虫被挡 | ACC-01 | -15 |
| 非 HTTPS / 不跳转 / 重定向过长 | ACC-05 | -10 / -3 / -3 |
| 严重实体不一致 | ENT-01 / ENT-02（≥2 个邮箱域） | -8~-12 / -5~-10 |
| 单一邮箱域 ≠ 站点域（含免费邮箱） | ENT-02（W） | 0（列出不计分） |
| lorem/占位主体内容 | CLN-03 | 按占比 -3~-10 |
| 复制站/纯模板站 | CLN-08/10 | -10~-20 |
| llms.txt | ACC-07 | +3（可选） |
| ItemList Schema | SCH-01 | +3（FAQPage 缺失自 v2026.10 起不计分） |
| 加分上限 | — | bonus 合计 ≤ +10，且不抵消真实性问题 |
| Trust Ceiling | TRU-07 | 维度与总分上限压缩（见 TRU-07） |

> CSR/纯前端渲染不设固定罚分：由 ACC-06/TEC-02 以高优先级 issue + 架构警告呈现，避免与内容/Schema 低分重复扣分。

### 3.3 等级与排序

| 总分 | 等级 |
|---|---|
| 90–100 | A+ |
| 80–89 | A |
| 70–79 | B |
| 60–69 | C |
| 0–59 | D |
| 扫描失败（一页未取到） | F |

- issue 排序：`[-priority_weight, -impact]`（先严重级，再影响分）。
- 分维等级：按该维 percentage 套用同一等级表。

### 3.4 打分原则

1. 存在分与质量分分离：存在通过不等于质量满分（如 FAQ schema 缺失不得因答案资产满分）。
2. 每条扣分可追溯到规则 ID + 证据；无证据不扣分。
3. 比率封顶 100%、分母可见（content 页 N）。
4. 置信度：R 规则=high；R+LLM=medium；LLM=medium/low，标 `review` 时需人工确认。

---

## 4. LLM 规则规格（统一契约）

**输入**：`{rule_id, page_urls[], evidence_pack[], site_context{brand, domain, site_type}, language}`。
**输出**（JSON，全部字段必填）：

```json
{
  "rule_id": "ENT-06",
  "verdict": "pass|fail|uncertain",
  "severity": "S1|S2|S3|S4",
  "confidence": "high|medium|low",
  "summary": {"zh-CN": "...", "en-US": "..."},
  "evidence": [
    {"url": "https://...", "locator": "h1|meta|schema|p#3|footer", "quote": "原文片段"}
  ],
  "recommendation": {"zh-CN": "...", "en-US": "..."},
  "suggested_fix": {"type": "code|text|structure", "content": "..."}
}
```

**约束**：
- `verdict=fail` 必须至少 1 条 evidence，且 quote 必须来自 evidence_pack（后端校验子串）；
- `suggested_fix.content` 禁止包含 evidence_pack 中的占位串（lorem/xxx/示例值）；缺失字段用中性占位并附“待人工补全”；
- 同一 rule 多页证据需去重；无法判断输出 `uncertain`，不臆测。

---

## 5. 输出规范（issue/evidence/建议）

| 字段 | 规范 |
|---|---|
| `issue.id` | 规则 ID（如 `ENT-01`） |
| `issue.title/description/recommendation` | 双语 `{zh-CN,en-US}` |
| `issue.priority` | 由严重度映射（§0.2） |
| `issue.priority_weight / impact` | 按 §0.2 建议区间 |
| `issue.category` | 对应维度 key |
| `issue.confidence` | high/medium/low/review |
| `issue.evidence[]` | `{scope: site\|page, url, locator, quote, rule_text}` |
| `issue.affected_urls[]` | **仅 URL 字符串**（禁止混入 schema 明细等对象） |
| `issue.template_residue_score` | CLN-10 命中时输出 |
| `suggestion[]` | 动作/点数/理由；LLM 建议需过 PRE-05 自检 |

---

## 6. 索菲亚案例应用（Step 1 验收样例）

| 规则 | 现场证据（已核验） | 期望判定 |
|---|---|---|
| CLN-03 | 首页 H1 副标题 `Primis non dignissim…`、About/Contact `Lorem ipsum … Ut elit tellus…` | S1 命中 |
| CLN-04 | 首页/About 计数器 `0 Years Experience`、`0 + Projects Worldwide`、`￥0 Billion` 等 | S2 命中 |
| CLN-05 | `/_privacy-policy/` 为 WordPress 默认模板全文 | S2 命中 |
| CLN-02 | `/pabriz-header/` 等模板演示页 200 在线，sitemap 含 `pabriz-*` | S2 命中 |
| ENT-01 | `Sofeyia`（版权/站名）vs `Suofeiya`（About H1/公司块） | S1 命中 |
| ENT-02 | Contact 同页 `sales@suofeiyahome.com` + `sales@sofeyiahome.com`（**同时出现 2 个不同邮箱域**） | S1 命中 |
| ENT-02 | `chunshanzaiwang@126.com`（官网域名 `resunhotel.cn`，单一 off-domain 邮箱） | **W 命中：列出但不计分**，entity 不扣分、不触发 Trust Ceiling |
| ENT-04 | `Sofeyia Home Collection Co., Ltd` vs `Suofeiya Home Collection Co., Ltd` | S2 命中 |
| ENT-07 | “引入 Sogal 20 年”“源自 1981”“45 年行业”“14 年上市”并存 | S2 命中（LLM） |
| SCH-04 | Organization.name=`sofeyia`（小写，与展示品牌 `Sofeyia`/`Suofeiya` 不一致）；缺 sameAs/description/contactPoint | S2 命中 |
| TRU-07 | 上述 S1 命中 → Trust Ceiling 生效 | E-E-A-T 不得超过 50% |
| RCH-04 | 报告 freshness 916.7% → 分母/封顶修复后重算 | 修正后重评 |
| ABS-01 | 段落可引用率 0%/内容块 2.5% | S2 命中（与内容实况一致） |

> 预期效果：修复前报告 E-E-A-T 10/10、content 15/20 的失真在规则体系下不再出现；报告“重点风险”章节由 CLN-03/04/05、ENT-01/02、SCH-04 驱动。

---

## 7. QA 与验收清单

| 项 | 标准 |
|---|---|
| 单元校验 | 每条 R 规则有 golden 输入/输出样例；索菲亚页面作为回归样本 |
| 证据校验 | 100% `fail` 带证据；quote 必须可在证据包中定位 |
| 占位校验 | 建议/代码中零占位串（lorem/xxx/示例电话） |
| 口径校验 | 比率 ≤100%；分母=content 页；system/demo 单独计数 |
| LLM 校验 | 人工抽检 ≥20 条/批；`uncertain` 不得计分 |
| 版本 | 规则 ID + 版本、prompt 版本随报告输出 |

---

## 8. 下一步（案例流程）

| 步骤 | 内容 | 产物 |
|---|---|---|
| Step 1（本文） | 规则规格 | 本手册 |
| Step 2 | 索菲亚证据包（页面/截图/schema/robots/历史） | golden evidence pack（结构见 `docs/geo_evaluation_data_structure.md`） |
| Step 3 | 按规则跑检测（R + R+LLM + LLM），产出带证据的 issue | 检测结果 JSON |
| Step 4 | 专家逐条核验（Accept/Edit/Reject）+ 客户定制结论 | 正式报告草稿 |
| Step 5 | 报告定稿与线下交付 | 索菲亚正式报告 |

---

## 附录 A：与 `GEO_SCORING_RULES_COMPLETE.md`（v5.0）的覆盖对照

| v5.0 模块 | v5.0 要点 | 本手册对应 | 处理 |
|---|---|---|---|
| Citability 20 分 | 可引用率 10（≥40/20/10）、数据密度 5（≥30/15）、段落质量 5（80–250/50–300） | ABS-01~06 | 已覆盖：沿用 20 分制五子项（可引用块率 7 + 证据块 7 + 直接回答 3 + 结构资产 2 + 对题 1），维度按 ×0.75 折算成 15 分 |
| 段落评分标准 | 词数、自包含、含数据、无模糊、中文 ÷1.5 | ABS-01 | 已覆盖（含中文等效与 vague 豁免） |
| Schema Tier1 覆盖 14 | Article 4 / HowTo 4 / Organization 2 / ItemList 1（FAQPage 自 v2026.10 起降为 W 不计分）；按站点类型过滤与重分配 | SCH-00、SCH-01 | 已补（含类型权重与重分配规则） |
| Schema 属性 6 | Organization/Product/Article 必需属性表 | SCH-02 | 已覆盖（属性清单一致） |
| Schema 嵌套 5 | Product→Org 2、Article→Org 2、≥4 类型 1（3 类 0.7、2 类 0.4） | SCH-03 | 已补精确分值 |
| 内容丰富度 20 | FAQ 子分、blog 子分、guide/tech、freshness 子分与阈值 | RCH-01~04 | 已补精确子分与阈值（含 FAQ 页判定、blog 误判过滤、新鲜度分母修复） |
| Knowledge Graph 15 | sameAs 3、knowsAbout 3、foundingDate 1、外部权威 4（域名白名单）、内链 2、location 2 | KG-01~06 | 已补（含 16+ 权威域白名单与去重要求） |
| E-E-A-T 10 | author schema 2、byline 2、privacy/contact/terms 各 1、expertise 2、about 1 | TRU-01~06 | 已覆盖并扩为 15 分制（新增署名真实性与 Experience 一手证据、Trust Ceiling） |
| OGP 5 | 基础 3（各 0.75）+ Twitter 2 | OGP-01/02 | **本次补入** |
| On-Page 5 | title/meta/H1/层级/canonical 各 1 + issue 阈值 | ONP-01~04 + TEC-01 | 已覆盖 |
| Penalty/Bonus | robots -15、无 HTTPS -10、不跳转 -3、重定向 -3、CSR -15；llms +3、Citability≥40% +4、ItemList +3 | §3.2 | 保留 robots/HTTPS/重定向/llms/ItemList；**弃用 CSR 固定 -15**（改高优 issue + 架构警告，避免与内容/Schema 低分重复）；**弃用 Citability +4**（已计维度分，避免双重计分） |
| AI Crawler 14 UA 与屏蔽判定 | 14 个 UA + 5 条屏蔽规则 | ACC-01 | **本次补全**（完整 UA 清单 + 5 条判定） |
| llms.txt | 200、>10 字符、非 HTML/软 404；缺失 issue | ACC-07 | 已补（改为**可选加分**：Google 官方不读取，不再作为缺失 issue） |
| 技术基础 | HTTPS/canonical/重定向/CSR | ACC-05、TEC-01/02 | 已覆盖 |
| 评分等级/Issue 优先级 | A+~D/颜色、critical-high-medium-low 与排序 | §3.3、§0.2 | 已覆盖（含 issue 排序规则） |
| E-E-A-T bonus（v4 遗留） | eeat≥7 → +3 | — | 弃用（已并入维度计分，避免双重计分） |

**结论**：v5.0 的计分项已全部映射；本次补入的缺口为 **OGP、Knowledge Graph、llms.txt、Schema Tier 权重/站点类型重分配、AI Crawler 完整清单与屏蔽判定**，并把各维子分与阈值明确到可直接实现。

---

*本手册与 `docs/geo_evaluation_methodology_latest.md` 同步；规则阈值为 v1.0 草案，随索菲亚案例回归校准。*
