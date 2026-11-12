#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a combined GEO Checker HTML report from technical + content packages.

Usage:
    python3 scripts/build_combined_report.py <tech_run_dir> [--content-run <content_run_dir>]
        [--lang en|zh] [--out-dir <dir>] [--brand NAME]

Defaults:
  - Content JSON is read from the same run dir if present, else --content-run is required.
  - Writes report/Combined_Report.html (or 综合报告.html when --lang zh).
  - Also writes a sidecar JSON (Combined_Report.json / 综合报告.json) with the
    published combined score and gate flags.

The two component scores stay independent and visible (technical /100,
Content GEO /100). A third combined /100 may be shown using technical 40%
+ content 60%, plus an access gate. Never replace the two component scores.
Never invent a combined score when either side is missing. Never invent AI
engine quotes. Never show scoring / rules / rubric version numbers.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse

try:
    from timeline_ui import render_timeline_block
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from timeline_ui import render_timeline_block

from combined_score import (
    CONTENT_WEIGHT,
    TECH_WEIGHT,
    format_score,
    score_from_reports,
)


def esc(s: str) -> str:
    return html_mod.escape(s or "", quote=False)


def inline_md(s: str) -> str:
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = s.replace("\n", "<br>")
    return s


def strip_html_tags(s: str) -> str:
    """Flatten tech summaries that may contain <strong>/<br> for plain highlights."""
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def grade_meta(grade: str):
    g = (grade or "D").upper()
    if g in ("A+", "A"):
        return "#059669", "c-a", "g-a", "var(--success)"
    if g == "B":
        return "#2563eb", "c-b", "g-b", "var(--info)"
    if g == "C":
        return "#d97706", "c-c", "g-c", "var(--warning)"
    if g == "F":
        return "#dc2626", "c-d", "g-d", "var(--danger)"
    return "#dc2626", "c-d", "g-d", "var(--danger)"


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_tech_report(run_dir: str) -> dict:
    for name in ("report.json", "report.engine.json"):
        p = os.path.join(run_dir, name)
        if os.path.isfile(p):
            return load_json(p)
    raise FileNotFoundError(f"No technical report.json under {run_dir}")


def find_content_report(run_dir: str, lang: str) -> dict:
    candidates = []
    if lang == "zh":
        candidates.append("content_report.zh.json")
    candidates.extend(["content_report.json", "content.engine.json"])
    for name in candidates:
        p = os.path.join(run_dir, name)
        if os.path.isfile(p):
            data = load_json(p)
            if lang == "zh":
                data = apply_zh_fields(data)
            return data
    raise FileNotFoundError(f"No content_report.json under {run_dir}")


def apply_zh_fields(data: dict) -> dict:
    data = dict(data)
    for k in ("overall_summary", "closing", "fetch_disclosure", "scope_note", "current_ia_notes"):
        zk = f"{k}_zh"
        if data.get(zk):
            data[k] = data[zk]
    return data


CONTENT_DIM_NAMES = {
    "en": {
        "information_architecture": "Information architecture",
        "taxonomy_gaps": "Content taxonomy & gaps",
        "writing_quality": "Writing quality",
        "authority_evidence": "Authority & evidence publishing",
        "query_coverage": "Target query coverage",
    },
    "zh": {
        "information_architecture": "信息架构",
        "taxonomy_gaps": "分类与缺口",
        "writing_quality": "写作质量",
        "authority_evidence": "权威与证据",
        "query_coverage": "采购问题覆盖",
    },
}


def content_dim_name(dim: dict, lang: str) -> str:
    key = dim.get("key") or ""
    if lang == "zh":
        if dim.get("name_zh"):
            return dim["name_zh"]
        if key in CONTENT_DIM_NAMES["zh"]:
            return CONTENT_DIM_NAMES["zh"][key]
    if key in CONTENT_DIM_NAMES.get(lang, {}):
        return CONTENT_DIM_NAMES[lang][key]
    return dim.get("name") or key or "—"


SOURCES = [
    {
        "title_zh": "AI Features and Your Website（AI 功能与您的网站）",
        "title_en": "AI Features and Your Website",
        "meta_zh": "Google Search Central，更新于 2025-12-10 UTC",
        "meta_en": "Google Search Central, last updated 2025-12-10 UTC",
        "url": "https://developers.google.com/search/docs/appearance/ai-features",
    },
    {
        "title_zh": "Top ways to ensure your content performs well in Google’s AI experiences on Search（让内容在 Google AI 搜索体验中表现更好的主要方法）",
        "title_en": "Top ways to ensure your content performs well in Google’s AI experiences on Search",
        "meta_zh": "Google Search Central 博文，John Mueller，2025-05-21",
        "meta_en": "Google Search Central Blog, John Mueller, May 21, 2025",
        "url": "https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search",
    },
    {
        "title_zh": "Optimizing your website for generative AI features on Google Search（针对 Google 搜索生成式 AI 功能优化网站）",
        "title_en": "Optimizing your website for generative AI features on Google Search",
        "meta_zh": "Google Search Central，更新于 2026-07-10 UTC",
        "meta_en": "Google Search Central, last updated 2026-07-10 UTC",
        "url": "https://developers.google.com/search/docs/fundamentals/ai-optimization-guide",
    },
    {
        "title_zh": "Creating helpful, reliable, people-first content（创造有帮助、可靠、以人为本的内容）",
        "title_en": "Creating helpful, reliable, people-first content",
        "meta_zh": "Google Search Central",
        "meta_en": "Google Search Central",
        "url": "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
    },
    {
        "title_zh": "Google Search Essentials（搜索要点）",
        "title_en": "Google Search Essentials",
        "meta_zh": "Google Search Central",
        "meta_en": "Google Search Central",
        "url": "https://developers.google.com/search/docs/essentials",
    },
    {
        "title_zh": "Google Search technical requirements（搜索技术要求）",
        "title_en": "Google Search technical requirements",
        "meta_zh": "Google Search Central",
        "meta_en": "Google Search Central",
        "url": "https://developers.google.com/search/docs/essentials/technical",
    },
    {
        "title_zh": "Overview of OpenAI Crawlers（OpenAI 爬虫概览：OAI-SearchBot、GPTBot、ChatGPT-User）",
        "title_en": "Overview of OpenAI Crawlers (OAI-SearchBot, GPTBot, ChatGPT-User)",
        "meta_zh": "OpenAI 开发者文档",
        "meta_en": "OpenAI developer documentation",
        "url": "https://developers.openai.com/api/docs/bots",
    },
    {
        "title_zh": "Searching the web with ChatGPT（使用 ChatGPT 搜索网页：资格条件与「相关、可靠」，位置不保证）",
        "title_en": "Searching the web with ChatGPT (eligibility; relevant, reliable information; placement not guaranteed)",
        "meta_zh": "OpenAI 帮助中心",
        "meta_en": "OpenAI Help Center",
        "url": "https://help.openai.com/en/articles/9237897-searching-the-web-with-chatgpt",
    },
    {
        "title_zh": "Does Anthropic crawl data from the web, and how can site owners block the crawler?（Anthropic 如何抓取网页，以及站长如何管理爬虫：Claude-SearchBot、Claude-User、ClaudeBot）",
        "title_en": "Does Anthropic crawl data from the web, and how can site owners block the crawler?",
        "meta_zh": "Claude 帮助中心",
        "meta_en": "Claude Help Center",
        "url": "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler",
    },
    {
        "title_zh": "Meta Web Crawlers（Meta 网页爬虫：Meta-WebIndexer、Meta-ExternalAgent 等）",
        "title_en": "Meta Web Crawlers",
        "meta_zh": "Meta for Developers",
        "meta_en": "Meta for Developers",
        "url": "https://developers.facebook.com/docs/sharing/webmasters/web-crawlers",
    },
    {
        "title_zh": "Kimi Crawlers（Kimi 爬虫：Kimi-SearchBot、Kimi-User、KimiBot）",
        "title_en": "Kimi Crawlers (Kimi-SearchBot, Kimi-User, KimiBot)",
        "meta_zh": "Kimi / 月之暗面官方政策",
        "meta_en": "Kimi / Moonshot official policy",
        "url": "https://www.kimi.com/policies/kimi-crawlers",
    },
    {
        "title_zh": "GEO: Generative Engine Optimization（生成式引擎优化），KDD 2024。Aggarwal、Murahari、Rajpurohit、Kalyan、Narasimhan、Deshpande。同行评审论文。",
        "title_en": "GEO: Generative Engine Optimization. Aggarwal, Murahari, Rajpurohit, Kalyan, Narasimhan, Deshpande. KDD 2024. Peer-reviewed.",
        "meta_zh": "DOI 10.1145/3637528.3671900；预印本 arXiv:2311.09735",
        "meta_en": "DOI 10.1145/3637528.3671900; preprint arXiv:2311.09735",
        "url": "https://doi.org/10.1145/3637528.3671900",
        "url_alt": "https://arxiv.org/abs/2311.09735",
        "url_alt_label_zh": "arXiv 预印本",
        "url_alt_label_en": "arXiv preprint",
    },
]


