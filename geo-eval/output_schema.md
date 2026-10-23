# GEO 评测数据结构基线（eval-1.1，用于索菲亚案例）

> 目的：定义**与最新方法论和检测规则完全对齐**的评测数据结构，供规则引擎（`docs/geo_detection_rules.md`，82 条规则 / 14 个域）、LLM 复核与专家评测（`docs/geo_deep_detection_agent_plans.md`）统一读写，作为索菲亚案例（Step 2 证据包 → Step 3 检测 → Step 4 专家核验 → Step 5 报告）的数据契约。
> 对齐版本：`methodology_version: v2026.10`（`docs/geo_evaluation_methodology_latest.md`）、`rules_version: v1.1`（`rules.md`）、`scoring_version: v1.1`（9 维权重：schema 15 / entity 15 / ogp 5 / richness 15 / kg 10 / absorption 15 / trust 15 / on_page 5 / quality 5）。**v2026.11 变更（整数化）**：`category_scores[].score` 一律整数、`percentage` 取整；扣分/上限/下限/惩罚全部整数（取消 `weight_scale`/`floors_pct`，改为绝对整数 `floors`）；`trust_ceiling.caps` 增加整数 `trust_max`/`entity_max`。
> **现行（v1.1）与本节整数化约定的差异**：Trust Ceiling 封顶为 trust ≤7.5、entity ≤4.5；v1.1 起不再使用「维度从宽下限」（entity≥4 / on_page≥2）。本节整数化字段仅用于归档旧版 run.json。
> 原则：向后兼容线上报告、证据驱动（每条结论可回溯）、评测独立（第三方 agent 报告不混入）。
> **eval-1.1 变更**：补齐规则手册新增域（OGP/KG）、`dimension_coverage` 规则到维度追溯、`score_adjustments` 明细（带 rule_id）、Trust Ceiling 双类型与 caps、bonus 上限、`ai_crawler_reachability` / `llms` / `placeholders` / `template_markers` 字段，以及规则↔字段映射表。

---

## 1. 当前线上报告结构快照（2026-09 实测索菲亚报告）

### 1.1 顶层字段（30）

| 字段 | 类型 | 说明 |
|---|---|---|
| `analyze_id` / `url` / `analysis_type` / `status` | string | 任务标识与状态 |
| `created_at` / `completed_at` / `timestamp` | ISO8601 | 时间 |
| `pages_scanned` | int | 扫描页数 |
| `scan_status` / `scan_error_code` / `scan_error_reason` / `scan_failures[]` | string/array | 扫描结果与失败页 |
| `overall_score` / `grade` | int/string | 总分与等级（A+~D；扫描失败 F） |
| `score_adjustments` | object | `base_score / penalty / bonus / adjustments[]` |
| `category_scores` | object | 九维（旧）：`schema_basic_coverage / schema_attributes / schema_nesting / ogp / content_richness / knowledge_graph / citability / eeat / on_page` |
| `page_type` / `site_type` | string/object | `site_type{type,label,source,adjustable,schema_checks}` |
| `rendering_mode` / `csr_warning` | string/object | CSR/SSR 与警告 |
| `scoring_version` | string | 例 `geo-4.0+ar-1.0` |
| `citability_data` | object | 内容块/证据块/直接回答/结构化资产/查询对齐/样本 |
| `issues[]` | array | 问题列表（见 1.2） |
| `action_items[]` | array | 最多 3 条 |
| `improvement_suggestions` | object | 按维度的修复建议 |
| `details` | object | 分析器原始输出 |
| `summary` | object | 双语总评 |
| `agent_readiness` | object | **第三方 agent 可用性范畴，移出本结构**（见 §2.10） |
| `report_visibility` / `can_share` | string/bool | 可见性 |

### 1.2 `issues[]` 元素结构（当前）

```
title/description/recommendation : {zh-CN, en-US}
category                          : string
priority                          : {zh-CN, en-US}      ← 展示态双语
priority_weight                   : int
impact                            : int
code_needed                       : bool
code_snippet                      : {language, code, description}
evidence                          : {scope, summary, rule, affected_urls[]}
owner_role                        : {zh-CN, en-US}
```

### 1.3 持久化与前端类型

