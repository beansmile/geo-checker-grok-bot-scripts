#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build standalone Content GEO report (HTML) from content_report.json.

HTML reuses report_templates/style.css so the deliverable matches the technical
GEO readiness report visually. SEO discoverability is NOT part of this report
(see technical report / seo_scoring.md).

Client deliverable is HTML only. Pass --also-md to also write Markdown (internal).

Language (product rule):
  Default English (--lang en → Content_Report.html).
  Chinese only when the agent passes --lang zh → 内容报告.html
  (user message explicitly asked for Chinese, e.g. 中文报告 / Chinese report / 出中文).

For Chinese runs, enrich *primary* narrative fields in Chinese (overall_summary,
closing, dim narr/callout, findings, etc.). Parallel *_zh fields remain supported
as fallbacks when primary prose is still English.
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import sys
from datetime import datetime

try:
    from timeline_ui import render_timeline_block
except ImportError:
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from timeline_ui import render_timeline_block

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def load_report(run_dir: str) -> dict:
    path = os.path.join(run_dir, "content_report.json")
    if not os.path.isfile(path):
        path = os.path.join(run_dir, "content.engine.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def grade_meta(grade: str):
    g = (grade or "D").upper()
    if g == "A+":
        return "#059669", "c-a", "g-a", "var(--success)"
    if g == "A":
        return "#10b981", "c-a", "g-a", "var(--success)"
    if g == "B":
        return "#2563eb", "c-b", "g-b", "var(--info)"
    if g == "C":
        return "#d97706", "c-c", "g-c", "var(--warning)"
    return "#dc2626", "c-d", "g-d", "var(--danger)"


def esc(s: str) -> str:
    return html_mod.escape(s or "", quote=False)



def format_score(n) -> str:
    """Show integers as 18, half-points as 17.5; never 18.0 or 7.3."""
    if n is None or n == "":
        return "—"
    x = float(n)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.1f}"




def inline_md(s: str) -> str:
    """Light **bold** and `code` for HTML prose (already escaped)."""
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def looks_cjk(s: str | None) -> bool:
    return bool(s and _CJK_RE.search(s))