STRINGS = {
    "en": {
        "html_lang": "en",
        "doc_title": "Combined GEO Report",
        "cover_kicker": "Generative Engine Optimization · Combined package",
        "cover_h1": "Combined GEO Report",
        "cover_sub": (
            "This package brings together the technical on-site readiness evaluation "
            "(10 dimensions /100, including SEO content discoverability) and the Content GEO evaluation "
            "(architecture, taxonomy, writing, authority evidence, buyer-question coverage). "
            "The two component scores stay independent; the combined score is a third headline number."
        ),
        "site": "Site",
        "report_date": "Report date",
        "tech_label": "Technical readiness",
        "seo_label": "SEO discoverability",
        "content_label": "Content GEO",
        "combined_label": "Combined score",
        "combined_label_sampled": "Sampled-pages combined score",
        "cover_tech_note": "SEO dim included in technical /100",
        "tech_card_sub": "10 dimensions · incl. SEO /15 · weight 40%",
        "content_card_sub": "5 dimensions · weight 60%",
        "combined_card_sub": "Technical 40% + Content 60%, then an access gate",
        "weights_line": "Weights: content 60% · technical 40%",
        "gate_off": "Access gate not applied",
        "gate_hard": "Access gate applied: combined score capped at 30",
        "gate_soft": "Access gate applied: combined score capped at 50",
        "cover_what": (
            "This is an on-site readiness combined score, not a citation rate, "
            "mention rate, ranking, or traffic forecast."
        ),
        "grade_scale": "Grade scale",
        "grade_scale_value": "A+≥90 · A≥80 · B≥70 · C≥60 · D&lt;60",
        "pass_label": "Pass 60",
        "good_label": "Good 80",
        "prepared_by": "Prepared by Beansmile · GEO Checker",
        "sample_size": "Sample size",
        "obs_mode": "Observation mode",
        "obs_raw": "Raw HTML (not rendered DOM)",
        "pages_unit": "pages",
        "tech_pages": "technical",
        "content_pages": "content",
        "confidence": "Confidence",
        "intro_kicker": "01 Combined conclusion",
        "intro_h2": "What this combined score means",
        "intro_lead": (
            "The combined score is an executive headline for on-site readiness: "
            "technical readiness contributes 40%, Content GEO contributes 60%, and an access "
            "gate may cap the result when search indexing or on-demand crawlers are blocked. "
            "It is <strong>not</strong> a citation rate, mention rate, share of voice, ranking, "
            "or traffic prediction, and it does not guarantee that a generative engine will cite this site."
        ),
        "intro_this_score": (
            "This site’s {label} is {score}/100 ({grade}). Technical readiness is {tech}/100 ({tech_grade}); "
            "Content GEO is {content}/100 ({content_grade}). {gate}"
        ),
        "intro_tech": "Technical track",
        "intro_content": "Content track",
        "intro_priority": "What to do first",
        "intro_overlap": (
            "Thin or hard-to-extract HTML shows up in both the technical absorption dimension "
            "and the content writing dimension. This combined score uses the two existing totals "
            "as-is and does not deduplicate that overlap."
        ),
        "scores_kicker": "02 Score composition",
        "scores_h2": "How the combined score is calculated",
        "scores_note": (
            "The two component scores remain independent and are still shown in full. "
            "The combined score is a third headline: it weights the displayed technical overall "
            "at 40% and the displayed Content GEO overall at 60%, then applies an access gate. "
            "It is not a third independent rubric, and it does not average the two scores as 50/50."
        ),
        "formula_label": "Formula used in this report",
        "formula_text": "Combined = clamp(0, 100, snap-to-0.5(0.40 × technical + 0.60 × content))",
        "formula_this": (
            "This run: 0.40 × {tech} + 0.60 × {content}, then snapped to a 0 or 0.5 increment, "
            "gives a combined score of {combined} ({grade}). {gate}"
        ),
        "formula_missing": (
            "A combined score is not published because one of the two component scores is missing."
        ),
        "narrative_kicker": "How to read the 40/60 contract",
        "layer1_lead": "Layer 1 — Technical discoverability is a prerequisite for content to be considered.",
        "layer1_body": (
            "This maps to the access gate, and to keeping a 40% technical weight. "
            "Google states that a page must already be indexed and meet Search technical requirements "
            "to be eligible to appear as a supporting link in AI Overviews or AI Mode; meeting those "
            "technical requirements also applies to AI formats. Official documentation from OpenAI, "
            "Anthropic, Meta, and Kimi independently supports this access-eligibility layer: allowing "
            "each vendor’s search crawler is described as a prerequisite for appearing in that vendor’s "
            "search results or being cited. Training-crawler blocks (for example GPTBot, ClaudeBot, "
            "or KimiBot) do not trigger this gate, which is consistent with those vendors’ practice of "
            "keeping training and search settings independent."
        ),
        "layer2_lead": "Layer 2 — Once a site is accessible, differentiation is in the content.",
        "layer2_body": (
            "This maps to a 60% content weight. Google is currently the only major vendor that "
            "explicitly says creating unique, useful content will, over time, likely influence a site’s "
            "presence in generative AI search more than the other suggestions in its guide. The KDD 2024 "
            "paper “GEO: Generative Engine Optimization” found that content-side methods (such as adding "
            "statistics, quotations, and citations) can improve visibility in generative-engine answers "
            "once a source has already been retrieved. OpenAI only says that ranking uses multiple factors "
            "to help users find “relevant, reliable information,” and that placement is not guaranteed — "
            "that must not be stretched into a claim that OpenAI also says content weighs more than technical access."
        ),
        "layer3_lead": "Layer 3 — 40/60 is our product contract, not a percentage any vendor published.",
        "layer3_body": (
            "We do not use 50/50, because that would treat “whether a page can be considered” as equal "
            "to “what wins after it is considered,” which would sit poorly with Google’s statement that "
            "content is likely to matter more. We do not use 30/70, because our technical 100 already "
            "includes discoverability, HTML absorption, and page quality; lowering the technical weight "
            "further would understate extractability barriers that are real on JavaScript-heavy sites. "
            "Vendor statements apply only to that vendor’s own product. The paper’s observation that "
            "content-side methods can boost visibility by up to 40% is an experimental result; it is "
            "not the same thing as our 40% technical weight, and it is not a citation-rate promise."
        ),
        "max": "Max",
        "grade": "Grade",
        "track": "Track",
        "score": "Score",
        "weight": "Weight",
        "tech_kicker": "03 Technical summary",
        "tech_h2": "On-site readiness (incl. SEO discoverability)",
        "tech_nine": "Ten-dimension readiness",
        "tech_seo": "SEO content discoverability (15 pts of the technical 100)",
        "provisional": "Provisional / crawl limited",
        "strengths": "Strengths",
        "key_findings": "Key findings",
        "see_full_tech": "The full evidence chain remains in the standalone technical HTML report.",
        "content_kicker": "04 Content summary",
        "content_h2": "Architecture, writing, evidence & questions",
        "dimensions": "Dimensions",
        "see_full_content": "The full evidence chain remains in the standalone Content GEO HTML report.",
        "shared_kicker": "05 Shared findings",
        "shared_h2": "Issues that span both tracks",
        "shared_note": (
            "The same root cause is written once here, with a note on which tracks it affects. "
            "Technical absorption and content writing can both flag extractable-body gaps; "
            "that overlap is disclosed, not deducted twice out of the combined score."
        ),
        "timeline_kicker": "06 Priority actions & effort",
        "timeline_h2": "Unified next steps and an effort-based timeline",
        "timeline_intro": (
            "Durations come from this run’s findings and priority actions — not a fixed "
            "multi-week calendar. HTTPS/crawl restores are same-day work; content builds take longer. "
            "Adjust owners and overlap to your capacity; finish with a same-sample re-test. "
            "These items describe a direction of improvement; they do not promise that the combined "
            "score will reach a stated target."
        ),
        "actions_h3": "Priority actions from both tracks",
        "priority": "Priority",
        "action": "Action",
        "owner": "Owner",
        "effort": "Effort",
        "outcome": "Acceptance / expected outcome",
        "days_unit": "days",
        "scope_kicker": "07 Scope & disclosure",
        "scope_h2": "What was evaluated",
        "scope_overlap": (
            "The combined score is a composite of the two existing headline totals. "
            "It does not deduplicate overlap between technical absorption and content writing, "
            "or between entity and authority evidence."
        ),
        "scope_excluded": (
            "Not included in the combined score: mention rate, citation rate, share of voice; "
            "llms.txt and other experimental conventions; training-crawler status; off-site brand monitoring."
        ),
        "scope_absent": "“Not seen in scope” does not mean the type is absent from the entire site.",
        "unevaluated": "Types unevaluated or not seen in scope",
        "fetch_disclosure": "Fetch disclosure",
        "closing_kicker": "08 Closing",
        "closing_h2": "Closing",
        "closing_template": (
            "The combined judgment is a {label} of {score}/100 ({grade}). {gate} "
            "First action: {first} "
            "We recommend re-testing against the same sample URLs. "
            "This score does not represent rankings, traffic, or a guarantee of AI citation."
        ),
        "refs_kicker": "09 Sources",
        "refs_h2": "Reference sources",
        "refs_disclaimer": (
            "The following materials are cited to explain the scoring principles. "
            "They do not mean that these organizations published or endorse this report’s "
            "specific scores or weights. Each vendor’s statements apply only to that vendor’s "
            "own products. Apart from Google, the vendor documents below mainly describe "
            "access and display prerequisites and do not publish a content-versus-technical split. "
            "Academic findings are experimental observations, not a citation-rate promise."
        ),
        "none": "—",
        "problem": "Problem",
        "impact": "Impact",
        "fix": "Fix",
        "footer": "GEO Checker · Combined package",
        "docfoot": (
            "Combined GEO package by Beansmile · GEO Checker. "
            "Technical /100 and Content GEO /100 stay independent; the combined /100 is a third "
            "headline (content 60%, technical 40%, plus an access gate). "
            "Not rankings, traffic, or guaranteed AI mentions."
        ),
        "alt_link": "preprint",
    },
    "zh": {
        "html_lang": "zh-CN",
        "doc_title": "GEO 综合评测报告",
        "cover_kicker": "生成式引擎优化 · 综合包",
        "cover_h1": "GEO 综合评测报告",
        "cover_sub": (
            "本综合包汇总技术侧站内就绪评测（十维 /100，含 SEO 内容可发现性）与内容侧 Content GEO 评测"
            "（信息架构、分类与缺口、编写质量、权威证据、采购问题覆盖）。"
            "技术分与内容分仍独立保留，综合分是第三个头条数。"
        ),
        "site": "站点",
        "report_date": "报告日期",
        "tech_label": "技术就绪度",
        "seo_label": "SEO 可发现性",
        "content_label": "内容 GEO",
        "combined_label": "综合分",
        "combined_label_sampled": "抽样页综合分",
        "cover_tech_note": "SEO 维已计入技术 /100",
        "tech_card_sub": "十维 · 含 SEO /15 · 权重 40%",
        "content_card_sub": "五维 · 权重 60%",
        "combined_card_sub": "技术 40% + 内容 60%，再视访问门槛封顶",
        "weights_line": "权重：内容 60% · 技术 40%",
        "gate_off": "访问门槛未生效",
        "gate_hard": "访问门槛已生效：综合分上限 30",
        "gate_soft": "访问门槛已生效：综合分上限 50",
        "cover_what": "这是站内准备度综合分，不是引用率、提及率、排名或流量预测。",
        "grade_scale": "等级刻度",
        "grade_scale_value": "A+≥90 · A≥80 · B≥70 · C≥60 · D&lt;60",
        "pass_label": "及格 60",
        "good_label": "良好 80",
        "prepared_by": "Beansmile · GEO Checker 编制",
        "sample_size": "抽样规模",
        "obs_mode": "观察模式",
        "obs_raw": "原始 HTML（非渲染 DOM）",
        "pages_unit": "页",
        "tech_pages": "技术",
        "content_pages": "内容",
        "confidence": "置信度",
        "intro_kicker": "01 综合结论",
        "intro_h2": "综合分是什么、本站卡在哪里",
        "intro_lead": (
            "本报告的综合分是站内准备度的管理头条：技术就绪度占 40%，内容 GEO 占 60%，"
            "若搜索索引或按需抓取爬虫被拦截，再用访问门槛对综合分设上限。"
            "它<strong>不是</strong>引用率、提及率、声量、排名或流量预测，也不保证生成式引擎会引用本站。"
        ),
        "intro_this_score": (
            "本站{label}为 {score} 分（{grade} 级）。技术就绪度 {tech}/100（{tech_grade}），"
            "内容 GEO {content}/100（{content_grade}）。{gate}"
        ),
        "intro_tech": "技术侧",
        "intro_content": "内容侧",
        "intro_priority": "建议先做的一条线",
        "intro_overlap": (
            "可抽取正文不足会同时出现在技术吸收维与内容写作维。综合分直接使用两侧已有总分，"
            "不对这一重叠做去重折算。"
        ),
        "scores_kicker": "02 分数构成",
        "scores_h2": "综合分如何计算",
        "scores_note": (
            "技术 /100 与内容 GEO /100 仍独立保留，并在本页完整展示。"
            "综合分是第三个头条数：先按展示中的技术总分 40%、内容总分 60% 加权，再视访问门槛封顶。"
            "它不是第三套独立打分，也不是把两项按 50/50 平均。"
        ),
        "formula_label": "本报告采用的算式",
        "formula_text": "综合分 = clamp(0, 100, 按 0.5 分档(0.40 × 技术分 + 0.60 × 内容分))",
        "formula_this": (
            "本次：0.40 × {tech} + 0.60 × {content}，按 0.5 分档后为 {combined} 分（{grade} 级）。{gate}"
        ),
        "formula_missing": "因缺少其中一侧总分，本次不发布综合分。",
        "narrative_kicker": "口径说明",
        "layer1_lead": "第一层：技术可发现性是内容被考虑的前提。",
        "layer1_body": (
            "这对应本报告的访问门槛，以及技术分仍占 40%。"
            "Google 写明：要作为 AI Overviews 或 AI Mode 的支持链接出现，页面必须已被索引，"
            "且符合 Search 技术要求、能以摘要形式出现在搜索结果中；满足技术要求同样适用于 AI 格式。"
            "OpenAI、Anthropic、Meta 和 Kimi 的官方文档也分别把允许各自的搜索爬虫访问，"
            "写成出现在该产品搜索结果或被引用的前提，用于支撑这一访问资格层。"
            "训练爬虫（如 GPTBot、ClaudeBot、KimiBot）被拦截不触发本门槛，"
            "这与各家把训练和搜索分开设置的官方做法一致。"
        ),
        "layer2_lead": "第二层：一旦可被访问，差异化在内容。",
        "layer2_body": (
            "这对应内容分占 60%。目前只有 Google 在官方指南中明确写到："
            "创造人们认为独特、有吸引力且有用的内容，长远来看很可能比该指南中其他建议，"
            "更能影响网站在生成式 AI 搜索中的存在感。"
            "KDD 2024 论文《GEO: Generative Engine Optimization》在来源已被检索到的前提下，"
            "观察到补充统计、引语和出处等内容侧方法，可以提升在生成式引擎回答中的可见度。"
            "OpenAI 只写到排名会用多项因素帮助用户找到「相关、可靠的信息」，且位置不保证——"
            "不能据此写成 OpenAI 也认为内容权重大于技术。"
        ),
        "layer3_lead": "第三层：40/60 是我们据此定下的产品口径，不是任何一家厂商或论文公布的比例。",
        "layer3_body": (
            "不选 50/50，是避免把「能否被考虑」与「被考虑之后凭什么胜出」等量齐观，"
            "这与 Google「内容影响可能更大」的表述不一致。"
            "不选 30/70，是因为我们的技术 100 分里已包含 SEO 可发现性、正文吸收和页面质量；"
            "技术权重再压低，会轻视 JavaScript 站点上真实存在的可抽取障碍。"
            "各家官方陈述只适用于其自身产品。"
            "论文里「可见度提升至多 40%」是内容侧实验观察，与本报告 40% 的技术权重不是同一回事，"
            "也不是对客户引用结果的承诺。"
        ),
        "max": "满分",
        "grade": "等级",
        "track": "轨道",
        "score": "得分",
        "weight": "权重",
        "tech_kicker": "03 技术摘要",
        "tech_h2": "站内就绪度（含 SEO 可发现性）",
        "tech_nine": "十维就绪度",
        "tech_seo": "SEO 内容可发现性（技术百分制中的 15 分维）",
        "provisional": "暂定 / 抓取受限",
        "strengths": "已有基础",
        "key_findings": "关键发现",
        "see_full_tech": "完整证据链仍以独立的技术 HTML 报告为准。",
        "content_kicker": "04 内容摘要",
        "content_h2": "架构、写作、证据与问题覆盖",
        "dimensions": "维度",
        "see_full_content": "完整证据链仍以独立的内容 GEO HTML 报告为准。",
        "shared_kicker": "05 共通问题",
        "shared_h2": "同一根因、同时影响两侧的问题",
        "shared_note": (
            "同一根因在此只写一次，并注明同时影响哪一侧。"
            "技术吸收维与内容写作维都可能打到「可抽取正文不足」；综合分披露这一重叠，但不做去重折算。"
        ),
        "timeline_kicker": "06 统一优先行动与工期",
        "timeline_h2": "两侧合并的下一步与按工作量估算的时间表",
        "timeline_intro": (
            "工期来自本轮发现与优先行动，不是拉长的多周日历。"
            "HTTPS/抓取恢复按天计；内容建设更长。可按产能调整负责人与并行；收尾用同一批抽样 URL 复测。"
            "下表只写改善方向，不承诺「做完综合分可到某一分数」。"
        ),
        "actions_h3": "来自两侧的优先行动",
        "priority": "优先级",
        "action": "行动",
        "owner": "负责人",
        "effort": "工作量",
        "outcome": "验收口径 / 预期结果",
        "days_unit": "天",
        "scope_kicker": "07 范围与披露",
        "scope_h2": "本次评测覆盖范围",
        "scope_overlap": (
            "综合分是两侧已有头条总分的加权复合，不是第三套独立打分。"
            "技术吸收维与内容写作维、实体与权威之间的重叠已披露，不做去重折算。"
        ),
        "scope_excluded": (
            "明确不计入综合分：提及率、引用率、声量；llms.txt 与其他实验性约定；训练爬虫状态；站外品牌监测。"
        ),
        "scope_absent": "范围内未见，不等于该类型在全站不存在。",
        "unevaluated": "未评估或范围内未见的类型",
        "fetch_disclosure": "抓取披露",
        "closing_kicker": "08 结语",
        "closing_h2": "结语",
        "closing_template": (
            "综合判定为{label} {score} 分（{grade} 级）。{gate}"
            "首要动作：{first}"
            "建议用同一批抽样 URL 复测。"
            "本分不代表排名、流量或保证被 AI 引用。"
        ),
        "refs_kicker": "09 参考来源",
        "refs_h2": "参考来源",
        "refs_disclaimer": (
            "下列资料用于说明评分原则，并不表示这些机构发布或认可本报告的具体分数与权重；"
            "各家陈述只适用于其自身产品；除 Google 外，下列厂商文档主要说明访问与展示前提，"
            "没有公布内容与技术的占比；学术结论是实验观察，不是引用率承诺。"
        ),
        "none": "—",
        "problem": "问题",
        "impact": "影响",
        "fix": "整改",
        "footer": "GEO Checker · 综合包",
        "docfoot": (
            "Beansmile · GEO Checker 综合包。"
            "技术 /100 与内容 GEO /100 仍独立呈现；综合 /100 为第三个头条数"
            "（内容 60%、技术 40%，另设访问门槛）。"
            "不代表排名、流量或保证被 AI 引用。"
        ),
        "alt_link": "预印本",
    },
}