- 数据库：`analyses`（`overall_score/grade/category_scores/score_adjustments/total_pages/total_issues/status/report_data jsonb/analysis_type/access_policy`）；第三方报告独立表 `third_party_reports`。
- 前端：`geo_ready_vue/types/analysis.ts`、`types/api/analyze.ts`；契约 `geo_ready/docs/analysis-api-contract.md`。

### 1.4 用于评测时的不足（eval-1.1 已解决）

| 现状 | eval-1.1 |
|---|---|
| issue 无 `rule_id / severity / confidence / source` | 全部补齐（§2.5） |
| evidence 结构不统一、`affected_urls` 曾混入 schema 明细对象 | 统一 evidence（§2.4）+ affected_urls 仅 URL |
| 九维与 v6 不一致（无 `entity`/`quality`；`citability`） | v6 九维 + 投影映射（§5.1） |
| 无 Trust Ceiling、无模板残留、无规则→维度追溯 | `trust_ceiling`、`template_residue`、`dimension_coverage`（§2.6） |
| `agent_readiness` 与 GEO 主分并列 | 移出，归 `third_party_reports`（§2.10） |
| 无专家核验层 | `ExpertReview`（§2.8） |

---

## 2. 基线数据结构（eval-1.1）

### 2.1 根对象 `EvaluationRun`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | string | ✔ | `"eval-1.1"` |
| `run_id` | string | ✔ | 例 `sofeyiahome-2026-09-15-run01` |
| `analyze_id` | string/null |  | 与线上报告关联 |
| `status` | enum | ✔ | `draft / collecting / rules_done / llm_done / expert_review / report_ready / delivered` |
| `site` | `SiteProfile` | ✔ | §2.2 |
| `scope` | object | ✔ | `{pages_total, by_role{content,system,demo,legal,trust,other}, content_pages[], scope_warnings[]}`；`scope_warnings[]` 为必检页缺失告警 `{required, reason}` |
| `evidence_pack` | object | ✔ | `{captured_at, pages_ref, screenshots_ref}` |
| `rule_results` | `RuleResult[]` | ✔ | §2.4（82 条规则） |
| `quality_review` | `QualityReview` |  | §2.7 |
| `scores` | `Scores` | ✔ | §2.6（v6 九维 + 调整 + 天花板 + 模板残留 + 维度追溯） |
| `issues` | `Issue[]` | ✔ | §2.5（由 rule_results 投影） |
| `suggestions` | `SuggestionGroup[]` | ✔ | 按维度：`category/category_name/current_score/max_score/percentage/total_improvement/target_score/suggestions[]{action,points,reason}` |
| `expert_review` | `ExpertReview` |  | §2.8 |
| `report` | `EvaluationReport` |  | §2.9 |
| `third_party_refs` | string[] |  | 仅登记 `third_party_reports` 引用 |
| `versions` | object | ✔ | `{methodology_version, rules_version, scoring_version, prompt_version}` |
| `created_at` / `updated_at` | ISO8601 | ✔ | 时间 |

### 2.2 `SiteProfile`