STRINGS = {
    "en": {
        "html_lang": "en",
        "title_suffix": "Content GEO Report",
        "meta_desc": "Content GEO evaluation for {domain}: {score}/100 ({grade}).",
        "topbar_doc": "{brand} · Content GEO · {domain}",
        "cover_no": "Beansmile · GEO Checker",
        "cover_kicker": "Generative Engine Optimization · Content evaluation",
        "cover_h1": "Content GEO Report",
        "cover_sub": (
            "Whether site content can be understood, trusted, and cited — architecture, "
            "page types, writing, authority evidence, and buyer-question coverage."
        ),
        "cover_score_em": "Content GEO {grade}",
        "pass_label": "Pass 60",
        "good_label": "Good 80",
        "cover_score_note": "Confidence: {conf}. Not a search-ranking audit.",
        "site": "Site",
        "report_date": "Report date",
        "pages_analyzed": "Pages analyzed",
        "grade_scale": "Grade scale",
        "grade_scale_value": "A+≥90 · A≥80 · B≥70 · C≥60 · D&lt;60",
        "prepared_by": "Prepared by Beansmile · GEO Checker",
        "footer": "GEO Checker · Content GEO",
        "docfoot": (
            "Content GEO evaluation by Beansmile · GEO Checker. Measures whether website "
            "content can be understood, trusted and cited — not rankings, traffic, or "
            "guaranteed AI mentions."
        ),
        "sec_overall": "01 Overall",
        "kicker_overall": "01 Overall assessment",
        "h2_overall": "Content GEO: {score} / 100 ({grade})",
        "fetch_disclosure": "Fetch disclosure",
        "one_line": "One-line conclusion",
        "sec_method": "02 Scoring method",
        "kicker_method": "02 Scoring method",
        "h2_method": "How the Content GEO score is calculated",
        "method_body": (
            "Five dimensions sum to 100. Titles, crawl paths, and sitemap/robots as "
            "discovery aids are covered in the technical report’s SEO chapter."
        ),
        "th_dimension": "Dimension",
        "th_score": "Score",
        "th_max": "Max",
        "th_grade": "Grade",
        "total_row": "Content GEO total",
        "grade_note": (
            "Grade scale: A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D &lt; 60 · F = unevaluable. "
            "Content GEO rubric."
        ),
        "sec_strengths": "03 Strengths",
        "kicker_strengths": "03 What's already working",
        "h2_strengths": "Existing foundations",
        "dim_sec": "Dimension {n:02d}",
        "dim_kicker": "Dimension · {n:02d}",
        "engine_notes": "Engine notes",
        "how_to_improve": "How to improve",
        "sec_ia": "Architecture",
        "kicker_ia": "Information architecture",
        "h2_ia": "Current vs recommended",
        "recommended_tree": "Recommended tree",
        "page_briefs": "Page briefs",
        "no_page_briefs": "No page briefs.",
        "sec_questions": "Questions",
        "kicker_questions": "Target questions",
        "h2_questions": "On-site support",
        "th_hash": "#",
        "th_question": "Question",
        "th_intent": "Intent",
        "th_support": "Support",
        "th_gaps": "Gaps",
        "no_questions": "No questions recorded.",
        "sec_ai": "AI visibility",
        "kicker_ai": "AI / search visibility",
        "h2_ai": "Would retrieval surface the official site?",
        "ai_note": "Methods are labeled. No engine quotes were invented.",
        "th_method": "Method",
        "th_tools": "Tools",
        "th_brand": "Brand?",
        "th_official": "Official?",
        "th_sources": "Sources",
        "th_notes": "Notes",
        "no_checks": "No checks attached.",
        "yes": "yes",
        "no": "no",
        "sec_authority": "Authority",
        "kicker_authority": "Authority evidence",
        "h2_authority": "What to publish on-site",
        "th_evidence": "Evidence",
        "th_where": "Where today",
        "th_action": "Action",
        "no_offsite": "No off-site inventory.",
        "sec_findings": "Findings",
        "kicker_findings": "Key findings",
        "h2_findings": "Issues to prioritise",
        "see_dims": "See dimension narratives.",
        "problem": "Problem",
        "impact": "Impact",
        "fix": "Fix",
        "sec_actions": "Actions",
        "kicker_actions": "Priority actions",
        "h2_actions": "Ordered next steps",
        "sec_scope": "Scope",
        "kicker_scope": "Scope",
        "h2_scope": "What this assessment covered",
        "fetch_mode": "Fetch mode",
        "pages_analyzed_inline": "Pages analyzed",
        "sample_urls": "Sample URLs",
        "conclusion": "Conclusion",
        "sample_label": "Sample",
        "outcome_label": "Expected outcome",
        "sec_timeline": "12 Follow-up plan",
        "kicker_timeline": "12 Follow-up plan",
        "h2_timeline": "Ordered next steps & schedule",
        "none": "—",
        # Markdown
        "md_title": "{brand} — Content GEO Evaluation Report",
        "md_intro": (
            "This report evaluates whether the site’s **content** can be understood, trusted, and cited "
            "by generative engines: information architecture, page types and gaps, writing quality, "
            "authority evidence, and coverage of real buyer questions (including labeled AI / search "
            "visibility checks). **GEO = Generative Engine Optimization** (websites), not geography."
        ),
        "md_h_overall": "## 1. Overall assessment",
        "md_one_line": "> **One-line conclusion**: {closing}",
        "md_fetch": "**Fetch disclosure**: {text}",
        "md_h_method": "## 2. Content GEO scoring method",
        "md_method_body": (
            "Five dimensions sum to 100. SEO content discoverability (titles, crawl paths, sitemap/robots "
            "as discovery aids) is scored in the technical GEO readiness report, not here."
        ),
        "md_grade_scale": "Grade scale: A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D < 60 · F = unevaluable.",
        "md_h_strengths": "## 3. What's already working",
        "md_none_listed": "- _(None listed)_",
        "md_h_dims": "## 4. Dimension assessment",
        "md_how": "**How to improve**: {text}",
        "md_h_ia": "## 5. Information architecture — current vs recommended",
        "md_recommended_tree": "Recommended tree:",
        "md_page_briefs": "### Page briefs to create or upgrade",
        "md_h_tax": "## 6. Content taxonomy & gaps",
        "md_page_type": "| Page type | Count in sample |",
        "md_h_write": "## 7. Writing quality",
        "md_h_auth": "## 8. Authority & evidence publishing",
        "md_off_header": "| Evidence | Where it lives today | Action |",
        "md_h_tq": "## 9. Target questions × on-site support",
        "md_tq_header": "| # | Question | Intent | On-site support (0–3) | Gaps |",
        "md_no_tq": "_No target questions recorded._",
        "md_h_ai": "## 10. Target questions × AI / search visibility",
        "md_ai_intro": (
            "Checks are labeled by method. `web_retrieval_proxy` = public web/search results used as a "
            "proxy for what retrieval-augmented systems are likely to ground on when live ChatGPT / "
            "Perplexity / Gemini product UIs were not available. **No engine quotes were invented.**"
        ),
        "md_constraint": "- Constraint: {text}",
        "md_ai_header": (
            "| Question | Method | Engines / tools | Brand mentioned? | Official domain cited? | "
            "Sources seen | Notes |"
        ),
        "md_no_ai": "_No AI/search visibility checks attached._",
        "md_h_findings": "## 11. Key findings",
        "md_problem": "**Problem**: {text}",
        "md_impact": "**Impact**: {text}",
        "md_fix": "**Fix**: {text}",
        "md_evidence": "Evidence:",
        "md_see_dims": "_See dimension narratives._",
        "md_h_actions": "## 12. Priority actions",
        "md_h_scope": "## 13. Scope",
        "md_pages": "- Pages analyzed: {n}",
        "md_fetch_mode": "- Fetch mode: `{mode}`",
        "md_sample": "- Sample URLs / files: {n}",
        "md_h_conclusion": "## 14. Conclusion",
        "md_prepared": "*Prepared by Beansmile · GEO Checker*",
        "md_pending": "_Pending enrichment._",
        "md_total": "Content GEO total",
        "unevaluable": "unevaluable",
        "confidence_prefix": "confidence: ",
    },
    "zh": {
        "html_lang": "zh-CN",
        "title_suffix": "内容 GEO 评测报告",
        "meta_desc": "{domain} 内容 GEO 评测：{score}/100（{grade}）。",
        "topbar_doc": "{brand} · 内容 GEO · {domain}",
        "cover_no": "Beansmile · GEO Checker",
        "cover_kicker": "生成式引擎优化 · 内容评测",
        "cover_h1": "内容 GEO 评测报告",
        "cover_sub": (
            "评估站点内容是否可被生成式引擎理解、信任与引用——信息架构、页面类型、写作质量、"
            "权威证据与采购问题覆盖。"
        ),
        "cover_score_em": "内容 GEO {grade}",
        "pass_label": "及格 60",
        "good_label": "良好 80",
        "cover_score_note": "置信度：{conf}。非搜索排名审计。",
        "site": "站点",
        "report_date": "报告日期",
        "pages_analyzed": "分析页数",
        "grade_scale": "等级刻度",
        "grade_scale_value": "A+≥90 · A≥80 · B≥70 · C≥60 · D&lt;60",
        "prepared_by": "Beansmile · GEO Checker 编制",
        "footer": "GEO Checker · 内容 GEO",
        "docfoot": (
            "Beansmile · GEO Checker 内容 GEO 评测。衡量网站内容是否可被理解、信任与引用——"
            "不代表排名、流量或保证被 AI 提及。"
        ),
        "sec_overall": "01 总体评价",
        "kicker_overall": "01 总体评价",
        "h2_overall": "内容 GEO：{score} / 100（{grade}）",
        "fetch_disclosure": "抓取披露",
        "one_line": "一句话结论",
        "sec_method": "02 评分方法",
        "kicker_method": "02 评分方法",
        "h2_method": "内容 GEO 分数如何计算",
        "method_body": (
            "五个维度合计 100 分。标题、抓取路径、sitemap/robots 等发现辅助项见技术报告的 SEO 章节。"
        ),
        "th_dimension": "维度",
        "th_score": "得分",
        "th_max": "满分",
        "th_grade": "等级",
        "total_row": "内容 GEO 总分",
        "grade_note": (
            "等级刻度：A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D &lt; 60 · F = 无法评测。"
            "内容 GEO 量规。"
        ),
        "sec_strengths": "03 已有基础",
        "kicker_strengths": "03 表现良好的部分",
        "h2_strengths": "现有基础",
        "dim_sec": "维度 {n:02d}",
        "dim_kicker": "维度 · {n:02d}",
        "engine_notes": "引擎备注",
        "how_to_improve": "改进建议",
        "sec_ia": "信息架构",
        "kicker_ia": "信息架构",
        "h2_ia": "现状与建议结构",
        "recommended_tree": "建议树",
        "page_briefs": "页面简报",
        "no_page_briefs": "暂无页面简报。",
        "sec_questions": "目标问题",
        "kicker_questions": "目标问题",
        "h2_questions": "站内支撑度",
        "th_hash": "#",
        "th_question": "问题",
        "th_intent": "意图",
        "th_support": "支撑度",
        "th_gaps": "缺口",
        "no_questions": "未记录目标问题。",
        "sec_ai": "AI 可见性",
        "kicker_ai": "AI / 搜索可见性",
        "h2_ai": "检索是否会露出官网？",
        "ai_note": "检查方法已标注。未编造任何引擎原话。",
        "th_method": "方法",
        "th_tools": "工具",
        "th_brand": "提及品牌？",
        "th_official": "引用官网？",
        "th_sources": "来源",
        "th_notes": "备注",
        "no_checks": "未附可见性检查。",
        "yes": "是",
        "no": "否",
        "sec_authority": "权威证据",
        "kicker_authority": "权威证据",
        "h2_authority": "建议在站内发布的内容",
        "th_evidence": "证据",
        "th_where": "目前所在",
        "th_action": "行动",
        "no_offsite": "无站外清单。",
        "sec_findings": "关键发现",
        "kicker_findings": "关键发现",
        "h2_findings": "需优先处理的问题",
        "see_dims": "详见各维度叙述。",
        "problem": "问题",
        "impact": "影响",
        "fix": "整改",
        "sec_actions": "优先行动",
        "kicker_actions": "优先行动",
        "h2_actions": "有序下一步",
        "sec_scope": "检测范围",
        "kicker_scope": "检测范围",
        "h2_scope": "本次评测覆盖范围",
        "fetch_mode": "抓取模式",
        "pages_analyzed_inline": "分析页数",
        "sample_urls": "抽样 URL",
        "conclusion": "结论",
        "sample_label": "样例",
        "outcome_label": "预期结果",
        "sec_timeline": "12 后续跟进",
        "kicker_timeline": "12 后续跟进",
        "h2_timeline": "有序下一步与时间表",
        "none": "—",
        "md_title": "{brand} — 内容 GEO 评测报告",
        "md_intro": (
            "本报告评估站点**内容**是否可被生成式引擎理解、信任与引用：信息架构、页面类型与缺口、"
            "写作质量、权威证据，以及对真实采购问题的覆盖（含标注方法的 AI / 搜索可见性检查）。"
            "**GEO = 生成式引擎优化**（网站），不是地理。"
        ),
        "md_h_overall": "## 1. 总体评价",
        "md_one_line": "> **一句话结论**：{closing}",
        "md_fetch": "**抓取披露**：{text}",
        "md_h_method": "## 2. 内容 GEO 评分方法",
        "md_method_body": (
            "五个维度合计 100 分。SEO 内容可发现性（标题、抓取路径、sitemap/robots 等发现辅助）"
            "计入技术 GEO 就绪报告，不在本报告。"
        ),
        "md_grade_scale": "等级刻度：A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D < 60 · F = 无法评测。",
        "md_h_strengths": "## 3. 表现良好的部分",
        "md_none_listed": "- _（暂无）_",
        "md_h_dims": "## 4. 分维度评估",
        "md_how": "**改进建议**：{text}",
        "md_h_ia": "## 5. 信息架构 — 现状与建议",
        "md_recommended_tree": "建议树：",
        "md_page_briefs": "### 待创建或升级的页面简报",
        "md_h_tax": "## 6. 内容分类与缺口",
        "md_page_type": "| 页面类型 | 样本中数量 |",
        "md_h_write": "## 7. 写作质量",
        "md_h_auth": "## 8. 权威与证据发布",
        "md_off_header": "| 证据 | 目前所在 | 行动 |",
        "md_h_tq": "## 9. 目标问题 × 站内支撑",
        "md_tq_header": "| # | 问题 | 意图 | 站内支撑（0–3） | 缺口 |",
        "md_no_tq": "_未记录目标问题。_",
        "md_h_ai": "## 10. 目标问题 × AI / 搜索可见性",
        "md_ai_intro": (
            "检查按方法标注。`web_retrieval_proxy` = 在无法使用 ChatGPT / Perplexity / Gemini "
            "产品界面时，用公开网页/搜索结果作为检索增强系统可能依据的代理。"
            "**未编造任何引擎原话。**"
        ),
        "md_constraint": "- 约束：{text}",
        "md_ai_header": (
            "| 问题 | 方法 | 引擎 / 工具 | 提及品牌？ | 引用官网？ | 见到的来源 | 备注 |"
        ),
        "md_no_ai": "_未附 AI/搜索可见性检查。_",
        "md_h_findings": "## 11. 关键发现",
        "md_problem": "**问题**：{text}",
        "md_impact": "**影响**：{text}",
        "md_fix": "**整改**：{text}",
        "md_evidence": "证据：",
        "md_see_dims": "_详见各维度叙述。_",
        "md_h_actions": "## 12. 优先行动",
        "md_h_scope": "## 13. 检测范围",
        "md_pages": "- 分析页数：{n}",
        "md_fetch_mode": "- 抓取模式：`{mode}`",
        "md_sample": "- 抽样 URL / 文件：{n}",
        "md_h_conclusion": "## 14. 结论",
        "md_prepared": "*Beansmile · GEO Checker 编制*",
        "md_pending": "_待充实。_",
        "md_total": "内容 GEO 总分",
        "unevaluable": "无法评测",
        "confidence_prefix": "置信度：",
    },
}


