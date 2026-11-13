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
    from report_meter import meter_html
    from report_chrome import index_overlay, index_ui, load_deck_js, strip_section_number, topbar_index, content_dim_name
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from timeline_ui import render_timeline_block
    from report_meter import meter_html
    from report_chrome import index_overlay, index_ui, load_deck_js, strip_section_number, topbar_index, content_dim_name

from combined_score import (
    CONTENT_WEIGHT,
    TECH_WEIGHT,
    format_score,
    score_from_reports,
    snap_half,
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
        "doc_title": "GEO Combined Report",
        "cover_kicker": "Generative Engine Optimization",
        "cover_h1": "GEO Combined Report",
        "cover_sub": "Combines the technical and content evaluations into one overall score, with priority recommendations.",
        "site": "Site",
        "report_date": "Report date",
        "tech_label": "Technical readiness",
        "seo_label": "SEO discoverability",
        "content_label": "Content GEO",
        "combined_label": "Combined score",
        "combined_label_sampled": "Sampled-pages combined score",
        "cover_tech_note": "SEO is included in the technical score",
        "tech_card_sub": "10 items · includes SEO (15 pts) · 40%",
        "content_card_sub": "5 items · 60%",
        "combined_card_sub": "Technical 40% + content 60%; capped if search crawlers are blocked",
        "weights_line": "Weights: content 60% · technical 40%",
        "gate_off": "Search crawlers can access the site, so the combined score is not capped.",
        "gate_hard": "Search crawlers are blocked, so the combined score is capped at 30.",
        "gate_soft": "Some search crawlers are blocked, so the combined score is capped at 50.",
        "cover_what": "This is a combined score, not a search ranking, and it does not predict traffic or whether AI will mention you.",
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
            "The combined score brings the technical score (40%) and the content score (60%) together. "
            "If search crawlers are blocked, the combined score is capped. "
            "It is not a search ranking, and it does not predict traffic or whether AI will mention you."
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
            "The technical and content scores are still shown on their own. "
            "The combined score is 40% technical and 60% content; it is capped if search crawlers are blocked."
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
        "layer1_lead": "What the technical score covers",
        "layer1_body": (
            "The technical score is 40% of the combined score. It looks at whether the site can be crawled and understood. "
            "If search crawlers are blocked, the combined score is capped. "
            "A block on training crawlers (such as GPTBot or ClaudeBot) does not trigger that cap, "
            "but those crawlers should still be allowed if you want the content to enter model-training material."
        ),
        "layer2_lead": "What the content score covers",
        "layer2_body": (
            "The content score is 60% of the combined score. It looks at whether the writing is clear and credible, "
            "and whether it can answer buyers’ questions. "
            "Once a site can be accessed, content does more to decide whether AI will use the information, "
            "so content carries the larger weight."
        ),
        "layer3_lead": "How to read the score",
        "layer3_body": (
            "The technical and content scores are shown separately. "
            "The combined score is 40% technical and 60% content, then rounded to the nearest 0 or 0.5. "
            "This is how this report is calculated. Official notes and papers are listed at the end for reference."
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
            "The same issue is written once here, with a note on whether it affects the technical score, "
            "the content score, or both. Thin extractable text can affect both; it is not deducted again "
            "from the combined score."
        ),
        "timeline_kicker": "06 Priority actions & effort",
        "timeline_h2": "Unified next steps and an effort-based timeline",
        "timeline_intro": (
            "Timelines are estimates from this run and can be adjusted. "
            "Access and page-structure fixes can often be done quickly; content work takes longer. "
            "After changes, we recommend testing the same sample pages again. "
            "The table describes a direction of improvement; it does not promise a specific combined score."
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
            "The combined score is calculated from the existing technical and content totals. "
            "Thin extractable text can affect both scores; it is not deducted a third time from the combined score."
        ),
        "scope_excluded": (
            "The combined score does not include how often AI mentions or cites the site, or files such as llms.txt. "
            "A block on training crawlers does not lower the combined score, but those crawlers should still be allowed "
            "so the content can enter model-training material."
        ),
        "scope_absent": "Not seeing a page type in the sample does not mean it is missing from the whole site.",
        "unevaluated": "Types unevaluated or not seen in scope",
        "fetch_disclosure": "Fetch disclosure",
        "closing_kicker": "08 Closing",
        "closing_h2": "Closing",
        "closing_template": (
            "The combined score is a {label} of {score}/100 ({grade}). {gate} "
            "Recommended first step: {first} "
            "We recommend testing the same sample pages again after changes. "
            "This score is not a search ranking, and it does not guarantee that AI will cite the site."
        ),
        "refs_kicker": "09 Sources",
        "refs_h2": "Reference sources",
        "refs_disclaimer": (
            "The sources below explain the scoring principles. They do not mean these organizations "
            "published or endorse this report’s scores or weights. Each vendor’s statements apply only "
            "to that vendor’s own products. The 40/60 split is this report’s method, not a percentage "
            "published by a vendor."
        ),
        "none": "—",
        "problem": "Problem",
        "impact": "Impact",
        "fix": "Fix",
        "footer": "GEO Checker · Combined package",
        "docfoot": (
            "Beansmile · GEO Checker combined report. "
            "The technical and content scores are shown separately; the combined score is 40% technical and 60% content. "
            "This is not a search ranking or a traffic forecast."
        ),
        "alt_link": "preprint",
    },
    "zh": {
        "html_lang": "zh-CN",
        "doc_title": "GEO 综合报告",
        "cover_kicker": "生成式引擎优化",
        "cover_h1": "GEO 综合报告",
        "cover_sub": "把技术评测和内容评测合在一起，给出总分和优先改进建议。",
        "site": "站点",
        "report_date": "报告日期",
        "tech_label": "技术就绪度",
        "seo_label": "SEO 可发现性",
        "content_label": "内容 GEO",
        "combined_label": "综合分",
        "combined_label_sampled": "抽样页综合分",
        "cover_tech_note": "SEO 已计入技术分",
        "tech_card_sub": "10 项 · 含 SEO 15 分 · 占 40%",
        "content_card_sub": "5 项 · 占 60%",
        "combined_card_sub": "技术 40% + 内容 60%；搜索爬虫被挡住时会设上限",
        "weights_line": "权重：内容 60% · 技术 40%",
        "gate_off": "搜索爬虫可以访问，综合分没有设上限。",
        "gate_hard": "搜索爬虫被挡住，综合分上限为 30。",
        "gate_soft": "部分搜索爬虫被挡住，综合分上限为 50。",
        "cover_what": "这是综合分，不是搜索排名，也不预测访问量或 AI 会不会提到你。",
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
        "intro_h2": "综合分说明",
        "intro_lead": (
            "综合分把技术分和内容分合在一起：技术占 40%，内容占 60%。"
            "如果搜索爬虫被挡住，综合分会有上限。"
            "这不是搜索排名，也不预测访问量或 AI 会不会提到你。"
        ),
        "intro_this_score": (
            "本站{label}为 {score} 分（{grade} 级）。技术分 {tech}/100（{tech_grade}），"
            "内容分 {content}/100（{content_grade}）。{gate}"
        ),
        "intro_tech": "技术侧",
        "intro_content": "内容侧",
        "intro_priority": "建议先做",
        "intro_overlap": (
            "“能抽出的正文偏少”会同时影响技术分和内容分。综合分直接使用这两项已有总分，不再另外扣一次。"
        ),
        "scores_kicker": "02 分数构成",
        "scores_h2": "综合分如何计算",
        "scores_note": (
            "技术分和内容分仍然单独显示。综合分按技术 40%、内容 60% 计算；"
            "如果搜索爬虫被挡住，再设上限。"
        ),
        "formula_label": "本报告采用的算式",
        "formula_text": "综合分 = clamp(0, 100, 按 0.5 分档(0.40 × 技术分 + 0.60 × 内容分))",
        "formula_this": (
            "本次：0.40 × {tech} + 0.60 × {content}，按 0.5 分档后为 {combined} 分（{grade} 级）。{gate}"
        ),
        "formula_missing": "因缺少其中一侧总分，本次不发布综合分。",
        "narrative_kicker": "口径说明",
        "layer1_lead": "技术分看什么",
        "layer1_body": (
            "技术分占综合分的 40%，看网站能不能被抓取和读懂。"
            "如果搜索爬虫被挡住，综合分会有上限。"
            "训练爬虫（如 GPTBot、ClaudeBot）被挡住不会触发这个上限，"
            "但仍建议开放，好让内容进入模型的学习材料。"
        ),
        "layer2_lead": "内容分看什么",
        "layer2_body": (
            "内容分占综合分的 60%，看内容是否清楚、可信，能否回答买家的问题。"
            "网站能被访问之后，内容更能决定 AI 会不会采用这些信息，所以内容权重大一些。"
        ),
        "layer3_lead": "分数怎么读",
        "layer3_body": (
            "技术分和内容分都会单独显示。综合分按技术 40%、内容 60% 计算，再按 0.5 分一档取值。"
            "这是本报告的计算方式。报告最后附有相关的官方说明和论文，供查阅。"
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
            "同一问题在这里只写一次，并注明同时影响技术还是内容。"
            "例如“能抽出的正文偏少”会同时影响两项分数，综合分不再另外扣一次。"
        ),
        "timeline_kicker": "06 统一优先行动与工期",
        "timeline_h2": "两侧合并的下一步与按工作量估算的时间表",
        "timeline_intro": (
            "工期根据本轮发现估算，可按实际情况调整。"
            "先处理访问和页面结构问题，内容建设需要更长时间。改完后，建议用同一批抽样页面再测一次。"
            "下表说明改进方向，不承诺综合分会到某个数字。"
        ),
        "actions_h3": "来自两侧的优先行动",
        "priority": "优先级",
        "action": "行动",
        "owner": "负责人",
        "effort": "工作量",
        "outcome": "验收口径 / 预期结果",
        "days_unit": "天",
        "scope_kicker": "07 范围与披露",
        "scope_h2": "本次检查范围",
        "scope_overlap": (
            "综合分按已有的技术分和内容分计算。"
            "“能抽出的正文偏少”会同时影响这两项分数，综合分不再另外扣一次。"
        ),
        "scope_excluded": (
            "综合分不包含 AI 提到或引用本站的次数，也不计入 llms.txt 等文件。"
            "训练爬虫被挡住不会降低综合分，但仍建议开放，好让内容进入模型的学习材料。"
        ),
        "scope_absent": "抽查范围内没看到某一类页面，不表示全站一定没有。",
        "unevaluated": "未评估或范围内未见的类型",
        "fetch_disclosure": "抓取说明",
        "closing_kicker": "08 结语",
        "closing_h2": "结语",
        "closing_template": (
            "综合分为{label} {score} 分（{grade} 级）。{gate}"
            "建议先做：{first}"
            "改完后，建议用同一批抽样页面再测一次。"
            "本分数不是搜索排名，也不保证 AI 会引用本站。"
        ),
        "refs_kicker": "09 参考来源",
        "refs_h2": "参考来源",
        "refs_disclaimer": (
            "以下资料用于说明评分原则，并不表示这些机构发布或认可本报告的具体分数和权重。"
            "各家说明只适用于其自身产品。40/60 的比例是本报告的计算方法，不是厂商公布的数字。"
        ),
        "none": "—",
        "problem": "问题",
        "impact": "影响",
        "fix": "整改",
        "footer": "GEO Checker · 综合报告",
        "docfoot": (
            "Beansmile · GEO Checker 综合报告。"
            "技术分和内容分单独呈现，综合分按技术 40%、内容 60% 计算。"
            "这不是搜索排名或访问量预测。"
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
    # Tech findings are later merged into the timeline; treat them as already
    # covered so an untranslated SEO copy is not added beside them.
    # Do not pre-seed next_steps here — those still need to be folded in below.
    existing += " " + " ".join(_action_blob(f) for f in (tech.get("findings") or []))
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
            seo_score = snap_half(min(15.0, max(0.0, float(raw) * 15 / 25)))
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

    index_entries = [
        ("cover", index_ui(lang)["cover"]),
        ("conclusion", strip_section_number(S["intro_kicker"])),
        ("scores", strip_section_number(S["scores_kicker"])),
        ("tech", strip_section_number(S["tech_kicker"])),
        ("content", strip_section_number(S["content_kicker"])),
        ("shared", strip_section_number(S["shared_kicker"])),
        ("timeline", strip_section_number(S["timeline_kicker"])),
        ("scope", strip_section_number(S["scope_kicker"])),
        ("closing", strip_section_number(S["closing_kicker"])),
        ("sources", strip_section_number(S["refs_kicker"])),
    ]
    nav_index = index_overlay(index_entries, lang)
    nav_topbar = topbar_index(len(index_entries), lang)
    deck_js = load_deck_js(lang)

    return f"""<!doctype html><html lang="{esc(S['html_lang'])}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(domain)} {esc(S['doc_title'])}</title>
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
  <span class="doc">{esc(domain)} {esc(S['doc_title'])}</span>
  <span class="right"><span class="now mono">{esc(date)}</span>
  {nav_topbar}</span>
</div><div class="progress"><i></i></div></div>

<div class="deck">

<section class="page page-dark cover" id="cover">
  <div class="cover-top"><span class="brand"><b>GEO Checker</b></span>
    <span class="cover-no mono">Beansmile · GEO Checker</span></div>
  <div class="cover-mid">
    <div class="pkicker light">{esc(S['cover_kicker'])}</div>
    <h1>{esc(domain)}<br>{esc(S['cover_h1'])}</h1>
    <p class="cover-sub">{esc(S['cover_sub'])}</p>
    <div class="cover-score">
      <div class="cbig">{esc(combined_disp)}<small>/100</small><em>{esc(combined_label)} {esc(str(combined_grade))}</em></div>
      <div>{meter_html(combined_score, S['pass_label'], S['good_label'])}
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
{nav_index}
<script>{deck_js}</script>
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