```json
{
  "url": "https://www.sofeyiahome.com/",
  "domain": "sofeyiahome.com",
  "registrable_domain": "sofeyiahome.com",
  "site_type": {"type": "corporate", "source": "auto"},
  "brand_candidates": [
    {"value": "Sofeyia", "count": 42, "sources": ["copyright", "og:site_name", "footer"]},
    {"value": "Suofeiya", "count": 37, "sources": ["about_h1", "contact_company_block", "body"]}
  ],
  "company_names": ["Sofeyia Home Collection Co., Ltd", "Suofeiya Home Collection Co., Ltd"],
  "emails": [
    {"value": "sales@sofeyiahome.com", "domain": "sofeyiahome.com", "sources": ["contact-us/mailto"]},
    {"value": "sales@suofeiyahome.com", "domain": "suofeiyahome.com", "sources": ["contact-us/text", "privacy/footer"]}
  ],
  "phones": [{"value": "+86-19966202249", "placeholder": false, "sources": ["contact-us"]}],
  "addresses": [{"value": "Suofeiya Plaza, No. 87, 89, Xinggang East Road, Haizhu District, Guangzhou", "source": "contact-us"}],
  "socials": [
    {"platform": "facebook", "url": "https://www.facebook.com/SofeyiaOfficial"},
    {"platform": "instagram", "url": "https://www.instagram.com/sofeyiahome"}
  ],
  "robots": {
    "has_robots_txt": true,
    "sitemap": ["https://www.sofeyiahome.com/sitemap_index.xml"],
    "blocked_critical": [],
    "blocked_noncritical": [],
    "matched_rules": ["ACC-01"]
  },
  "ai_crawler_reachability": [
    {"ua": "OAI-SearchBot", "url": "https://www.sofeyiahome.com/", "status": 200, "blocked": false},
    {"ua": "GPTBot", "url": "https://www.sofeyiahome.com/", "status": 200, "blocked": false},
    {"ua": "ClaudeBot", "url": "https://www.sofeyiahome.com/", "status": 200, "blocked": false},
    {"ua": "PerplexityBot", "url": "https://www.sofeyiahome.com/", "status": 200, "blocked": false}
  ],
  "llms": {"llms_txt": {"present": false, "status": null}, "llms_full": {"present": false, "status": null}},
  "sitemap": {"url_count": 60, "content_ratio": 0.32},
  "tech": {"https": true, "http_redirects_to_https": true, "redirect_hops": 0, "canonical_coverage": 1.0, "cms_hint": "WordPress+Yoast"}
}
```

> `matched_rules` 记录该字段支撑的规则；`ai_crawler_reachability` 对应 ACC-02；`llms` 对应 ACC-07；`sitemap.content_ratio` 用于 ACC-04/CLN-09。

### 2.3 `PageEvidence`（每页一条）

| 字段 | 说明 | 支撑规则 |
|---|---|---|
| `page_id` / `url` / `role` | `role ∈ content/system/demo/legal/trust/other` | PRE-01/02 |
| `status_code` / `render_mode` | `ssr/csr/unknown` | ACC-06、TEC-02 |
| `title` | `{text, length, issue(missing/too_short/too_long)}` | ONP-01 |
| `meta_description` | 同上 | ONP-02 |
| `h1` / `headings` | `{count, text, issues[]}`；层级跳跃 | ONP-03/04 |
| `language` | `en/zh/…` | ABS 中文等效 |
| `top_fold` | `{direct_answer: bool, quote}` 首屏直接回答 | ONP-05、ABS-04 |
| `content_text_ref` | 文本文件引用（外置） | — |
| `content_blocks[]` | `{type(paragraph/list_group/table_summary/faq_answer/howto_step), word_count, citable, issues[], evidence_type(definition/data/comparison/step|null), data_points[]}` | ABS-01~05 |
| `schema[]` | `{raw, type, name, url, attrs_missing[], same_as[], dates{}, publisher, author, id_refs[]}` | SCH-01~10 |
| `ogp` / `twitter` | 键值对 + `placeholder_flags[]` | OGP-01/02 |
| `links` | `{internal_count, external[]{url, domain, in_main_content, authority(bool), platform}}` | KG-04/05、CIT-01 |
| `dates` | `{datePublished, dateModified, anomalies[]}` | SCH-08、RCH-04 |
| `head_meta` | `{canonical, robots_meta, viewport, hreflang[]}` | TEC-01、ACC-06 |
| `js_disabled` | `{text_length, key_content_present}` | ACC-06 |
| `placeholders[]` | `{kind(lorem/zero_counter/default_legal/placeholder_cta/empty_link), quote, locator}` | CLN-03~06 |
| `template_markers` | `{demo_path, template_fingerprint[], residue_score}` | CLN-02/10/11 |
| `trust_page` | `{kind(privacy/contact/terms/about), content_matches(bool)}` | ENT-08、TRU-03/05 |
| `author` | `{schema_author, byline, is_default_author(bool)}` | TRU-01/02 |
| `quality` | `{helpfulness, ai_bulk_ratio, marketing_fluff_ratio}`（LLM） | QLT-01~03 |
| `screenshot_ref` | 文件引用 | 证据附录 |

### 2.4 `RuleResult`（每条规则每次运行一条）

