# 评分规则（scoring）

> 10 维 100 分制，口径 v1.2（2026-11）。规则来源见 `rules.md`；方法论依据见 `methodology.md`；
> SEO 维度细则见 `seo_scoring.md`。

## 1. 维度权重

| 维度 | 规则域 | 满分 |
|---|---|---|
| 结构化数据 | SCH-00~10 | 12 |
| 品牌与实体一致性 | ENT-01~08 | 12 |
| 开放图谱与分享 | OGP-01/02 | 5 |
| 内容覆盖与新鲜度 | RCH-01~04 | 12 |
| 站内实体信号 | KG-01~06 | 10 |
| 答案可吸收性 | ABS-01~06 | 12 |
| 信任度 | TRU-01~07 | 12 |
| 页面主题与元数据 | ONP-01~06 | 5 |
| 内容质量 | QLT-01~03 | 5 |
| **SEO 内容可发现性** | SEO / `seo_scoring.md` | **15** |
| **基础合计** | | **100** |

加减分（ACC、llms.txt +3、ItemList +3 等）**不**并入上表，见第 3 节；报告先展示基础分 /100，再单独展示 `score_adjustments`。

## 2. 分维计分口径（v1.2）

相对 v1.1：原满分 15 的五维（schema / entity / richness / absorption / trust）按 **×12/15** 折算到满分 12；检查项与取样方式不变。SEO 为新增维度。

| 维度 | 计分方式 | 满分可达 |
|---|---|---|
| schema | 内部仍按 v1.1 满分 15 口径累计，再 ×12/15（保留 1 位） | 12 |
| entity | 内部 15 − 实体扣分，再 ×12/15 | 12 |
| ogp | 只评**首页**：`og:title/description/image/url` 各 0.75 + `twitter:card` 2。内页缺标签只作建议项 | 5 |
| richness | FAQ / 文章 / 正文体量三项内部满分 15，再 ×12/15；`llms.txt` 不计入本维 | 12 |
| kg | sameAs 每条 1 分、上限 4；knowsAbout 3；foundingDate 1；address/location/areaServed 2 | 10 |
| absorption | **Citability 五子项（20 分制，×0.6 折算）**：可引用块率 7 + 证据块覆盖 7 + 直接回答 3 + 结构化答案资产 2 + 对题度 1 | 12 |
| trust | About / Contact / 合规 / 作者 / 正文体量内部满分 15，再 ×12/15 | 12 |
| on_page | Title / Meta / H1 覆盖（不变） | 5 |
| quality | 5 − 清洁度扣分（不变） | 5 |
| **seo** | 启发式先打 `/25`（`seo_analyze.py`），再 `dim = round(raw×15/25, 1)` 封顶 15；子信号见 `seo_scoring.md` | 15 |

> `llms.txt` 只在第 3 节加分项里 `+3`，不在 richness / seo 维度内重复计分。

## 3. 惩罚与加分

| 项 | 规则 | 调整 |
|---|---|---|
| AI 检索爬虫被 robots 屏蔽 | ACC-01 | -15 |
| 非 HTTPS / 不跳转 / 重定向过长 | ACC-05 | -10 / -3 / -3 |
| 严重实体不一致（品牌冲突 / ≥2 个邮箱域） | ENT-01 / ENT-02 | -8~-12 / -5~-10 |
| 单一邮箱域 ≠ 站点域（含免费邮箱） | ENT-02（W 警告项） | 0（列出不计分） |
| lorem/占位主体内容 | CLN-03 | 按占比 -3~-10 |
| 复制站/纯模板站 | CLN-08/10 | -10~-20 |
| llms.txt | ACC-07 | +3（唯一计分处） |
| ItemList Schema | SCH-01 | +3 |
| 加分上限 | — | bonus ≤ +10，不抵消真实性问题 |

> CSR/纯前端渲染不设固定罚分：由 ACC-06/TEC-02 以高优先级 issue + 架构警告呈现，避免重复扣分。
>
> 报告展示顺序：**基础分（十维合计，≤100）** → **加减分（`score_adjustments`）** → **最终 `overall_score`**。加减分永不并入维度权重表。

## 4. Trust Ceiling（信任上限，TRU-07）

命中任一 S1 一致性问题（ENT-01 品牌写法不一致 / ENT-02 邮箱域名不一致）时：

| 约束 | 值 |
|---|---|
| trust 维度 | ≤ 50%（=6/12） |
| entity 维度 | ≤ 30%（=3.6/12） |
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

报告 HTML 显示 `Advisory` / `建议项` 徽标；`scope_warnings` 同样在「检测范围」页展示。

## 8. 打分原则

1. **存在分与质量分分离**：存在通过 ≠ 质量满分（如 FAQ 无 schema 但答案资产满分，不得因答案满分给 schema 分）。
2. **每条扣分可追溯**：规则 ID + 证据；无证据不扣分。
3. **比率封顶 100%**，分母 = content 页（见 `rules.md` §0.3）。
4. **置信度**：R 规则 = high；R+LLM = medium；LLM = medium/low（标 `review` 需人工确认）。

## 9. 输出评分结构

报告 JSON 中的 `dimensions` / `category_scores`（10 维，含 `seo`）+ `overall_score` + `grade`，以及 `score_adjustments` / `adjustments`（base_score / penalty / bonus）。SEO 详情另附 `seo_discoverability`（含 `score_raw_25` 与维度分 /15）。每条 finding 带 `scored`（`false` = 建议项）。完整数据结构见 `output_schema.md`。

### 总分计算

```
base_score = sum(dim_scores)          # 十维，封顶逻辑见 Trust Ceiling
overall_score = clamp(0, 100, int(base_score - penalty + bonus))
```

`bonus` 合计 ≤ +10。加减分条目列出在 `adjustments`，不改变维度满分表。