def _finding_title(f) -> str:
    if isinstance(f, str):
        return f
    return f.get("title") or f.get("problem") or ""


def _finding_blob(f) -> str:
    if isinstance(f, str):
        return f.lower()
    parts = [
        f.get("title") or "",
        f.get("problem") or "",
        f.get("solution") or "",
        f.get("impact") or "",
    ]
    return " ".join(parts).lower()


def collect_shared_findings(tech: dict, content: dict, limit: int = 6) -> list:
    """Surface findings that appear on both tracks (crawl, thin pages, etc.)."""
    tech_findings = list(tech.get("findings") or [])
    seo = tech.get("seo_discoverability") or {}
    tech_findings.extend(seo.get("findings") or [])
    content_findings = list(content.get("findings") or [])

    shared = []
    used = set()

    def norm(t: str) -> str:
        t = t.lower()
        for token in (
            "http", "https", "tls", "crawl", "thin", "title", "sitemap", "robots",
            "抓取", "薄", "可抽取", "正文", "h1",
        ):
            if token in t:
                return token
        return t[:40]

    content_keys = {norm(_finding_title(f)): f for f in content_findings}

    for f in tech_findings + content_findings:
        title = _finding_title(f)
        key = norm(title)
        if key in used:
            continue
        chosen = content_keys.get(key) or f
        shared.append(chosen)
        used.add(key)
        if len(shared) >= limit:
            break
    return shared