```json
{
  "rule_id": "ENT-01",
  "rule_domain": "ENT",
  "page_id": null,
  "applicable": true,
  "na_reason": null,
  "verdict": "fail",
  "severity": "S1",
  "confidence": "high",
  "method": "R",
  "metrics": {"brand_candidates": 2, "distinct_normalized": 2, "occurrences": {"Sofeyia": 42, "Suofeiya": 37}},
  "evidence": [
    {"type": "quote", "url": "https://www.sofeyiahome.com/about-us/", "locator": "h1", "quote": "About Suofeiya"},
    {"type": "quote", "url": "https://www.sofeyiahome.com/", "locator": "footer.copyright", "quote": "Copyright © 2025 Sofeyia Home Collection Co., Ltd."}
  ],
  "recommendation": {"zh-CN": "统一品牌写法（Sofeyia / Suofeiya）并同步公司名、邮箱域名与社交账号", "en-US": "Unify brand spelling across name, company, email domains, and social handles"},
  "suggested_fix": {"type": "text", "content": "选择唯一品牌名并全局替换；邮箱统一使用 @sofeyiahome.com"},
  "run": {"rules_version": "1.0", "model": null, "tokens": null, "latency_ms": 12}
}
```

- `verdict ∈ pass|fail|uncertain|na`；`applicable=false`（站点类型不适用）不计分、不进 issue，`na_reason` 说明。
- `method ∈ R|R+LLM|LLM`；`confidence ∈ high|medium|low|review`。
- `evidence[].type ∈ quote|field|url|header|screenshot`；`fail` 必须 ≥1 条可定位证据。

### 2.5 `Issue`（报告面，由 `RuleResult` 投影）

| 字段 | 类型 | 说明 |
|---|---|---|
| `issue_id` | string | `<rule_id>-<instance>`，例 `ENT-01-s1` |
| `rule_id` / `rule_ids[]` | string/array | 来源规则（合并同类问题时用数组） |
| `source` | enum | `rule / llm / expert` |
| `dimension` | enum | v6 维度 key |
| `title` / `description` / `recommendation` | 双语对象 | 展示文案 |
| `severity` / `priority` / `priority_label` | enum/双语 | `severity S1~S4`；`priority critical/high/medium/low`（机器值）；`priority_label` 展示态 |
| `priority_weight` / `impact` | int | 排序与影响分 |
| `confidence` | enum | `high/medium/low/review` |
| `evidence[]` | array | 同 §2.4 |
| `affected_urls[]` | string[] | **仅 URL** |
| `code_needed` / `code_snippet` | bool/object | `{language, code, description}` |
| `owner_role` | 双语对象 | 研发/内容/市场/法务 |
| `template_residue_score` | number/null | 仅 CLN-10 类 |
| `sort_key` | string | `"<priority_weight>-<impact>"`（排序 `[-priority_weight,-impact]`） |
| `scored` | bool | `false` = 只报不评的建议项（权威外链 / 内页 OGP / 单一 off-domain 邮箱）；不计入严重度色带，报告显示 Advisory 徽标。缺省视为 `true` |

### 2.6 `Scores`

