# 端到端流程（pipeline）

> 当前 skill 的实际执行链（见 `SKILL.md`）：
> `run.py`（抓站）→ `analyze.py`（规则引擎，出 `report.engine.json`）→ `enrich.py`（LLM 深度解读，出 `report.json`）→ `build_report.py`（出 md+html）。
>
> 下文为参考版「分步流水线」（源自索菲亚金样例的 17 个脚本），用于说明各检测阶段的产物与职责，不替代上面这条执行链。

> 从输入网址到输出报告，共 5 步。每步产出物作为下一步输入，全部落在 run 目录下。

```
输入 URL
  → Step 1 抓站         robots / sitemap / llms.txt + 深检页面 HTML
  → Step 2 证据解析     SiteProfile / PageEvidence + 页面角色分类 + 确定性规则(R)
  → Step 3 规则判定     确定性规则 R + LLM 语义块 → rule_results / issues / 评分
  → Step 4 专家复核     Accept / Edit / Reject → 校准后的评分与结论
  → Step 5 出报告       md + html 客户报告
```

## Step 1 · 抓站（`scripts/fetch_site.py`）

- 抓 `/robots.txt`、`/sitemap.xml`、`/llms.txt`、`/llms-full.txt`
- 解析 sitemap 得到 URL 清单，抽样约 24 个深检页面（home/about/contact/faq/product/project/services/legal/system/demo 各角色覆盖）
- 保存 `evidence/pages/*.html` + `evidence/pages.list`

**产物**：`evidence/{robots.txt, sitemap*.xml, llms*.txt, pages/*.html}`

## Step 2 · 证据解析（`scripts/build_evidence.py`）

- 解析 HTML → `pages/*.json`（title/meta/H1/schema/ogp/links/text_stats）
- 生成 `site.json`（品牌候选、邮箱、公司名、社交、robots、llms、sitemap、tech）
- 生成 `scope.json`（URL 清单 + 页面角色分类 content/system/demo/legal/trust）
- 跑确定性规则（R），产出 `rule_results.json`

**产物**：`pages/*.json`、`site.json`、`scope.json`、`rule_results.json`

## Step 3 · 规则判定（`scripts/run_rules.py` + `merge_llm.py`）

- `run_rules.py`（Step 3a）：跑完确定性规则 R，产出 `rule_results.json` / `issues` / `run.json`
- `merge_llm.py`（Step 3b）：由 LLM 完成语义类规则判定 + 规则→维度评分映射，产出 `llm_checks.json` + `scoring_map.json`
- `run_remaining_rules.py`（Step 3c）：跑补充规则（不计分，待专家确认）

**产物**：`rule_results.json`、`run.json`、`llm_checks.json`、`scoring_map.json`

## Step 4 · 专家复核（`build_expert_review.py` → `apply_expert_review.py`）

- `build_expert_review.py`（Step 4a）：生成专家核验工作单 + ExpertReview 骨架
- `apply_expert_review.py`（Step 4c/5a）：应用专家决策（Accept/Edit/Reject），产出 decisions CSV、结果 JSON、报告草稿

**产物**：`expert_review*.json`、`expert_review_decisions.csv`、`report_draft.md`

## Step 5 · 出报告

| 脚本 | 产物 |
|---|---|
| `build_report_client.py` | `report/*_compact.md` + `.html`（精简版） |
| `build_report_deck.py` | `report/*.html`（主报告·卡片式 deck） |
| `build_report_official.py` | `report/*_long.html`（长文版） |

报告版式模板见 `report_templates/`。

## run 目录约定

```
runs/<site>/<date>_runNN/
├── evidence/        # Step 1 产物
├── pages/           # Step 2 页面 JSON
├── site.json        # 站点画像
├── scope.json       # URL 清单 + 角色
├── rule_results.json
├── run.json
├── llm_checks.json
├── scoring_map.json
├── expert_review*.json
└── report/          # Step 5 报告
```