def prefer_zh_narrative(data: dict) -> dict:
    """Prefer Chinese narrative for --lang zh builds.

    Order of preference per field:
      1. Primary field already contains CJK → keep (agent enriched in Chinese).
      2. Else use parallel *_zh if present.
      3. Else keep English primary (chrome still Chinese).

    Agents running Chinese reports should write Chinese into primary fields
    (overall_summary, closing, dim narr/callout, findings, …), not only *_zh.
    """
    out = dict(data)
    narrative_keys = (
        "overall_summary",
        "closing",
        "fetch_disclosure",
        "scope_note",
        "current_ia_notes",
    )
    for k in narrative_keys:
        primary = out.get(k) or ""
        alt = out.get(f"{k}_zh") or ""
        if looks_cjk(primary):
            continue
        if alt:
            out[k] = alt

    dims = []
    for d in out.get("dimensions") or []:
        d = dict(d)
        for field in ("narr", "callout", "name"):
            primary = d.get(field) or ""
            alt = d.get(f"{field}_zh") or ""
            if looks_cjk(primary):
                continue
            if alt:
                d[field] = alt
        notes = d.get("notes") or []
        notes_zh = d.get("notes_zh") or []
        if notes_zh and not any(looks_cjk(n) for n in notes):
            d["notes"] = notes_zh
        dims.append(d)
    out["dimensions"] = dims

    # strengths / findings / priority_actions: swap list-level *_zh when primary looks EN
    for list_key in ("strengths", "findings", "priority_actions", "recommended_ia_tree", "page_briefs"):
        zh_key = f"{list_key}_zh"
        primary_list = out.get(list_key) or []
        alt_list = out.get(zh_key) or []
        if not alt_list:
            continue
        # If any string item in primary already CJK, keep primary
        sample = ""
        for item in primary_list[:3]:
            if isinstance(item, str):
                sample += item
            elif isinstance(item, dict):
                sample += " ".join(str(v) for v in item.values() if isinstance(v, str))
        if looks_cjk(sample):
            continue
        out[list_key] = alt_list

    return out