```json
{
  "category_scores": {
    "schema":          {"score": null, "max": 15, "percentage": null, "grade": null, "category_name": {"zh-CN": "结构化数据", "en-US": "Structured Data"}},
    "entity":          {"score": null, "max": 10, "percentage": null, "grade": null, "category_name": {"zh-CN": "实体一致性", "en-US": "Entity Consistency"}},
    "ogp":             {"score": null, "max": 5,  "percentage": null, "grade": null, "category_name": {"zh-CN": "开放图谱", "en-US": "Open Graph"}},
    "richness":        {"score": null, "max": 15, "percentage": null, "grade": null, "category_name": {"zh-CN": "内容丰富度", "en-US": "Content Richness"}},
    "knowledge_graph": {"score": null, "max": 10, "percentage": null, "grade": null, "category_name": {"zh-CN": "知识图谱", "en-US": "Knowledge Graph"}},
    "absorption":      {"score": null, "max": 15, "percentage": null, "grade": null, "category_name": {"zh-CN": "吸收潜质", "en-US": "Absorption"}},
    "trust":           {"score": null, "max": 15, "percentage": null, "grade": null, "category_name": {"zh-CN": "信任/E-E-A-T", "en-US": "Trust / E-E-A-T"}},
    "on_page":         {"score": null, "max": 5,  "percentage": null, "grade": null, "category_name": {"zh-CN": "页面主题", "en-US": "On-Page"}},
    "quality":         {"score": null, "max": 5,  "percentage": null, "grade": null, "category_name": {"zh-CN": "内容质量", "en-US": "Content Quality"}}
  },
  "overall_score": null,
  "grade": null,
  "score_adjustments": {
    "base_score": null,
    "penalty": 0,
    "bonus": 0,
    "bonus_cap": 10,
    "adjustments": [
      {"type": "penalty", "rule_id": "ACC-01", "points": -15, "reason": {"zh-CN": "主流 AI 爬虫被 robots.txt 屏蔽", "en-US": "Major AI crawlers blocked"}},
      {"type": "bonus", "rule_id": "ACC-07", "points": 3, "reason": {"zh-CN": "存在 llms.txt", "en-US": "Has llms.txt"}}
    ]
  },
  "trust_ceiling": {
    "applied": true,
    "type": "consistency",
    "triggers": ["ENT-01", "ENT-02"],
    "caps": {"trust_max_pct": 50, "entity_max_pct": 30, "overall_max": 70, "trust_max": 7, "entity_max": 4}
  },
  "template_residue": {
    "score": null,
    "level": "none|low|significant|severe",
    "hits": [
      {"kind": "lorem", "rule_id": "CLN-03", "page_id": "home", "locator": "h1", "quote": "Create. Enhance. and Sustain."},
      {"kind": "zero_counter", "rule_id": "CLN-04", "page_id": "home", "locator": "counters", "quote": "0 Years Experience"}
    ]
  },
  "dimension_coverage": {
    "schema":          {"rules_total": 11, "rules_failed": ["SCH-04", "SCH-07"], "rule_ids": ["SCH-00","SCH-01","SCH-02","SCH-03","SCH-04","SCH-05","SCH-06","SCH-07","SCH-08","SCH-09","SCH-10"]},
    "entity":          {"rules_total": 8,  "rules_failed": ["ENT-01","ENT-02","ENT-04","ENT-07"], "rule_ids": ["ENT-01","ENT-02","ENT-03","ENT-04","ENT-05","ENT-06","ENT-07","ENT-08"]},
    "ogp":             {"rules_total": 2,  "rules_failed": ["OGP-01"], "rule_ids": ["OGP-01","OGP-02"]},
    "richness":        {"rules_total": 4,  "rules_failed": ["RCH-01","RCH-04"], "rule_ids": ["RCH-01","RCH-02","RCH-03","RCH-04"]},
    "knowledge_graph": {"rules_total": 6,  "rules_failed": ["KG-01","KG-02","KG-03"], "rule_ids": ["KG-01","KG-02","KG-03","KG-04","KG-05","KG-06"]},
    "absorption":      {"rules_total": 6,  "rules_failed": ["ABS-01","ABS-02"], "rule_ids": ["ABS-01","ABS-02","ABS-03","ABS-04","ABS-05","ABS-06"]},
    "trust":           {"rules_total": 7,  "rules_failed": ["TRU-02","TRU-07"], "rule_ids": ["TRU-01","TRU-02","TRU-03","TRU-04","TRU-05","TRU-06","TRU-07"]},
    "on_page":         {"rules_total": 6,  "rules_failed": ["ONP-01","ONP-03"], "rule_ids": ["ONP-01","ONP-02","ONP-03","ONP-04","ONP-05","ONP-06"]},
    "quality":         {"rules_total": 3,  "rules_failed": ["QLT-01"], "rule_ids": ["QLT-01","QLT-02","QLT-03"]}
  }
}
```

- 维度满分（v2026.11）：schema 15 + entity 15 + ogp 5 + richness 15 + knowledge_graph 10 + absorption 15 + trust 15 + on_page 5 + quality 5 = **100**。所有扣分为整数；上限为整数（trust ≤ 7、entity ≤ 4、总分 ≤ 70）；维度下限为整数（entity ≥ 4、quality ≥ 1、on_page ≥ 2）。
- 惩罚/加分规则见规则手册 §3.2；`bonus_cap=10`，加分不抵消真实性问题。
- Trust Ceiling 两类：`consistency`（ENT-01/02 等 → trust ≤50%、entity ≤30%、总分 ≤70）与 `placeholder/template`（CLN-03/10 → 总分 ≤75）。
- `dimension_coverage` 让每个维度分可回溯到具体规则，`rules_failed` 即该维度扣分来源。