def _has_extractability_overlap(tech: dict, content: dict) -> bool:
    blobs = []
    for f in (tech.get("findings") or []) + (content.get("findings") or []):
        blobs.append(_finding_blob(f))
    blobs.append((tech.get("overall_summary") or "").lower())
    blobs.append((content.get("overall_summary") or "").lower())
    text = " ".join(blobs)
    keys = ("可抽取", "薄正文", "正文不足", "正文偏少", "thin", "extractable", "空 title", "缺少 title")
    tech_hit = any(k in (tech.get("overall_summary") or "") or k in "".join(_finding_blob(f) for f in (tech.get("findings") or [])) for k in keys)
    content_hit = any(k in (content.get("overall_summary") or "") or k in "".join(_finding_blob(f) for f in (content.get("findings") or [])) for k in keys)
    return bool(tech_hit and content_hit)


def render_finding_blocks(findings: list, S: dict, limit: int = 5) -> str:
    out = []
    for i, f in enumerate(findings[:limit], 1):
        if isinstance(f, str):
            out.append(f'<div class="frow"><h4>{i} · {esc(f)}</h4></div>')
            continue
        sev = (f.get("severity") or "medium")
        sev_slug = re.sub(r"\s+", "-", str(sev).lower())
        out.append(
            f"""<div class="frow">
  <div class="frow-h"><span class="sev sev-{esc(sev_slug)}">{esc(str(sev))}</span>
  <h4>{i} · {esc(f.get('title') or '')}</h4></div>
  <p><b>{esc(S['problem'])}</b>: {esc(f.get('problem') or '')}</p>
  <p><b>{esc(S['impact'])}</b>: {esc(f.get('impact') or '')}</p>
  <p class="fix"><b>{esc(S['fix'])}</b>: {esc(f.get('solution') or '')}</p>
</div>"""
        )
    return "".join(out) or f"<p class='note'>{esc(S['none'])}</p>"


def infer_brand(tech: dict, content: dict, override: str | None) -> str:
    if override:
        return override
    banned = {"geo checker", "beansmile", "beansmile · geo checker", "geo checker · beansmile"}
    for cand in (
        content.get("site_brand"),
        content.get("company_name"),
        tech.get("brand"),
        tech.get("site_brand"),
    ):
        if cand and str(cand).strip().lower() not in banned:
            return str(cand).strip()
    title = content.get("title") or ""
    if "·" in title:
        left = title.split("·")[0].strip()
        if left and left.lower() not in banned:
            return left
    for text in (content.get("overall_summary") or "", tech.get("overall_summary") or ""):
        m = re.match(r"([^（(]{2,40}?)(?:（|\(|技术|内容|的)", text)
        if m:
            return m.group(1).strip()
    return (
        content.get("domain")
        or tech.get("domain")
        or urlparse(tech.get("url") or "").hostname
        or "site"
    )


