# {{brand}} — GEO Readiness Report

> **{{domain}}** · {{date}} · On-site readiness **{{overall_score}} / 100 ({{grade}})**

This report measures how ready a website is to be correctly understood, trusted and cited by generative search engines (ChatGPT, Perplexity, Google AI Overviews and similar). It does not cover search rankings or traffic, and it does not measure how often AI actually cites the site.

---

## 1. Overall assessment

{{overall_summary}}

> **One-line conclusion**: {{closing}}

---

## 2. Scoring method

Nine dimension scores (capped at each maximum) sum to the base score; adjustments are then added or subtracted:

| Dimension | Score | Max | Grade |
|---|---|---|---|
{{#dim_pages}}| {{name}} | {{score}} | /{{max}} | {{grade}} |
{{/dim_pages}}| **Dimension total** | **{{dim_sum}}** | **/100** | {{grade}} |

{{#adj_rows}}- {{type}} {{points}}: {{reason}}
{{/adj_rows}}

Calculation: displayed dimension scores total {{dim_sum}} → base score (1 decimal place) {{base_score}} → final score {{overall_score}} / 100 ({{grade}}). The final score is the base score rounded down to a whole number, after any bonus or penalty.

Grade scale: A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D < 60.

---

## 3. What's already working

{{#strengths}}- {{.}}
{{/strengths}}

---

## 4. Key findings

{{#findings}}
### {{n}} · [{{severity_display}}] {{title}}

**Problem**: {{problem}}

**Impact**: {{impact}}

**Fix**: {{solution}}

{{evidence_md}}
{{code_md}}
{{/findings}}

---

## 5. Dimension assessment

{{#dim_pages}}
### {{n}} · {{name}} ({{score}} / {{max}} · {{grade}})

{{narr}}

{{findings_md}}
**How to improve**: {{callout}}

---
{{/dim_pages}}

## 6. Priority actions

{{#action_rows}}
- **[{{sev}}] {{action}}** ({{owner}}) — {{detail}}
{{/action_rows}}

---

## 7. Scope

{{scope_text}}

{{scope_note_text}}

{{scope_warning_text}}

---

## 8. Conclusion

{{closing}}

---

*Prepared by Beansmile · GEO Checker*