### 2.7 `QualityReview`（LLM 块，对应 QLT-01~03）

```json
{
  "prompt_version": "qlt-1.0",
  "rule_results": [
    {"rule_id": "QLT-01", "page_id": "about", "verdict": "fail", "severity": "S2", "confidence": "medium",
     "evidence": [{"type": "quote", "url": "https://www.sofeyiahome.com/about-us/", "locator": "h1+first_paragraph", "quote": "..."}],
     "recommendation": {"zh-CN": "...", "en-US": "..."}}
  ],
  "aggregate": {"helpfulness_score": null, "ai_bulk_ratio": null, "marketing_fluff_ratio": null}
}
```

### 2.8 `ExpertReview`

```json
{
  "reviewer": "expert@aeofy.ai",
  "status": "in_progress|done",
  "intake": {
    "client": "索菲亚 / Sofeyia Home",
    "goals": ["提升海外品牌可信度与 AI 可读性"],
    "concerns": ["品牌名混用", "模板残留"],
    "authorization": {"scope": "public pages", "sensitive_pages_excluded": []}
  },
  "items": [
    {
      "issue_id": "ENT-01-s1",
      "machine": {"verdict": "fail", "severity": "S1", "confidence": "high"},
      "decision": "accept|edit|reject|pending",
      "edited_conclusion": {"zh-CN": "...", "en-US": "..."},
      "added_evidence": [{"type": "screenshot", "ref": "screenshots/about-h1.png"}],
      "notes": "客户确认以 Sofeyia 为唯一品牌名"
    }
  ],
  "custom_sections": [{"title": {"zh-CN": "内容架构建议", "en-US": "Content architecture advice"}, "body": {"zh-CN": "...", "en-US": "..."}}],
  "signoff": {"by": "expert@aeofy.ai", "at": "2026-09-16T10:00:00+08:00"}
}
```

### 2.9 `EvaluationReport`（线下交付）

```json
{
  "report_version": "1.0",
  "format": "md|html|pdf",
  "file_ref": "report/report.pdf",
  "sections": ["cover", "executive_summary", "key_risks", "dimension_findings", "issue_details", "fix_plan", "evidence_appendix", "methodology_note", "signoff"],
  "risk_order": ["S1", "S2", "S3", "S4"],
  "delivered_at": null,
  "delivered_to": null
}
```

- `key_risks` 由 S1/S2 issue 驱动（如 `CLN-03/04/05`、`ENT-01/02`、`SCH-04`）。
- `fix_plan` 由 `suggestions[]` 按维度与工作量排序生成。

### 2.10 第三方报告的边界

- `agent_readiness` 及 Ora / Vercel(is-agentic) / Cloudflare(isitagentready) 等结果**不进入本结构**，由 `third_party_reports`（`provider/status/score/grade/payload/interpretation`）独立承载。
- 本结构仅在 `third_party_refs[]` 登记引用，不做分数合并。

---

## 3. 字段规范

| 项 | 规范 |
|---|---|
| 双语 | 展示文案 `{zh-CN, en-US}`；机器值英文枚举 |
| 分数 | 整数 0–100；`score ≤ max`；`percentage` 1 位小数；维度合计 100 |
| 比率 | 分母=唯一 content 页；分子去重；封顶 100% |
| URL | `affected_urls` 仅字符串；evidence URL 绝对地址 |
| 页面角色 | `content/system/demo/legal/trust/other` |
| 严重度↔优先级 | S1→critical（pw 9–10，impact 30–50）；S2→high（3–4，6–12）；S3→medium（2，3–6）；S4→low（1，1–3） |
| 等级 | 90–100 A+ / 80–89 A / 70–79 B / 60–69 C / 0–59 D；扫描失败 F（无有效页面） |
| 置信度 | `high`（R）→ `medium`（R+LLM）→ `low/review`（LLM，需人工确认） |
| ID | `run_id` 唯一；`issue_id=<rule_id>-<instance>`；`page_id=<slug\|hash8>` |
| 时间 | ISO8601 带时区 |
| 空值 | 未计算 `null`；缺失数组 `[]`；不用 0 冒充缺失 |
| 版本 | `schema/methodology/rules/scoring/prompt` 独立记录 |
| 大文件 | HTML/截图/PDF 外置，结构仅存 `*_ref` |