def render_md(data: dict, lang: str = "en") -> str:
    S = STRINGS[lang]
    brand = data.get("site_brand") or data.get("company_name") or data.get("domain") or "Website"
    domain = data.get("domain") or ""
    score = data.get("overall_score")
    grade = data.get("grade") or "—"
    conf = data.get("confidence") or ""
    score_line = (
        S["unevaluable"]
        if data.get("unevaluable") or score is None
        else f"**{format_score(score)} / 100 ({grade})**"
    )
    lines: list[str] = []
    lines.append(f"# {S['md_title'].format(brand=brand)}")
    lines.append("")
    conf_bit = f" · {S['confidence_prefix']}{conf}" if conf else ""
    lines.append(f"> **{domain}** · {(data.get('generated_at') or '')[:10]} · Content GEO {score_line}{conf_bit}")
    lines.append("")
    lines.append(S["md_intro"])
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_overall"])
    lines.append("")
    lines.append(data.get("overall_summary") or S["md_pending"])
    lines.append("")
    lines.append(S["md_one_line"].format(closing=data.get("closing") or S["none"]))
    lines.append("")
    if data.get("fetch_disclosure"):
        lines.append(S["md_fetch"].format(text=data["fetch_disclosure"]))
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_method"])
    lines.append("")
    lines.append(S["md_method_body"])
    lines.append("")
    lines.append(f"| {S['th_dimension']} | {S['th_score']} | {S['th_max']} | {S['th_grade']} |")
    lines.append("|---|---|---|---|")
    for d in data.get("dimensions") or []:
        lines.append(
            f"| {d.get('name')} | {format_score(d.get('score'))} | /{d.get('max')} | {d.get('grade')} |"
        )
    if score is not None:
        lines.append(f"| **{S['md_total']}** | **{format_score(score)}** | **/100** | {grade} |")
    lines.append("")
    lines.append(S["md_grade_scale"])
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_strengths"])
    lines.append("")
    strengths = data.get("strengths") or []
    if strengths:
        for s in strengths:
            lines.append(f"- {s}")
    else:
        lines.append(S["md_none_listed"])
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_dims"])
    lines.append("")
    for i, d in enumerate(data.get("dimensions") or [], 1):
        lines.append(f"### {i} · {d.get('name')} ({format_score(d.get('score'))} / {d.get('max')} · {d.get('grade')})")
        lines.append("")
        lines.append(d.get("narr") or " ".join(d.get("notes") or []) or S["none"])
        lines.append("")
        if d.get("callout"):
            lines.append(S["md_how"].format(text=d["callout"]))
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_ia"])
    lines.append("")
    if data.get("current_ia_notes"):
        lines.append(data["current_ia_notes"])
        lines.append("")
    ia = data.get("recommended_ia_tree") or []
    if ia:
        lines.append(S["md_recommended_tree"])
        lines.append("")
        for node in ia:
            if isinstance(node, str):
                lines.append(f"- {node}")
            else:
                lines.append(f"- **{node.get('section')}**: {node.get('detail', '')}")
        lines.append("")
    briefs = data.get("page_briefs") or []
    if briefs:
        lines.append(S["md_page_briefs"])
        lines.append("")
        for b in briefs:
            lines.append(f"#### {b.get('title') or b.get('path')}")
            lines.append("")
            lines.append(b.get("purpose") or "")
            lines.append("")
            for m in b.get("must_have") or []:
                lines.append(f"- {m}")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_tax"])
    lines.append("")
    tax = next(
        (d for d in (data.get("dimensions") or []) if d.get("id") == "C-TAX" or d.get("key") == "taxonomy_gaps"),
        None,
    )
    if tax and tax.get("narr"):
        lines.append(tax["narr"])
        lines.append("")
    counts = data.get("page_type_counts") or {}
    if counts:
        lines.append(S["md_page_type"])
        lines.append("|---|---|")
        for k, v in sorted(counts.items()):
            lines.append(f"| {k} | {v} |")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_write"])
    lines.append("")
    wr = next(
        (d for d in (data.get("dimensions") or []) if d.get("id") == "C-WRITE" or d.get("key") == "writing_quality"),
        None,
    )
    if wr:
        lines.append(wr.get("narr") or S["none"])
        lines.append("")
        if wr.get("callout"):
            lines.append(S["md_how"].format(text=wr["callout"]))
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_auth"])
    lines.append("")
    au = next(
        (d for d in (data.get("dimensions") or []) if d.get("id") == "C-AUTH" or d.get("key") == "authority_evidence"),
        None,
    )
    if au:
        lines.append(au.get("narr") or S["none"])
        lines.append("")
    off = data.get("offsite_evidence") or []
    if off:
        lines.append(S["md_off_header"])
        lines.append("|---|---|---|")
        for o in off:
            lines.append(
                f"| {o.get('title')} | {o.get('source_url') or o.get('where')} | {o.get('action')} |"
            )
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_tq"])
    lines.append("")
    tq = data.get("target_questions") or []
    if tq:
        lines.append(S["md_tq_header"])
        lines.append("|---|---|---|---|---|")
        for i, q in enumerate(tq, 1):
            gaps = "; ".join(q.get("knowledge_gaps") or []) or S["none"]
            lines.append(
                f"| {i} | {q.get('question')} | {q.get('intent')} | {q.get('on_site_support')} | {gaps} |"
            )
        lines.append("")
    else:
        lines.append(S["md_no_tq"])
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_ai"])
    lines.append("")
    lines.append(S["md_ai_intro"])
    lines.append("")
    for lim in data.get("ai_check_limits") or []:
        lines.append(S["md_constraint"].format(text=lim))
    if data.get("ai_check_limits"):
        lines.append("")
    checks = data.get("ai_checks") or []
    if checks:
        lines.append(S["md_ai_header"])
        lines.append("|---|---|---|---|---|---|---|")
        for c in checks:
            sources = "; ".join((c.get("sources_seen") or [])[:4]) or S["none"]
            lines.append(
                f"| {c.get('question')} | `{c.get('check_type')}` | {c.get('engines_or_methods')} | "
                f"{S['yes'] if c.get('mentioned_brand') else S['no']} | "
                f"{S['yes'] if c.get('cited_official_domain') else S['no']} | {sources} | "
                f"{(c.get('notes') or '')[:160]} |"
            )
        lines.append("")
        for c in checks:
            if c.get("answer_summary"):
                lines.append(f"- **{c.get('question')}** — {c['answer_summary']}")
        lines.append("")
    else:
        lines.append(S["md_no_ai"])
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_findings"])
    lines.append("")
    findings = data.get("findings") or []
    if findings:
        for i, f in enumerate(findings, 1):
            if isinstance(f, str):
                lines.append(f"### {i} · {f}")
                lines.append("")
            else:
                lines.append(f"### {i} · [{f.get('severity', 'medium')}] {f.get('title')}")
                lines.append("")
                lines.append(S["md_problem"].format(text=f.get("problem")))
                lines.append("")
                lines.append(S["md_impact"].format(text=f.get("impact")))
                lines.append("")
                lines.append(S["md_fix"].format(text=f.get("solution")))
                lines.append("")
                ev = f.get("evidence") or []
                if ev:
                    lines.append(S["md_evidence"])
                    for e in ev:
                        lines.append(f"- {e}")
                    lines.append("")
    else:
        lines.append(S["md_see_dims"])
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_actions"])
    lines.append("")
    for a in data.get("priority_actions") or []:
        if isinstance(a, str):
            lines.append(f"- {a}")
        else:
            lines.append(
                f"- **[{a.get('sev', 'P1')}] {a.get('action')}** ({a.get('owner', 'content')}) — {a.get('detail', '')}"
            )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_scope"])
    lines.append("")
    lines.append(data.get("scope_note") or "")
    lines.append("")
    lines.append(S["md_pages"].format(n=data.get("pages_analyzed")))
    lines.append(S["md_fetch_mode"].format(mode=data.get("fetch_mode")))
    lines.append(S["md_sample"].format(n=len(data.get("sample_urls") or [])))
    for u in (data.get("sample_urls") or [])[:24]:
        lines.append(f"  - {u}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_h_conclusion"])
    lines.append("")
    lines.append(data.get("closing") or S["none"])
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(S["md_prepared"])
    lines.append("")
    return "\n".join(lines)


