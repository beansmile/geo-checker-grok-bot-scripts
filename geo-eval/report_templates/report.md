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
{{/dim_pages}}| **九维合计** | **{{dim_sum}}** | **/100** | {{grade}} |

{{#adj_rows}}- {{type}} {{points}}：{{reason}}
{{/adj_rows}}

计算口径：九维显示值合计 {{dim_sum}} → 基础分（保留一位小数）{{base_score}} → 最终总分 {{overall_score}} / 100（{{grade}}）。最终总分＝基础分向下取整，再叠加加减分项。

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
