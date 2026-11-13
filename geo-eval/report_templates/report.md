# {{brand}} GEO 评测报告

> **{{domain}}** · {{date}} · 站内准备度 **{{overall_score}} / 100（{{grade}}）**

本报告衡量网站在生成式搜索（ChatGPT、豆包、Kimi 等）中被正确理解、信任与引用的准备度，不涉及搜索排名与流量，也不包含 AI 实际引用情况的实测。

---

## 一、总体评价

{{overall_summary}}

> **一句话结论**：{{closing}}

---

## 二、评分方法

九个维度得分（上限内计分），合计为基础分，再加/减调整项得总分：

| 维度 | 得分 | 满分 | 等级 |
|---|---|---|---|
{{#dim_pages}}| {{name}} | {{score}} | /{{max}} | {{grade}} |
{{/dim_pages}}| **十维合计** | **{{dim_sum}}** | **/100** | {{grade}} |

{{#adj_rows}}- {{type}} {{points}}：{{reason}}
{{/adj_rows}}

计算口径：十维显示值合计 {{dim_sum}} → 基础分（各维按 0 或 0.5 计）{{base_score}} → 最终总分 {{overall_score}} / 100（{{grade}}）。总分 = clamp(0, 100, int(基础分 − 罚分 + 加分))，取整数。

等级映射：A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D < 60。

---

## 三、表现良好的部分

{{#strengths}}- {{.}}
{{/strengths}}

---

## 四、关键发现

{{#findings}}
### {{n}} · [{{severity_display}}] {{title}}

**问题**：{{problem}}

**影响**：{{impact}}

**解决**：{{solution}}

{{evidence_md}}
{{code_md}}
{{/findings}}

---

## 五、分维度评估

{{#dim_pages}}
### {{n}} · {{name}}（{{score}} / {{max}} · {{grade}}）

{{narr}}

{{findings_md}}
**提升建议**：{{callout}}

---
{{/dim_pages}}


---

## 五 b. SEO 内容可发现性（独立计分）

**{{seo_score}} / {{seo_max}}（{{seo_grade}}）** · 置信度：{{seo_confidence}}

本分块评估重要内容 URL 是否可被搜索发现与索引（标题/H1/meta 意图匹配、薄内容或重复风险、站内抓取路径、sitemap/robots 作为内容发现辅助）。**独立计分，不并入九维 {{overall_score}} / 100 总分。**

{{seo_narr}}

{{seo_notes_md}}

**改进建议**：{{seo_callout}}

## 六、优先改进建议

{{#action_rows}}
- **[{{sev}}] {{action}}**（{{owner}}）— {{detail}}
{{/action_rows}}

---

## 七、检测范围

{{scope_text}}

{{scope_note_text}}

{{scope_warning_text}}

---

## 八、结论

{{closing}}

---

*署名：Beansmile · GEO Checker*