---

## 4. 规则 ↔ 数据结构字段映射

| 规则域 | 主要数据来源字段 | 输出维度 | 关键规则 |
|---|---|---|---|
| ACC | `site.robots`、`site.ai_crawler_reachability`、`site.llms`、`page.head_meta`、`page.js_disabled`、`site.tech` | 门槛/惩罚 | ACC-01~07 |
| CLN | `page.role`、`page.placeholders[]`、`page.template_markers`、`site.sitemap.content_ratio` | 清洁度（并入相关维度扣分） | CLN-01~11 |
| SCH | `page.schema[]` | schema | SCH-00~10 |
| OGP | `page.ogp`、`page.twitter` | ogp | OGP-01/02 |
| KG | `page.schema[].same_as`、`page.links.external[].authority`、`page.links.internal_count`、`location/areaServed/address` | knowledge_graph | KG-01~06 |
| ENT | `site.brand_candidates/company_names/emails/phones/addresses/socials`、`page.content_text` | entity | ENT-01~08 |
| ONP | `page.title/meta_description/h1/headings/top_fold` | on_page | ONP-01~06 |
| RCH | `page.content_blocks[]`、`page.schema[]`（FAQPage/Article）、`page.role`、`page.dates` | richness | RCH-01~04 |
| ABS | `page.content_blocks[]`、`page.top_fold`、`page.content_text` | absorption | ABS-01~06 |
| TRU | `page.author`、`page.trust_page`、`page.content_text`、`site` 一致性结果 | trust | TRU-01~07 |
| CIT | `page.links.external[]`、`page.content_text`（声明/出处） | citations/kg | CIT-01~03 |
| QLT | `page.quality`（LLM） | quality | QLT-01~03 |
| TEC | `page.head_meta.canonical`、`page.render_mode`、`page.content_text` 长度 | on_page/门槛 | TEC-01~03 |
| PRE | 全部页面元信息 | 口径 | PRE-01~05 |

---

## 5. 兼容与投影映射

### 5.1 v6 维度 ↔ 旧报告 key

| eval-1.1 `category_scores` | 旧报告 key | 投影规则 |
|---|---|---|
| `schema` (15) | `schema_basic_coverage`(10)+`schema_attributes`(6)+`schema_nesting`(5) | 求和后按 15 归一；旧 key 仍输出供前端 |
| `entity` (10) | —（新增） | 投影新增维度卡片 |
| `ogp` (5) | `ogp` | 同名直传 |
| `richness` (15) | `content_richness`(20) | 按 15 归一 |
| `knowledge_graph` (10) | `knowledge_graph`(15) | 按 10 归一 |
| `absorption` (15) | `citability`(20) | 按 15 归一 |
| `trust` (15) | `eeat`(10) | 按 15 归一（含 Trust Ceiling） |
| `on_page` (5) | `on_page` | 同名直传 |
| `quality` (5) | —（新增） | 投影新增维度卡片 |

### 5.2 issue 投影

- 旧前端字段保留：`title/description/recommendation/priority(双语)/priority_weight/impact/category/code_needed/code_snippet/evidence{scope,summary,rule,affected_urls}`。
- 新增：`issue_id/rule_id/rule_ids/dimension/source/severity/confidence/priority(机器)/priority_label/template_residue_score/sort_key`；`affected_urls` 强制仅 URL。

### 5.3 落库建议

| 方案 | 表 | 适用 |
|---|---|---|
| 快速（索菲亚本周） | `evaluation_runs(id, run_id, domain, url, schema_version, status, payload jsonb, created_at, updated_at)`；大文件走 storage | 单案例、迭代快 |
| 规范（后续） | `evaluation_runs` + `evaluation_pages` + `rule_results` + `evaluation_issues` + `expert_reviews` + `evaluation_reports` | 多客户、可统计 |

> 线上报告链路继续写 `analyses.report_data`；评测链路独立，通过 `analyze_id` 关联但不互相覆盖。