def _synth_sample(action: dict, lang: str) -> str:
    """When enrichment omits sample, provide a structural example (not invented crawl quotes)."""
    if action.get("sample") or action.get("example"):
        return action.get("sample") or action.get("example") or ""
    title = (action.get("action") or action.get("title") or "").lower()
    blob = f"{title} {action.get('detail') or ''}".lower()
    if lang == "zh":
        if any(k in blob for k in ("https", "tls", "500", "抓取", "爬虫")):
            return "验收：curl -I https://example.com 返回 200；GSC「网址检查」可抓取；访问日志可见 Googlebot / OAI-SearchBot。"
        if any(k in blob for k in ("evergreen", "常青", "答案页", "采购")):
            return (
                "H1：如何选择适合园区的智慧灯杆？\n"
                "首段（先答）：优先核对供电方式、杆体承重、通信模块与本地标准，再比厂商交付周期。\n"
                "必备小节：选型清单表 · 模块/接口 · 案例数据 · FAQ · 询价 CTA"
            )
        if any(k in blob for k in ("case", "案例")):
            return (
                "标题：某某新区智慧灯杆项目\n"
                "结构：背景 → 方案模块 → 可量化结果（如故障率/节能%）→ 照片 → 可核验来源链接"
            )
        if any(k in blob for k in ("template", "产品", "specs", "规格")):
            return (
                "产品页骨架：\n"
                "H1（唯一）→ 一句话定位 → 规格表 → 模块/标准 → 下载资料 → 相关案例 → FAQ"
            )
        if any(k in blob for k in ("proof", "专利", "资质", "奖项")):
            return (
                "/proof/ 证明中心：奖项 | 专利 | 资质\n"
                "每条：名称 · 颁发方 · 日期 · 证书图/编号 · 来源 URL"
            )
        return (
            "改动要点：写清「改什么页面 / 改成什么样」。\n"
            "样例结构：原状 → 目标标题/H1 → 必备小节 → 验收标准"
        )
    if any(k in blob for k in ("https", "tls", "500", "crawl", "bot")):
        return "Acceptance: curl -I https://example.com returns 200; GSC URL Inspection succeeds; access logs show Googlebot / OAI-SearchBot."
    if any(k in blob for k in ("evergreen", "answer page", "buyer", "procurement", "losing")):
        return (
            "H1: How to choose a smart pole for campus roads?\n"
            "Lead (answer first): Check power, load rating, radio modules, and local standards before comparing lead times.\n"
            "Must-have: selection checklist table · modules/interfaces · case metrics · FAQ · inquiry CTA"
        )
    if any(k in blob for k in ("case", "project")):
        return (
            "Title: [District] smart-pole deployment\n"
            "Structure: context → solution modules → measurable outcomes → photos → source links"
        )
    if any(k in blob for k in ("template", "product", "specs", "modules")):
        return (
            "Product page skeleton:\n"
            "Unique H1 → one-line positioning → specs table → modules/standards → downloads → related cases → FAQ"
        )
    if any(k in blob for k in ("proof", "patent", "award", "qualification")):
        return (
            "/proof/ hub: Awards | Patents | Qualifications\n"
            "Each entry: name · issuer · date · certificate id/image · source URL"
        )
    return (
        "Change brief: which URL changes, and what good looks like.\n"
        "Sample shape: current state → target title/H1 → required sections → acceptance check"
    )