def observation_label(tech: dict, content: dict, S: dict) -> str:
    mode = (
        (tech.get("scope") or {}).get("observation_mode")
        or tech.get("observation_mode")
        or content.get("fetch_mode")
        or ""
    )
    mode = str(mode).lower()
    if mode in {"raw_http_html", "raw_html", "raw"} or "原始" in (content.get("fetch_disclosure") or ""):
        return S["obs_raw"]
    return mode or S["none"]


def report_date(tech: dict, content: dict) -> str:
    raw = (content.get("generated_at") or tech.get("generated_at") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    return datetime.now().strftime("%Y-%m-%d")


def sample_size_label(tech: dict, content: dict, S: dict) -> str:
    content_n = content.get("pages_analyzed")
    tech_n = tech.get("sampled_count") or (tech.get("scope") or {}).get("sampled_count")
    parts = []
    if content_n:
        parts.append(f"{S['content_pages']} {content_n} {S['pages_unit']}")
    if tech_n and tech_n != content_n:
        parts.append(f"{S['tech_pages']} {tech_n} {S['pages_unit']}")
    elif tech_n and not content_n:
        parts.append(f"{tech_n} {S['pages_unit']}")
    return " · ".join(parts) if parts else S["none"]


def gate_label(gate: dict, S: dict) -> str:
    if not gate or not gate.get("applied"):
        return S["gate_off"]
    if gate.get("kind") == "hard" or gate.get("cap") == 30:
        return S["gate_hard"]
    return S["gate_soft"]



CONF_LABELS = {
    "en": {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "provisional": "provisional",
        "none": "none",
    },
    "zh": {
        "high": "高",
        "medium": "中",
        "low": "低",
        "provisional": "暂定",
        "none": "无",
    },
}


def confidence_label(value, lang: str) -> str:
    if value in (None, "", "—"):
        return "—"
    raw = str(value).strip()
    table = CONF_LABELS.get(lang) or CONF_LABELS["en"]
    return table.get(raw.lower(), raw)


def first_action_text(content: dict, tech: dict) -> str:
    closing = (content.get("closing") or "").strip()
    if closing:
        text = closing
        if text and not text.endswith(("。", ".", "！", "!", "？", "?")):
            text += "。" if re.search(r"[\u4e00-\u9fff]", text) else ". "
        return text
    for a in content.get("priority_actions") or []:
        if isinstance(a, dict) and a.get("action"):
            return str(a.get("action")).strip() + ("。" if re.search(r"[\u4e00-\u9fff]", str(a.get("action"))) else ". ")
        if isinstance(a, str) and a.strip():
            return a.strip()
    for step in tech.get("next_steps") or []:
        if isinstance(step, dict) and step.get("title"):
            return str(step.get("title")).strip() + ("。" if re.search(r"[\u4e00-\u9fff]", str(step.get("title"))) else ". ")
    return ""


def unevaluated_types(tech: dict, content: dict) -> list[str]:
    cov = tech.get("coverage") or {}
    items = []
    for key in ("unevaluated_types", "observed_absent_types"):
        for t in cov.get(key) or []:
            if t and t not in items:
                items.append(str(t))
    for w in (tech.get("scope") or {}).get("scope_warnings") or []:
        if isinstance(w, dict) and w.get("required"):
            label = str(w.get("required"))
            if w.get("reason"):
                label = f"{label} ({w.get('reason')})"
            if label not in items:
                items.append(label)
    return items


def _action_blob(item) -> str:
    if isinstance(item, dict):
        return " ".join(
            str(item.get(k) or "")
            for k in ("action", "title", "title_zh", "detail", "solution", "solution_zh", "body", "problem")
        ).lower()
    return str(item).lower()


# Same-issue tokens used to drop translated duplicates (e.g. English SEO
# "Canonical tags missing…" vs already-translated TEC-CANONICAL-MISSING).
_THEME_TOKENS = ("canonical",)

_OWNER_ZH = {
    "content": "内容",
    "eng/ops": "工程 / 运维",
    "eng": "工程",
    "engineering": "工程",
    "ops": "运维",
}


def _already_covered(title: str, existing: str) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return False
    blob = (existing or "").lower()
    if t in blob:
        return True
    for tok in _THEME_TOKENS:
        if tok in t and tok in blob:
            return True
    return False


def _owner_label(owner: str, lang: str) -> str:
    raw = (owner or "").strip()
    if lang == "zh":
        return _OWNER_ZH.get(raw.lower(), raw)
    return raw


def _localized_title(item: dict, lang: str) -> str:
    if lang == "zh":
        return (item.get("title_zh") or item.get("title") or item.get("action") or item.get("solution") or "").strip()
    return (item.get("title") or item.get("title_zh") or item.get("action") or item.get("solution") or "").strip()


def _localized_detail(item: dict, lang: str) -> str:
    if lang == "zh":
        return (item.get("solution_zh") or item.get("solution") or item.get("detail") or item.get("body") or "").strip()
    return (item.get("solution") or item.get("solution_zh") or item.get("detail") or item.get("body") or "").strip()


def collect_actions(tech: dict, content: dict, lang: str = "en") -> list:
    actions = list(content.get("priority_actions") or [])
    seo = tech.get("seo_discoverability") or {}
    existing = " ".join(_action_blob(a) for a in actions)
    # Tech findings / next steps are later merged into the timeline; treat them
    # as already covered so an untranslated SEO copy is not added beside them.
    existing += " " + " ".join(_action_blob(f) for f in (tech.get("findings") or []))
    existing += " " + " ".join(_action_blob(s) for s in (tech.get("next_steps") or []))
    for f in seo.get("findings") or []:
        if not isinstance(f, dict) or not (f.get("solution") or f.get("solution_zh")):
            continue
        title = _localized_title(f, lang)
        detail = _localized_detail(f, lang)
        if not title or _already_covered(title, existing):
            continue
        owner = "eng/ops" if any(
            k in _finding_blob(f) for k in ("crawl", "抓取", "爬虫", "robots")
        ) else "content"
        actions.append(
            {
                "sev": "P0" if (f.get("severity") or "") in ("critical", "高") else "P1",
                "action": title,
                "detail": detail,
                "owner": _owner_label(owner, lang),
            }
        )
        existing += " " + title.lower() + " " + detail.lower()
    for step in tech.get("next_steps") or []:
        if not isinstance(step, dict):
            continue
        title = _localized_title(step, lang)
        if not title or _already_covered(title, existing):
            continue
        actions.append(
            {
                "sev": "P1",
                "action": title,
                "detail": step.get("body") or "",
                "owner": _owner_label(step.get("owner") or "", lang),
            }
        )
        existing += " " + title.lower()
    return actions


def render_actions_table(actions: list, S: dict) -> str:
    if not actions:
        return f"<p class='note'>{esc(S['none'])}</p>"
    rows = []
    for a in actions:
        if isinstance(a, str):
            rows.append(
                f"<tr><td class='mono'>—</td><td>{esc(a)}</td>"
                f"<td>{esc(S['none'])}</td><td class='mono'>{esc(S['none'])}</td>"
                f"<td>{esc(S['none'])}</td></tr>"
            )
            continue
        sev = a.get("sev") or a.get("priority") or "P1"
        action = a.get("action") or ""
        detail = a.get("detail") or ""
        body = esc(action)
        if detail:
            body += f"<p class='tdetail'>{esc(detail)}</p>"
        owner = a.get("owner") or S["none"]
        days = a.get("effort_days")
        effort = f"{days} {S['days_unit']}" if days not in (None, "") else S["none"]
        outcome = a.get("outcome") or S["none"]
        rows.append(
            f"<tr><td class='mono'>{esc(str(sev))}</td><td>{body}</td>"
            f"<td>{esc(str(owner))}</td><td class='mono'>{esc(effort)}</td>"
            f"<td>{esc(str(outcome))}</td></tr>"
        )
    return (
        f"<table class='mtable actions-table'><thead><tr>"
        f"<th>{esc(S['priority'])}</th><th>{esc(S['action'])}</th>"
        f"<th>{esc(S['owner'])}</th><th>{esc(S['effort'])}</th>"
        f"<th>{esc(S['outcome'])}</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_sources(lang: str, S: dict) -> str:
    items = []
    for src in SOURCES:
        title = src["title_zh"] if lang == "zh" else src["title_en"]
        meta = src["meta_zh"] if lang == "zh" else src["meta_en"]
        url = src["url"]
        alt = ""
        if src.get("url_alt"):
            alt_label = src.get("url_alt_label_zh") if lang == "zh" else src.get("url_alt_label_en")
            alt = (
                f" · <a href=\"{esc(src['url_alt'])}\">{esc(alt_label or S['alt_link'])}</a>"
                f" <span class='ref-url mono'>{esc(src['url_alt'])}</span>"
            )
        items.append(
            f"<li><div class='ref-title'>{esc(title)}</div>"
            f"<div class='ref-meta'>{esc(meta)}</div>"
            f"<div><a href=\"{esc(url)}\">{esc(url)}</a>{alt}</div></li>"
        )
    return (
        f"<p class='disclaimer'>{esc(S['refs_disclaimer'])}</p>"
        f"<ol class='refs'>{''.join(items)}</ol>"
    )


def build_combined_payload(tech: dict, content: dict, lang: str, brand: str, date: str) -> dict:
    result = score_from_reports(tech, content)
    return {
        "schema": "geo_checker_combined",
        "domain": content.get("domain") or tech.get("domain"),
        "site_url": content.get("site_url") or tech.get("url"),
        "brand": brand,
        "generated_at": date,
        "lang": lang,
        "technical": {
            "overall_score": result.get("tech_overall"),
            "grade": result.get("tech_grade"),
        },
        "content": {
            "overall_score": result.get("content_overall"),
            "grade": result.get("content_grade"),
            "sampled": result.get("sampled"),
        },
        "combined": {
            "overall_score": result.get("overall_score"),
            "grade": result.get("grade"),
            "label": (
                "抽样页综合分" if result.get("sampled") and lang == "zh"
                else "sampled-pages combined score" if result.get("sampled")
                else "综合分" if lang == "zh" else "combined score"
            ),
            "weights": {"technical": TECH_WEIGHT, "content": CONTENT_WEIGHT},
            "gate": result.get("gate"),
            "sampled": result.get("sampled"),
            "missing": result.get("missing"),
        },
    }


def render_html(tech: dict, content: dict, style_css: str, lang: str, brand: str | None) -> str:
    S = STRINGS[lang]
    domain = (
        content.get("domain")
        or tech.get("domain")
        or urlparse(tech.get("url") or "").hostname
        or "site"
    )
    brand = infer_brand(tech, content, brand)
    date = report_date(tech, content)
    result = score_from_reports(tech, content)
    gate = result.get("gate") or {}
    gate_text = gate_label(gate, S)
    combined_score = result.get("overall_score")
    combined_grade = result.get("grade") or "—"
    sampled = result.get("sampled")
    combined_label = S["combined_label_sampled"] if sampled else S["combined_label"]

    tech_score = tech.get("overall_score")
    tech_grade = tech.get("grade") or "—"
    seo = tech.get("seo_discoverability") or {}
    _seo_dim = next((d for d in (tech.get("dimensions") or []) if d.get("key") == "seo"), None)
    if _seo_dim and _seo_dim.get("score") is not None:
        seo_score = _seo_dim.get("score")
        seo_grade = _seo_dim.get("grade") or seo.get("grade") or "—"
    else:
        raw = seo.get("score")
        mx = seo.get("max") or 15
        if raw is not None and float(mx) == 25:
            seo_score = round(float(raw) * 15 / 25, 1)
        else:
            seo_score = seo.get("dim_score", raw)
        seo_grade = seo.get("grade") or "—"
    seo_conf = seo.get("confidence") or ("provisional" if tech.get("provisional") else "—")
    content_score = content.get("overall_score")
    content_grade = content.get("grade") or "—"
    content_conf = confidence_label(content.get("confidence") or "—", lang)

    seo_conf = confidence_label(seo_conf, lang)
    _, tc, tg, _ = grade_meta(tech_grade if tech_score is not None else "F")
    _, cc, cg, _ = grade_meta(content_grade if content_score is not None else "F")
    _, xc, xg, _ = grade_meta(combined_grade if combined_score is not None else "F")

    tech_disp = format_score(tech_score)
    content_disp = format_score(content_score)
    combined_disp = format_score(combined_score)
    # SEO dim is a component detail; show only as qualitative text in the
    # summary (do not print 0.1-level tech dim scores as customer headlines).
    seo_narr = seo.get("narr") or seo.get("callout") or ""

    pct_source = combined_score if combined_score is not None else (
        content_score if content_score is not None else tech_score
    )
    pct = 0 if pct_source is None else max(0, min(100, float(pct_source)))
    pct_disp = format_score(pct)

    provisional_badge = ""
    if tech.get("provisional") or (seo.get("confidence") or "").lower() == "provisional":
        provisional_badge = f'<span class="sev sev-warning">{esc(S["provisional"])}</span>'

    tech_summary = tech.get("overall_summary") or tech.get("closing") or ""
    if "<" in tech_summary and ">" in tech_summary:
        tech_summary_html = tech_summary
    else:
        tech_summary_html = inline_md(tech_summary)
    content_summary = content.get("overall_summary") or ""

    tech_strengths = "".join(f"<li>{esc(s)}</li>" for s in (tech.get("strengths") or [])[:6]) or f"<li>{esc(S['none'])}</li>"
    content_strengths = "".join(f"<li>{esc(s)}</li>" for s in (content.get("strengths") or [])[:6]) or f"<li>{esc(S['none'])}</li>"

    tech_findings = list(tech.get("findings") or [])
    # Keep scored / higher-severity findings first; still skip inventing new ones.
    content_findings = list(content.get("findings") or [])

    dim_rows = "".join(
        f"<tr><td>{esc(content_dim_name(d, lang))}</td>"
        f"<td class='num mono'>{esc(format_score(d.get('score')))}</td>"
        f"<td class='dim mono'>/{esc(str(d.get('max')))}</td>"
        f"<td class='dim mono r'>{esc(str(d.get('grade')))}</td></tr>"
        for d in (content.get("dimensions") or [])
    )

    shared = collect_shared_findings(tech, content)
    shared_html = render_finding_blocks(shared, S, limit=6)

    actions = collect_actions(tech, content, lang)
    _tl_sources = list(actions)
    for f in (content_findings + tech_findings):
        if isinstance(f, dict):
            _tl_sources.append({
                "title": f.get("title") or f.get("problem") or "",
                "detail": f.get("solution") or "",
                "sev": f.get("severity") or "",
                "owner": f.get("owner") or "",
            })
        elif isinstance(f, str):
            _tl_sources.append({"title": f})
    page_count = content.get("pages_analyzed") or (tech.get("scope") or {}).get("sampled_count")
    timeline_block = render_timeline_block(
        _tl_sources,
        lang=lang,
        page_count=page_count,
        include_retest=True,
        show_samples=False,
        limit=12,
    )
    actions_table = render_actions_table(actions, S)

    tech_finding_html = render_finding_blocks(tech_findings, S, limit=4)
    content_finding_html = render_finding_blocks(content_findings, S, limit=5)

    scope_note = content.get("scope_note") or (tech.get("scope") or {}).get("note") or (tech.get("coverage") or {}).get("note_zh" if lang == "zh" else "note_en") or ""
    fetch_disclosure = content.get("fetch_disclosure") or ""
    closing = content.get("closing") or tech.get("closing") or ""
    first = first_action_text(content, tech) or (closing or S["none"])

    site_url = content.get("site_url") or tech.get("url") or f"https://{domain}"
    obs = observation_label(tech, content, S)
    sample_lbl = sample_size_label(tech, content, S)
    missing = result.get("missing")

    if missing:
        formula_this = S["formula_missing"]
        this_score = S["formula_missing"]
        closing_html = inline_md(closing) if closing else esc(S["formula_missing"])
    else:
        formula_this = S["formula_this"].format(
            tech=tech_disp, content=content_disp,
            combined=combined_disp, grade=combined_grade, gate=gate_text,
        )
        this_score = S["intro_this_score"].format(
            label=combined_label, score=combined_disp, grade=combined_grade,
            tech=tech_disp, tech_grade=tech_grade,
            content=content_disp, content_grade=content_grade,
            gate=gate_text,
        )
        closing_html = esc(S["closing_template"].format(
            label=combined_label, score=combined_disp, grade=combined_grade,
            gate=gate_text, first=first,
        ))

    overlap_note = S["intro_overlap"] if _has_extractability_overlap(tech, content) else ""
    uneval = unevaluated_types(tech, content)
    uneval_html = ""
    if uneval:
        uneval_html = (
            f"<div class='sublab'>{esc(S['unevaluated'])}</div>"
            f"<ul class='plain'>{''.join(f'<li>{esc(x)}</li>' for x in uneval)}</ul>"
        )

    gate_banner = ""
    if gate.get("applied"):
        gate_banner = f"<p class='gate-banner'>{esc(gate_text)}</p>"

    sources_html = render_sources(lang, S)
    meta_desc = (
        f"{combined_label} {combined_disp}/100 ({combined_grade}); "
        f"{S['tech_label']} {tech_disp}/100 ({tech_grade}); "
        f"{S['content_label']} {content_disp}/100 ({content_grade})."
        if not missing else f"{S['tech_label']} {tech_disp}/100; {S['content_label']} {content_disp}/100."
    )

    return f"""<!doctype html><html lang="{esc(S['html_lang'])}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(brand)} {esc(S['doc_title'])} · {esc(domain)}</title>
<meta name="description" content="{esc(meta_desc)}">
<style>{style_css}
/* Combined report extras on shared technical stylesheet */
.page {{ min-height: auto; padding-bottom: 2rem; }}
.deck {{ max-width: 920px; margin: 0 auto; }}
.sev {{ display:inline-block; font-size:.75rem; letter-spacing:.04em; padding:2px 8px; border-radius:999px; background:#eee; }}
.sev-critical, .sev-high, .sev-高 {{ background:#fee2e2; color:#991b1b; }}
.sev-medium, .sev-中 {{ background:#e0e7ff; color:#3730a3; }}
.sev-low, .sev-低 {{ background:#ecfdf5; color:#065f46; }}
.sev-warning {{ background:#ffedd5; color:#9a3412; }}
.c-a{{color:var(--success)}}.c-b{{color:var(--info)}}.c-c{{color:var(--warning)}}.c-d{{color:var(--danger)}}
.g-a{{color:var(--success)}}.g-b{{color:var(--info)}}.g-c{{color:var(--warning)}}.g-d{{color:var(--danger)}}
.score-grid{{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:16px;margin-top:var(--space-5)}}
.score-card{{background:var(--surface-2);border:1px solid var(--border);border-radius:12px;padding:16px 18px}}
.score-card.featured{{border-color:var(--text-2);background:var(--surface-1)}}
.score-card .label{{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3);font-weight:600}}
.score-card .val{{font-family:var(--font-mono);font-size:28px;font-weight:650;margin-top:6px}}
.score-card.featured .val{{font-size:36px}}
.score-card .val small{{font-size:13px;color:var(--text-3);font-weight:500}}
.score-card .sub{{font-size:12.5px;color:var(--text-3);margin-top:4px}}
@media (max-width:720px){{.score-grid{{grid-template-columns:1fr}}}}
.formula{{font-family:var(--font-mono);background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin:16px 0;font-size:13.5px;line-height:1.55}}
.layers{{margin:18px 0 0;padding:0;list-style:none;counter-reset:layer}}
.layers>li{{margin:0 0 16px;padding:14px 16px 14px 18px;border-left:3px solid var(--border);background:var(--surface-2);border-radius:0 10px 10px 0}}
.layers>li h3{{margin:0 0 6px;font-size:15px}}
.gate-banner{{background:#ffedd5;color:#9a3412;border-radius:8px;padding:10px 14px;font-size:14px}}
.disclaimer{{font-size:13.5px;line-height:1.65;background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:14px 16px}}
ol.refs{{margin:18px 0 0;padding-left:1.3em}}
ol.refs li{{margin:0 0 14px}}
.ref-title{{font-weight:600}}
.ref-meta{{color:var(--text-3);font-size:13px;margin:2px 0 4px}}
.ref-url{{font-size:12px;color:var(--text-3);margin-left:6px}}
.tdetail{{margin:6px 0 0;color:var(--text-2);font-size:13px}}
.actions-table td{{vertical-align:top}}
.cover-comp{{margin:8px 0 0;font-size:13.5px;color:#C7D2FE}}
</style></head><body>
<div class="topbar"><div class="topbar-in">
  <span class="brand"><b>GEO Checker</b></span>
  <span class="doc">{esc(brand)} · {esc(S['doc_title'])} · {esc(domain)}</span>
  <span class="right"><span class="now mono">{esc(date)}</span></span>
</div><div class="progress"><i style="width:{pct_disp}%"></i></div></div>

<div class="deck">

<section class="page page-dark cover" id="cover">
  <div class="cover-top"><span class="brand"><b>GEO Checker</b></span>
    <span class="cover-no mono">Beansmile · GEO Checker</span></div>
  <div class="cover-mid">
    <div class="pkicker light">{esc(S['cover_kicker'])}</div>
    <h1>{esc(brand)}<br>{esc(S['cover_h1'])}</h1>
    <p class="cover-sub">{esc(S['cover_sub'])}</p>
    <div class="cover-score">
      <div class="cbig">{esc(combined_disp)}<small>/100</small><em>{esc(combined_label)} {esc(str(combined_grade))}</em></div>
      <div><div class="cmeter"><div class="cm-track"><span class="cm-fill" style="width:{pct_disp}%"></span></div>
      <div class="cm-scale"><span>0</span><span>{esc(S['pass_label'])}</span><span>{esc(S['good_label'])}</span><span>100</span></div></div>
      <p class="cover-score-note">{esc(S['tech_label'])}: {esc(tech_disp)}/100 ({esc(str(tech_grade))}) · {esc(S['content_label'])}: {esc(content_disp)}/100 ({esc(str(content_grade))})</p>
      <p class="cover-comp">{esc(S['weights_line'])} · {esc(gate_text)}</p>
      <p class="cover-score-note">{esc(S['cover_what'])}</p></div>
    </div>
  </div>
  <dl class="cover-facts">
    <div class="wide"><dt>{esc(S['site'])}</dt><dd class="mono">{esc(site_url)}</dd></div>
    <div><dt>{esc(S['report_date'])}</dt><dd class="mono">{esc(date)}</dd></div>
    <div><dt>{esc(S['sample_size'])}</dt><dd>{esc(sample_lbl)}</dd></div>
    <div><dt>{esc(S['obs_mode'])}</dt><dd>{esc(obs)}</dd></div>
    <div><dt>{esc(S['confidence'])}</dt><dd>{esc(str(content_conf))} · tech {esc(str(seo_conf))}</dd></div>
    <div><dt>{esc(S['grade_scale'])}</dt><dd class="mono">{S['grade_scale_value']}</dd></div>
  </dl>
  <div class="cover-sign"><span>{esc(S['prepared_by'])}</span> {provisional_badge}</div>
</section>

<section class="page" id="conclusion">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">01</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['intro_kicker'])}</div>
    <h2>{esc(S['intro_h2'])}</h2></div></div>
  <div class="narr lead">{S['intro_lead']}</div>
  {gate_banner}
  <p class="narr">{esc(this_score)}</p>
  <div class="sublab">{esc(S['intro_tech'])}</div>
  <div class="narr">{tech_summary_html}</div>
  <div class="sublab">{esc(S['intro_content'])}</div>
  <div class="narr">{inline_md(content_summary)}</div>
  {"<p class='narr'>" + esc(overlap_note) + "</p>" if overlap_note else ""}
  <div class="sublab">{esc(S['intro_priority'])}</div>
  <p class="narr">{esc(first)}</p>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="scores">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">02</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['scores_kicker'])}</div>
    <h2>{esc(S['scores_h2'])}</h2></div></div>
  <p class="narr">{esc(S['scores_note'])}</p>
  <div class="score-grid">
    <div class="score-card featured">
      <div class="label">{esc(combined_label)}</div>
      <div class="val {xc}">{esc(combined_disp)}<small>/100</small> <em class="g {xg}">{esc(str(combined_grade))}</em></div>
      <div class="sub">{esc(S['combined_card_sub'])}</div>
    </div>
    <div class="score-card">
      <div class="label">{esc(S['tech_label'])}</div>
      <div class="val {tc}">{esc(tech_disp)}<small>/100</small> <em class="g {tg}">{esc(str(tech_grade))}</em></div>
      <div class="sub">{esc(S['tech_card_sub'])} · {esc(S['confidence'])}: {esc(str(seo_conf))}</div>
    </div>
    <div class="score-card">
      <div class="label">{esc(S['content_label'])}</div>
      <div class="val {cc}">{esc(content_disp)}<small>/100</small> <em class="g {cg}">{esc(str(content_grade))}</em></div>
      <div class="sub">{esc(S['content_card_sub'])} · {esc(S['confidence'])}: {esc(str(content_conf))}</div>
    </div>
  </div>
  <div class="sublab">{esc(S['formula_label'])}</div>
  <div class="formula">{esc(S['formula_text'])}<br>{esc(formula_this)}</div>
  <table class="mtable" style="margin-top:8px"><thead>
    <tr><th>{esc(S['track'])}</th><th>{esc(S['score'])}</th><th>{esc(S['max'])}</th><th>{esc(S['weight'])}</th><th class="r">{esc(S['grade'])}</th></tr>
  </thead><tbody>
    <tr><td>{esc(S['tech_label'])}</td><td class="num mono">{esc(tech_disp)}</td><td class="dim mono">/100</td><td class="dim mono">40%</td><td class="r">{esc(str(tech_grade))}</td></tr>
    <tr><td>{esc(S['content_label'])}</td><td class="num mono">{esc(content_disp)}</td><td class="dim mono">/100</td><td class="dim mono">60%</td><td class="r">{esc(str(content_grade))}</td></tr>
    <tr class="total"><td>{esc(combined_label)}</td><td class="num mono">{esc(combined_disp)}</td><td class="dim mono">/100</td><td class="dim mono">—</td><td class="r">{esc(str(combined_grade))}</td></tr>
  </tbody></table>
  <div class="sublab">{esc(S['narrative_kicker'])}</div>
  <ol class="layers">
    <li><h3>{esc(S['layer1_lead'])}</h3><p>{esc(S['layer1_body'])}</p></li>
    <li><h3>{esc(S['layer2_lead'])}</h3><p>{esc(S['layer2_body'])}</p></li>
    <li><h3>{esc(S['layer3_lead'])}</h3><p>{esc(S['layer3_body'])}</p></li>
  </ol>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="tech">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">03</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['tech_kicker'])}</div>
    <h2>{esc(S['tech_h2'])}</h2></div>
    <div class="pmeta"><span class="scorechip {tc}"><b>{esc(tech_disp)}</b><span>/100</span>
    <em class="g {tg}">{esc(str(tech_grade))}</em></span></div></div>
  <div class="sublab">{esc(S['tech_nine'])}</div>
  <div class="narr">{tech_summary_html}</div>
  <div class="sublab">{esc(S['tech_seo'])}</div>
  <div class="narr">{inline_md(seo_narr)}</div>
  <div class="sublab">{esc(S['strengths'])}</div>
  <ul class="plain">{tech_strengths}</ul>
  <div class="sublab">{esc(S['key_findings'])}</div>
  {tech_finding_html}
  <p class="note">{esc(S['see_full_tech'])}</p>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="content">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">04</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['content_kicker'])}</div>
    <h2>{esc(S['content_h2'])}</h2></div>
    <div class="pmeta"><span class="scorechip {cc}"><b>{esc(content_disp)}</b><span>/100</span>
    <em class="g {cg}">{esc(str(content_grade))}</em></span></div></div>
  <div class="narr lead">{inline_md(content_summary)}</div>
  {"<p class='note'><b>" + esc(S['fetch_disclosure']) + "</b>: " + esc(fetch_disclosure) + "</p>" if fetch_disclosure else ""}
  <div class="sublab">{esc(S['dimensions'])}</div>
  <table class="mtable"><thead><tr><th>{esc(S['dimensions'])}</th><th>{esc(S['score'])}</th><th>{esc(S['max'])}</th><th class="r">{esc(S['grade'])}</th></tr></thead>
  <tbody>{dim_rows or "<tr><td colspan='4'>" + esc(S['none']) + "</td></tr>"}</tbody></table>
  <div class="sublab">{esc(S['strengths'])}</div>
  <ul class="plain">{content_strengths}</ul>
  <div class="sublab">{esc(S['key_findings'])}</div>
  {content_finding_html}
  <p class="note">{esc(S['see_full_content'])}</p>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="shared">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">05</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['shared_kicker'])}</div>
    <h2>{esc(S['shared_h2'])}</h2></div></div>
  <p class="narr">{esc(S['shared_note'])}</p>
  {shared_html}
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="timeline">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">06</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['timeline_kicker'])}</div>
    <h2>{esc(S['timeline_h2'])}</h2></div></div>
  <p class="narr">{esc(S['timeline_intro'])}</p>
  <div class="sublab">{esc(S['actions_h3'])}</div>
  {actions_table}
  {timeline_block}
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="scope">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">07</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['scope_kicker'])}</div>
    <h2>{esc(S['scope_h2'])}</h2></div></div>
  <p class="narr">{inline_md(scope_note)}</p>
  {"<p class='note'><b>" + esc(S['fetch_disclosure']) + "</b>: " + esc(fetch_disclosure) + "</p>" if fetch_disclosure else ""}
  <p class="narr">{esc(S['scope_overlap'])}</p>
  <p class="narr">{esc(S['scope_excluded'])}</p>
  <p class="narr">{esc(S['scope_absent'])}</p>
  {uneval_html}
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="closing">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">08</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['closing_kicker'])}</div>
    <h2>{esc(S['closing_h2'])}</h2></div></div>
  <div class="callout"><b>{esc(S['closing_h2'])}</b><p>{closing_html}</p></div>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="sources">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">09</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['refs_kicker'])}</div>
    <h2>{esc(S['refs_h2'])}</h2></div></div>
  {sources_html}
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

</div>
<p class="docfoot">{esc(S['docfoot'])}</p>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="Build combined GEO Checker HTML report")
    ap.add_argument("tech_run", help="Technical run directory (contains report.json)")
    ap.add_argument(
        "--content-run",
        default=None,
        help="Content run directory (contains content_report.json). Defaults to tech_run.",
    )
    ap.add_argument("--lang", default="en", choices=("en", "zh"))
    ap.add_argument("--out-dir", default=None, help="Output directory (default: <tech_run>/report)")
    ap.add_argument("--brand", default=None)
    args = ap.parse_args()

    tech_run = args.tech_run
    content_run = args.content_run or tech_run
    lang = args.lang

    tech = find_tech_report(tech_run)
    try:
        content = find_content_report(content_run, lang)
    except FileNotFoundError:
        if content_run == tech_run:
            print(
                "[build_combined_report] No content_report.json in tech run; "
                "pass --content-run <content_run_dir>",
                file=sys.stderr,
            )
            sys.exit(2)
        raise

    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    style_path = os.path.join(skill_root, "report_templates", "style.css")
    style = open(style_path, encoding="utf-8").read() if os.path.isfile(style_path) else ""

    out_dir = args.out_dir or os.path.join(tech_run, "report")
    os.makedirs(out_dir, exist_ok=True)

    brand = infer_brand(tech, content, args.brand)
    date = report_date(tech, content)
    html = render_html(tech, content, style, lang=lang, brand=args.brand)
    stem = "综合报告" if lang == "zh" else "Combined_Report"
    html_path = os.path.join(out_dir, f"{stem}.html")
    open(html_path, "w", encoding="utf-8").write(html)
    print(f"Wrote {html_path} ({len(html)} chars)")

    payload = build_combined_payload(tech, content, lang, brand, date)
    json_path = os.path.join(out_dir, f"{stem}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