---

## 6. 索菲亚案例文件组织（建议）

```
storage/evaluations/sofeyiahome/2026-09-15_run01/
├── run.json                 # EvaluationRun 根对象
├── site.json                # SiteProfile
├── scope.json               # 页面清单与角色分布
├── pages/{page_id}.json     # PageEvidence
├── evidence/{page_id}.html  # 原始 HTML/文本
├── screenshots/{page_id}-{locator}.png
├── rule_results.json        # RuleResult[]（82 条）
├── llm_checks.json          # QualityReview + LLM 版 RuleResult
├── scores.json              # Scores（或内嵌 run.json）
├── expert_review.json       # ExpertReview
└── report/
    ├── report.md / report.html / report.pdf
    └── assets/
```

命名：`run_id = <domain>-<YYYY-MM-DD>-run<NN>`；`page_id = slug(url)` 或 8 位 hash；截图 `{page_id}-{locator}.png`。

---

## 7. 校验清单（写入前必须通过）

1. `schema_version="eval-1.1"` 且 `methodology_version/rules_version/scoring_version` 非空。
2. `scores.category_scores` 九维齐全，`max` 合计=100；`percentage ∈ [0,100]`。
3. 每条 `verdict=fail` 的 `rule_results[*].evidence` ≥1，`quote` 可在证据包定位。
4. `issues[*].affected_urls` 全为字符串；无对象混入。
5. `priority` 为机器枚举且 `priority_label` 双语齐全；`sort_key` 与 `[-priority_weight,-impact]` 一致。
6. `trust_ceiling.applied=true` 时 `triggers` 非空且 caps 生效（投影后 trust/entity/总分不超上限）。
7. `score_adjustments.bonus ≤ bonus_cap(10)`；penalty/bonus 项均带 `rule_id`。
8. `template_residue.hits[*].rule_id` 均存在于 `rule_results`；`level` 与 score 区间一致。
9. `dimension_coverage` 覆盖所有参与计分的维度，`rules_failed` 与对应 `RuleResult.verdict=fail` 一致。
10. 建议/代码不含占位串（`lorem`、`xxx`、`示例值`、`+86-xxx`）。
11. `scope.by_role` 计数之和 = `pages_total`；content 与 system/demo 分开。
12. 双语对象两个 key 均存在；`third_party` 内容不出现在除 `third_party_refs` 外任何字段。

---

## 8. 下一步

| 步骤 | 使用结构 |
|---|---|
| Step 2 证据包 | `SiteProfile` + `PageEvidence`（`storage/evaluations/sofeyiahome/...`） |
| Step 3 规则检测 | `RuleResult[]`（82 条规则） |
| Step 3b LLM 复核 | `QualityReview` + LLM 版 `RuleResult` |
| Step 4 专家核验 | `ExpertReview.items[]` |
| Step 5 报告交付 | `EvaluationReport` + `scores`/`issues` 投影 |

---

## 附录：eval-1.0 → eval-1.1 变更

| 变更 | 内容 |
|---|---|
| 新增域 | OGP-01/02、KG-01~06 进入维度与字段（`page.ogp/twitter`、`page.links.external[].authority`） |
| 追溯 | 新增 `dimension_coverage`（规则→维度→扣分来源） |
| 惩罚/加分 | `score_adjustments.adjustments[]` 增加 `rule_id`；`bonus_cap=10` |
| 天花板 | `trust_ceiling.type`（consistency / placeholder）+ 显式 caps |
| 证据字段 | `placeholders[].kind`、`template_markers`、`js_disabled`、`ai_crawler_reachability`、`llms`、`head_meta` |
| issue | `rule_ids[]`、`dimension`、`sort_key`、机器 `priority` + `priority_label` |
| LLM | `QualityReview.rule_results[]` 对齐 QLT-01~03 |
| 专家 | `ExpertReview.intake`（客户目标/关注点/授权范围） |
| 校验 | 12 条（含 bonus cap、维度追溯一致性、天花板生效） |

---

*本基线为 eval-1.1 草案；与 `docs/geo_evaluation_methodology_latest.md`、`docs/geo_detection_rules.md` 同步演进，索菲亚首轮跑通后升级为 eval-1.2。*