def render_html(data: dict, style_css: str, lang: str = "en") -> str:
    S = STRINGS[lang]
    brand = data.get("site_brand") or data.get("company_name") or data.get("domain") or "Website"
    domain = data.get("domain") or ""
    score = data.get("overall_score")
    grade = data.get("grade") or "—"
    conf = data.get("confidence") or "—"
    date = (data.get("generated_at") or datetime.now().isoformat())[:10]
    score_disp = "—" if score is None else format_score(score)
    _, c_class, g_class, bar = grade_meta(grade if score is not None else "F")
    pct = 0 if score is None else max(0, min(100, float(score)))

    dims = data.get("dimensions") or []
    dim_rows = "".join(
        f"<tr><td>{esc(d.get('name'))}</td><td class=\"num mono\">{esc(format_score(d.get('score')))}</td>"
        f"<td class=\"dim mono\">/{esc(str(d.get('max')))}</td>"
        f"<td class=\"dim mono r\">{esc(str(d.get('grade')))}</td></tr>"
        for d in dims
    )
    if score is not None:
        dim_rows += (
            f"<tr class=\"total\"><td>{esc(S['total_row'])}</td><td class=\"num mono\">{esc(format_score(score))}</td>"
            f"<td class=\"dim mono\">/100</td><td class=\"r\">{esc(str(grade))}</td></tr>"
        )

    dim_cards = ""
    for i, d in enumerate(dims, 1):
        ds = float(d.get("score") or 0)
        dm = float(d.get("max") or 1)
        dp = round(ds / dm * 100, 1) if dm else 0
        _, dc, dg, dbar = grade_meta(d.get("grade") or "D")
        notes_html = "".join(f"<li>{esc(n)}</li>" for n in (d.get("notes") or [])[:6])
        dim_cards += f"""
<section class="page" id="dim{i}">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['dim_sec'].format(n=i))}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['dim_kicker'].format(n=i))}</div>
    <h2>{esc(d.get('name'))}</h2></div>
    <div class="pmeta"><span class="scorechip {dc}"><b>{esc(format_score(d.get('score')))}</b>
    <span>/{esc(str(d.get('max')))}</span><em class="g {dg}">{esc(str(d.get('grade')))}</em></span></div></div>
  <div class="mini"><i style="width:{dp}%;background:{dbar}"></i></div>
  <div class="narr">{inline_md(d.get('narr') or '')}</div>
  {"<div class='sublab'>" + esc(S['engine_notes']) + "</div><ul class='plain'>" + notes_html + "</ul>" if notes_html else ""}
  {"<div class='callout'><b>" + esc(S['how_to_improve']) + "</b><p>" + inline_md(d.get('callout') or '') + "</p></div>" if d.get('callout') else ""}
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>"""

    strengths = "".join(f"<li>{esc(s)}</li>" for s in (data.get("strengths") or [])) or f"<li>{esc(S['none'])}</li>"

    ia_nodes = ""
    for node in data.get("recommended_ia_tree") or []:
        if isinstance(node, str):
            ia_nodes += f"<li>{esc(node)}</li>"
        else:
            ia_nodes += f"<li><b>{esc(node.get('section'))}</b> — {esc(node.get('detail', ''))}</li>"

    briefs_html = ""
    for b in data.get("page_briefs") or []:
        must = "".join(f"<li>{esc(m)}</li>" for m in (b.get("must_have") or []))
        briefs_html += f"""
<div class="frow"><div class="frow-h"><h4>{esc(b.get('title') or b.get('path'))}</h4></div>
<p class="fix">{esc(b.get('purpose') or '')}</p>
<ul class="plain">{must}</ul></div>"""

    tq_rows = ""
    for i, q in enumerate(data.get("target_questions") or [], 1):
        gaps = "; ".join(q.get("knowledge_gaps") or []) or S["none"]
        tq_rows += (
            f"<tr><td class=\"mono\">{i}</td><td>{esc(q.get('question'))}</td>"
            f"<td>{esc(q.get('intent'))}</td><td class=\"num mono\">{esc(str(q.get('on_site_support')))}</td>"
            f"<td>{esc(gaps)}</td></tr>"
        )

    ai_rows = ""
    for c in data.get("ai_checks") or []:
        sources = "; ".join((c.get("sources_seen") or [])[:3]) or S["none"]
        ai_rows += (
            f"<tr><td>{esc(c.get('question'))}</td><td><code>{esc(c.get('check_type'))}</code></td>"
            f"<td>{esc(c.get('engines_or_methods'))}</td>"
            f"<td>{esc(S['yes'] if c.get('mentioned_brand') else S['no'])}</td>"
            f"<td>{esc(S['yes'] if c.get('cited_official_domain') else S['no'])}</td>"
            f"<td>{esc(sources)}</td><td>{esc((c.get('notes') or '')[:140])}</td></tr>"
        )

    ai_limits = "".join(f"<li>{esc(x)}</li>" for x in (data.get("ai_check_limits") or []))

    off_rows = ""
    for o in data.get("offsite_evidence") or []:
        off_rows += (
            f"<tr><td>{esc(o.get('title'))}</td><td>{esc(o.get('source_url') or o.get('where'))}</td>"
            f"<td>{esc(o.get('action'))}</td></tr>"
        )

    findings_html = ""
    for i, f in enumerate(data.get("findings") or [], 1):
        if isinstance(f, str):
            findings_html += f"<div class='frow'><h4>{i} · {esc(f)}</h4></div>"
            continue
        sev = esc(f.get("severity") or "medium")

        def _ev_line(e):
            if isinstance(e, dict):
                return esc((e.get("quote") or e.get("url") or str(e))[:240])
            return esc(str(e))

        ev = "".join(f"<li>{_ev_line(e)}</li>" for e in (f.get("evidence") or []))
        findings_html += f"""
<div class="frow" id="f{i}">
  <div class="frow-h"><span class="sev sev-{sev}">{sev}</span><h4>{i} · {esc(f.get('title'))}</h4></div>
  <p><b>{esc(S['problem'])}</b>: {esc(f.get('problem'))}</p>
  <p><b>{esc(S['impact'])}</b>: {esc(f.get('impact'))}</p>
  <p class="fix"><b>{esc(S['fix'])}</b>: {esc(f.get('solution'))}</p>
  {"<ul class='plain'>" + ev + "</ul>" if ev else ""}
</div>"""

    actions_html = ""
    for a in data.get("priority_actions") or []:
        if isinstance(a, str):
            actions_html += f"<div class='arow'><div><h4>{esc(a)}</h4></div></div>"
            continue
        sample = _synth_sample(a, lang)
        outcome = a.get("outcome") or a.get("expected_outcome") or ""
        effort = a.get("effort_days")
        effort_html = (
            f"<span class='tl-dur-badge mono'>{esc(str(effort))}{(' 天' if lang=='zh' else 'd')}</span>"
            if effort not in (None, "") else ""
        )
        sample_html = (
            f"<div class='sample-block'><span class='sample-label mono'>{esc(S['sample_label'])}</span>"
            f"<pre>{esc(sample)}</pre></div>"
            if sample else ""
        )
        outcome_html = (
            f"<p><b>{esc(S['outcome_label'])}</b>: {esc(outcome)}</p>" if outcome else ""
        )
        actions_html += (
            f"<div class='arow'><div><h4>[{esc(a.get('sev','P1'))}] {esc(a.get('action') or a.get('title') or '')}</h4>"
            f"<p>{esc(a.get('detail',''))}</p>{outcome_html}{sample_html}</div>"
            f"<span class='owner owner-info'>{esc(a.get('owner','content'))}</span>{effort_html}</div>"
        )

    _tl_actions = []
    for a in data.get("priority_actions") or []:
        if isinstance(a, str):
            _tl_actions.append({"title": a, "sample": ""})
        else:
            _tl_actions.append({
                "title": a.get("action") or a.get("title") or "",
                "detail": a.get("detail") or "",
                "owner": a.get("owner") or "",
                "sev": a.get("sev") or "",
                "sample": _synth_sample(a, lang),
                "effort_days": a.get("effort_days"),
                "outcome": a.get("outcome") or a.get("expected_outcome") or "",
            })
    timeline_html = render_timeline_block(
        _tl_actions,
        lang=lang,
        page_count=data.get("pages_analyzed"),
        include_retest=True,
        show_samples=True,
        limit=10,
    )

    sample = "".join(f"<li class='mono'>{esc(u)}</li>" for u in (data.get("sample_urls") or [])[:24])
    none_li = f"<li>{esc(S['none'])}</li>"

    return f"""<!doctype html><html lang="{esc(S['html_lang'])}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(brand)} {esc(S['title_suffix'])} · {esc(domain)}</title>
<meta name="description" content="{esc(S['meta_desc'].format(domain=domain, score=score_disp, grade=grade))}">
<style>{style_css}
/* Content GEO extras on shared technical stylesheet */
.page {{ min-height: auto; padding-bottom: 2rem; }}
.deck {{ max-width: 920px; margin: 0 auto; }}
.sev {{ display:inline-block; font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; padding:2px 8px; border-radius:999px; background:#eee; }}
.sev-critical {{ background:#fee2e2; color:#991b1b; }}
.sev-high {{ background:#ffedd5; color:#9a3412; }}
.sev-medium {{ background:#e0e7ff; color:#3730a3; }}
.sev-low {{ background:#ecfdf5; color:#065f46; }}
</style></head><body>
<div class="topbar"><div class="topbar-in">
  <span class="brand"><b>GEO Checker</b></span>
  <span class="doc">{esc(S['topbar_doc'].format(brand=brand, domain=domain))}</span>
  <span class="right"><span class="now mono">{esc(date)}</span></span>
</div><div class="progress"><i style="width:{pct}%"></i></div></div>

<div class="deck">

<section class="page page-dark cover" id="cover">
  <div class="cover-top"><span class="brand"><b>GEO Checker</b></span>
    <span class="cover-no mono">{esc(S['cover_no'])}</span></div>
  <div class="cover-mid">
    <div class="pkicker light">{esc(S['cover_kicker'])}</div>
    <h1>{esc(brand)}<br>{esc(S['cover_h1'])}</h1>
    <p class="cover-sub">{esc(S['cover_sub'])}</p>
    <div class="cover-score"><div class="cbig">{esc(score_disp)}<small>/100</small><em>{esc(S['cover_score_em'].format(grade=grade))}</em></div>
    <div><div class="cmeter"><div class="cm-track"><span class="cm-fill" style="width:{pct}%"></span></div>
    <div class="cm-scale"><span>0</span><span>{esc(S['pass_label'])}</span><span>{esc(S['good_label'])}</span><span>100</span></div></div>
    <p class="cover-score-note">{esc(S['cover_score_note'].format(conf=conf))}</p></div></div>
  </div>
  <dl class="cover-facts">
    <div class="wide"><dt>{esc(S['site'])}</dt><dd class="mono">{esc(data.get('site_url') or domain)}</dd></div>
    <div><dt>{esc(S['report_date'])}</dt><dd class="mono">{esc(date)}</dd></div>
    <div><dt>{esc(S['pages_analyzed'])}</dt><dd>{esc(str(data.get('pages_analyzed') or S['none']))}</dd></div>
    <div><dt>{esc(S['grade_scale'])}</dt><dd class="mono">{S['grade_scale_value']}</dd></div>
  </dl>
  <div class="cover-sign"><span>{esc(S['prepared_by'])}</span></div>
</section>

<section class="page" id="overall">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_overall'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_overall'])}</div>
    <h2>{esc(S['h2_overall'].format(score=score_disp, grade=grade))}</h2></div>
    <div class="pmeta"><span class="scorechip {c_class}"><b>{esc(score_disp)}</b><span>/100</span></span></div></div>
  <div class="narr lead">{inline_md(data.get('overall_summary') or '')}</div>
  {"<p class='note'><b>" + esc(S['fetch_disclosure']) + "</b>: " + esc(data.get('fetch_disclosure') or '') + "</p>" if data.get('fetch_disclosure') else ""}
  <div class="callout"><b>{esc(S['one_line'])}</b><p>{inline_md(data.get('closing') or '')}</p></div>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="method">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_method'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_method'])}</div>
    <h2>{esc(S['h2_method'])}</h2></div></div>
  <p class="narr">{esc(S['method_body'])}</p>
  <table class="mtable"><thead><tr><th>{esc(S['th_dimension'])}</th><th>{esc(S['th_score'])}</th><th>{esc(S['th_max'])}</th><th class="r">{esc(S['th_grade'])}</th></tr></thead>
  <tbody>{dim_rows}</tbody></table>
  <p class="note">{S['grade_note']}</p>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="strengths">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_strengths'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_strengths'])}</div><h2>{esc(S['h2_strengths'])}</h2></div></div>
  <ul class="plain">{strengths}</ul>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

{dim_cards}

<section class="page" id="ia">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_ia'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_ia'])}</div>
    <h2>{esc(S['h2_ia'])}</h2></div></div>
  <p class="narr">{inline_md(data.get('current_ia_notes') or '')}</p>
  <div class="sublab">{esc(S['recommended_tree'])}</div>
  <ul class="plain">{ia_nodes or none_li}</ul>
  <div class="sublab">{esc(S['page_briefs'])}</div>
  {briefs_html or '<p class="note">' + esc(S['no_page_briefs']) + '</p>'}
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="questions">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_questions'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_questions'])}</div>
    <h2>{esc(S['h2_questions'])}</h2></div></div>
  <table class="mtable"><thead><tr><th>{esc(S['th_hash'])}</th><th>{esc(S['th_question'])}</th><th>{esc(S['th_intent'])}</th><th>{esc(S['th_support'])}</th><th>{esc(S['th_gaps'])}</th></tr></thead>
  <tbody>{tq_rows or '<tr><td colspan="5">' + esc(S['no_questions']) + '</td></tr>'}</tbody></table>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="ai">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_ai'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_ai'])}</div>
    <h2>{esc(S['h2_ai'])}</h2></div></div>
  <p class="note">{esc(S['ai_note'])}</p>
  {"<ul class='plain'>" + ai_limits + "</ul>" if ai_limits else ""}
  <table class="mtable"><thead><tr><th>{esc(S['th_question'])}</th><th>{esc(S['th_method'])}</th><th>{esc(S['th_tools'])}</th><th>{esc(S['th_brand'])}</th><th>{esc(S['th_official'])}</th><th>{esc(S['th_sources'])}</th><th>{esc(S['th_notes'])}</th></tr></thead>
  <tbody>{ai_rows or '<tr><td colspan="7">' + esc(S['no_checks']) + '</td></tr>'}</tbody></table>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="evidence">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_authority'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_authority'])}</div>
    <h2>{esc(S['h2_authority'])}</h2></div></div>
  <table class="mtable"><thead><tr><th>{esc(S['th_evidence'])}</th><th>{esc(S['th_where'])}</th><th>{esc(S['th_action'])}</th></tr></thead>
  <tbody>{off_rows or '<tr><td colspan="3">' + esc(S['no_offsite']) + '</td></tr>'}</tbody></table>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="findings">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_findings'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_findings'])}</div><h2>{esc(S['h2_findings'])}</h2></div></div>
  {findings_html or '<p class="note">' + esc(S['see_dims']) + '</p>'}
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="actions">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_actions'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_actions'])}</div><h2>{esc(S['h2_actions'])}</h2></div></div>
  <div class="actions">{actions_html or '<p class="note">' + esc(S['none']) + '</p>'}</div>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="followup">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_timeline'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_timeline'])}</div><h2>{esc(S['h2_timeline'])}</h2></div></div>
  {timeline_html}
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="scope">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">{esc(S['sec_scope'])}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['kicker_scope'])}</div><h2>{esc(S['h2_scope'])}</h2></div></div>
  <p class="narr">{inline_md(data.get('scope_note') or '')}</p>
  <p class="note">{esc(S['fetch_mode'])}: <code>{esc(data.get('fetch_mode') or '')}</code> · {esc(S['pages_analyzed_inline'])}: {esc(str(data.get('pages_analyzed') or S['none']))}</p>
  <div class="sublab">{esc(S['sample_urls'])}</div>
  <ul class="plain">{sample or none_li}</ul>
  <div class="callout"><b>{esc(S['conclusion'])}</b><p>{inline_md(data.get('closing') or '')}</p></div>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

</div>
<p class="docfoot">{esc(S['docfoot'])}</p>
</body></html>
"""


def main():
    if len(sys.argv) < 2:
        print("Usage: build_content_report.py <run_dir> [--lang en|zh] [--also-md]")
        sys.exit(2)
    run_dir = sys.argv[1]
    lang = "en"
    if "--lang" in sys.argv:
        lang = sys.argv[sys.argv.index("--lang") + 1]
    if lang not in STRINGS:
        print(f"[build_content_report] unknown lang {lang!r}, choose from {sorted(STRINGS)}")
        sys.exit(2)

    data = load_report(run_dir)
    rp = os.path.join(run_dir, "content_report.json")
    if os.path.isfile(rp):
        data = json.load(open(rp, encoding="utf-8"))

    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    style_path = os.path.join(skill_root, "report_templates", "style.css")
    style = open(style_path, encoding="utf-8").read() if os.path.isfile(style_path) else ""

    out_dir = os.path.join(run_dir, "report")
    os.makedirs(out_dir, exist_ok=True)

    if lang == "zh":
        data = prefer_zh_narrative(data)

    stem = "内容报告" if lang == "zh" else "Content_Report"
    html_path = os.path.join(out_dir, f"{stem}.html")
    open(html_path, "w", encoding="utf-8").write(render_html(data, style, lang=lang))
    print(f"Wrote {html_path}")

    if "--also-md" in sys.argv:
        md = render_md(data, lang=lang)
        md_path = os.path.join(out_dir, f"{stem}.md")
        open(md_path, "w", encoding="utf-8").write(md)
        print(f"Wrote {md_path} (--also-md)")


if __name__ == "__main__":
    main()
