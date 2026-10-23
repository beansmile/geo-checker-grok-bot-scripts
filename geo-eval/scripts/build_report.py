#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 5：report.json → report/*.md + report/*.html

用法:
    python3 build_report.py <run_dir> [--brand 品牌名] [--lang zh|en] [--suffix .zh] [--source report.json]

输入:  <run_dir>/report.json（analyze.py 或 enrich.py 产物）+ ../report_templates/ 模板
输出:  <run_dir>/report/report{suffix}.md + report{suffix}.html

--lang en 使用 report_en.md / report_en.html 模板与英文标签；默认 en（Grok Bot / GEO Checker）。
--suffix 用于同时产出多语言版本（如中文用 --lang zh --suffix .zh，英文不加后缀）。

安全说明：报告正文（标题/问题/影响/解决/维度解读）可能含 <h1>、<title>、<script>
等技术字样。HTML 渲染时按语言单独做一次转义，否则 <title> 这类 raw-text 元素会把
后续整份文档吞成纯文本（表现为报告只渲染出前几页）。Markdown 渲染不做转义。
"""

import html as html_mod
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse

# report.json 没有版本字段时的兜底（旧 run 目录）
VERSION_FALLBACK = "v1.1"


# ---------------------------------------------------------------------------
# 极简 mustache 渲染
# ---------------------------------------------------------------------------

def render(template, data):
    """极简模板渲染：{{var}} 替换；{{#list}}...{{/list}} 循环（{{field}} 取项字段，{{.}} 取项本身）。"""
    def expand_lists(text):
        out = []
        i = 0
        while i < len(text):
            m = re.search(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", text[i:], re.S)
            if not m:
                out.append(text[i:])
                break
            out.append(text[i:i + m.start()])
            key, body = m.group(1), m.group(2)
            items = data.get(key) or []
            for item in items:
                rendered = body
                if isinstance(item, dict):
                    for k, v in item.items():
                        rendered = rendered.replace("{{%s}}" % k, str(v))
                else:
                    rendered = rendered.replace("{{.}}", str(item))
                out.append(rendered)
            i += m.end()
        return "".join(out)

    text = expand_lists(template)

    def sub(m):
        key = m.group(1)
        return str(data.get(key, ""))
    return re.sub(r"\{\{(\w+)\}\}", sub, text)


def load_report(run_dir, source="report.json"):
    p = os.path.join(run_dir, source)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    # 无 LLM 富化时回退到引擎快照
    p = os.path.join(run_dir, "report.engine.json")
    return json.load(open(p, encoding="utf-8"))


# ---------------------------------------------------------------------------
# 语言相关的全部文案
# ---------------------------------------------------------------------------

STRINGS = {
    "zh": {
        "template_md": "report.md",
        "template_html": "report.html",
        "dim_order": [
            ("schema", "结构化数据"),
            ("entity", "品牌与实体一致性"),
            ("ogp", "开放图谱与分享"),
            ("richness", "内容覆盖与新鲜度"),
            ("kg", "站内实体信号"),
            ("absorption", "答案可吸收性"),
            ("trust", "信任度"),
            ("on_page", "页面主题与元数据"),
            ("quality", "内容质量"),
        ],
        "dim_advice": {
            "schema": "结构化数据是「人话的机器副本」，补全组织信息属性（sameAs/简介/联系方式）与列表结构化数据即可，优先度低于实体口径与内容本身。",
            "entity": "先建立实体映射（法定主体→集团→品牌→国际品牌→域名→社交/邮箱），再用「关于我们」页与组织信息结构化数据声明关联；不必强制统一拼写，但每个名称都要指向同一实体。",
            "ogp": "为重要页面单独撰写 og:title/og:description 与 Twitter 标题/描述，避免复用页面拼接文本（次要卫生项，优先度低于内容与实体）。",
            "richness": "围绕买家真实问题建立内容矩阵（交付周期、材料/认证、选型对比、项目案例），而不是机械增加文章数量。",
            "kg": "站内补全官方账号、业务范围、成立日期等声明，并在正文引用权威来源；实体权威的站外证据建议作为后续动作单独推进。",
            "absorption": "把关键内容改写成自包含答案块（先答后述 + 事实/数据），按定义、数据、对比、步骤四类组织内容。",
            "trust": "建立真实作者与资质页、补全团队信息，为数据与资质标注来源；优先解决品牌一致性问题。",
            "on_page": "为页面补齐标题与元描述、修正 H1 与层级；优先清理演示/系统页，而不是在将被移除的页面上改 H1。",
            "quality": "清理模板与占位内容，删除或标注绝对化表述的出处，建立发布前质量检查流程。",
        },
        "grade_label": {"A+": "优秀", "A": "良好", "B": "良好", "C": "一般", "D": "不足", "F": "失败"},
        "sev_labels": {"critical": "严重", "high": "高", "medium": "中", "low": "低"},
        "sev_owner": {
            "critical": ("owner-primary", "贵司确认 + 建站商执行"),
            "high": ("owner-warning", "建站商执行"),
            "medium": ("owner-info", "建站商执行"),
            "low": ("owner-success", "可自行优化"),
        },
        "role_name": {"home": "首页", "content": "正文页", "trust": "信任页", "legal": "合规页", "meta": "索引页"},
        "default_solution": "见上方修复建议。",
        "no_dim_findings": "本维度未单独检出问题；详见「关键发现」章节。",
        "adj_note_none": "<p>本页无加分/扣分条目，总分＝九维合计。</p>",
        "advisory_label": "建议项",
        "advisory_hint": "只提示，不计分",
        "scope_warning_fmt": "必检页面未找到：{items}。相关维度可能因缺页被低估，改进建议中已相应标注。",
        "scope_warning_sep": "、",
        "required_page_name": {"faq": "FAQ 页", "about": "About 页", "contact": "Contact 页", "privacy": "隐私政策页"},
        "evidence_label": "问题内容原文（典型样本）",
        "code_label": "给建站商的参考代码",
        "code_hint": "以下代码给技术人员看，可转发建站公司，不必阅读",
        "copy_label": "复制代码",
        "idx_overall": "总体评价",
        "idx_strengths": "表现良好的部分",
        "idx_method": "评分方法（可复现）",
        "idx_findings": "关键发现",
        "idx_dims": "分维度评估",
        "idx_dim": "维度",
        "idx_actions": "优先改进建议",
        "idx_scope": "检测范围",
        "idx_conclusion": "结论",
        "idx_glossary": "术语人话对照表",
        "step_labels": ["第一步", "第二步", "第三步"],
        "default_next_steps": [
            {"title": "确认主体口径", "body": "由贵司书面确认品牌标准写法、主用邮箱与实体关系。"},
            {"title": "按清单逐项修复", "body": "以「优先改进建议」为准，逐项修复并标注完成。"},
            {"title": "复测核验", "body": "修复后复测本报告口径，看分数与问题是否改善。"},
        ],
        "scope_fmt": (
            "sitemap {sitemap} 个 URL，抽样 {sampled} 个重点页（角色分布：{roles}）；"
            "AI 检索爬虫 {blocked}；llms.txt {llms}。"
        ),
        "scope_blocked_yes": "被 robots.txt 屏蔽",
        "scope_blocked_no": "未被 robots.txt 屏蔽",
        "scope_crawler": {
            "blocked_live": "实测被拦截（WAF/挑战页）",
            "ok_live": "实测可正常抓取",
            "blocked_robots": "被 robots.txt 屏蔽",
            "unknown": "未做实测",
        },
        "scope_llms_yes": "有",
        "scope_llms_no": "无",
        "calc_rule": (
            "九维显示值合计 <b>{dim_sum}</b> → 基础分（保留一位小数）<b>{base}</b> → "
            "本页无加减分，基础分向下取整得最终总分 <b>{overall}</b> / 100（{grade}）。"
        ),
    },
    "en": {
        "template_md": "report_en.md",
        "template_html": "report_en.html",
        "dim_order": [
            ("schema", "Structured data"),
            ("entity", "Brand & entity consistency"),
            ("ogp", "Open Graph & sharing"),
            ("richness", "Content coverage & freshness"),
            ("kg", "On-site entity signals"),
            ("absorption", "Answer absorbability"),
            ("trust", "Trust"),
            ("on_page", "Page topic & metadata"),
            ("quality", "Content quality"),
        ],
        "dim_advice": {
            "schema": "Structured data is the machine-readable copy of what the page already says in prose. Completing the organisation attributes (sameAs, description, contact details) and list markup is worthwhile, but ranks below entity consistency and the content itself.",
            "entity": "Build the entity map (legal entity to brand to domain to social/email), then declare those links via the About page and Organisation structured data. Spelling need not be identical everywhere, but every name must point to the same entity.",
            "ogp": "Write og:title/og:description and Twitter title/description for each important page instead of reusing page-scraped text (a hygiene item, below content and entity in priority).",
            "richness": "Build the content matrix around real buyer questions (lead times, materials and certifications, option comparisons, case studies) rather than mechanically adding more articles.",
            "kg": "Declare official accounts, service scope and founding date on-site, and cite authoritative sources in body copy. Off-site evidence of entity authority is best run as a separate follow-up workstream.",
            "absorption": "Rewrite key content into self-contained answer blocks (answer first, then detail, with facts and figures), organised as definition, data, comparison and steps.",
            "trust": "Publish real author and credential pages, complete the team information, and cite sources for data and qualifications. Fix brand consistency issues first.",
            "on_page": "Give every page a title and meta description, and fix H1 and heading hierarchy. Clear demo and system pages first rather than fixing H1 on pages that will be removed.",
            "quality": "Clean up template and placeholder content, source or remove absolute claims, and add a pre-publish quality check.",
        },
        "grade_label": {"A+": "Excellent", "A": "Good", "B": "Good", "C": "Fair", "D": "Poor", "F": "Failed"},
        "sev_labels": {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"},
        "sev_owner": {
            "critical": ("owner-primary", "Client confirm + web vendor"),
            "high": ("owner-warning", "Web vendor"),
            "medium": ("owner-info", "Web vendor"),
            "low": ("owner-success", "Quick in-house win"),
        },
        "role_name": {"home": "Home", "content": "Content", "trust": "Trust", "legal": "Legal", "meta": "Index"},
        "default_solution": "See the fix above.",
        "no_dim_findings": "No separate issues were detected in this dimension; see the Key findings section.",
        "adj_note_none": "<p>No bonus or penalty applies to this report, so the total equals the nine-dimension sum.</p>",
        "advisory_label": "Advisory",
        "advisory_hint": "listed, not scored",
        "scope_warning_fmt": "Required pages not found: {items}. The related dimensions may be understated; improvement notes reflect this.",
        "scope_warning_sep": ", ",
        "required_page_name": {"faq": "FAQ page", "about": "About page", "contact": "Contact page", "privacy": "Privacy policy"},
        "evidence_label": "Evidence — original text (typical samples)",
        "code_label": "Reference code for your web vendor",
        "code_hint": "For technical staff — forward to your web vendor; no need to read",
        "copy_label": "Copy code",
        "idx_overall": "Overall assessment",
        "idx_strengths": "What's already working",
        "idx_method": "Scoring method (reproducible)",
        "idx_findings": "Key findings",
        "idx_dims": "Dimension assessment",
        "idx_dim": "Dimension",
        "idx_actions": "Priority actions",
        "idx_scope": "Scope",
        "idx_conclusion": "Conclusion",
        "idx_glossary": "Glossary",
        "step_labels": ["Step 1", "Step 2", "Step 3"],
        "default_next_steps": [
            {"title": "Fix discovery and homepage machine signals", "body": "Ship a real sitemap.xml and Markdown llms.txt, then add Organisation JSON-LD, Open Graph tags, and a unique H1 on the homepage."},
            {"title": "Work through the action list", "body": "Apply the Priority actions in order — paste-ready reference code is on each finding page."},
            {"title": "Re-run GEO Checker", "body": "After the fixes, re-run this assessment to see whether the score and issue count improve."},
        ],
        "scope_fmt": (
            "{sitemap} URLs in the sitemap, {sampled} key pages sampled (role mix: {roles}); "
            "AI retrieval crawlers {blocked}; llms.txt: {llms}."
        ),
        "scope_blocked_yes": "blocked by robots.txt",
        "scope_blocked_no": "not blocked by robots.txt",
        "scope_crawler": {
            "blocked_live": "blocked in testing (WAF / challenge page)",
            "ok_live": "fetchable in testing",
            "blocked_robots": "blocked by robots.txt",
            "unknown": "not live-tested",
        },
        "scope_llms_yes": "present",
        "scope_llms_no": "absent",
        "calc_rule": (
            "Displayed dimension scores total <b>{dim_sum}</b> → base score (1 decimal place) "
            "<b>{base}</b> → with no bonus or penalty on this page, the base score is rounded "
            "down to a whole number for the final score: <b>{overall}</b> / 100 ({grade})."
        ),
    },
}

_SEV_KEY = {
    "严重": "critical", "高": "high", "中": "medium", "低": "low",
    "critical": "critical", "high": "high", "medium": "medium", "low": "low",
    "Critical": "critical", "High": "high", "Medium": "medium", "Low": "low",
}

SEV_CLASS_BY_KEY = {
    "critical": "sev-danger",
    "high": "sev-warning",
    "medium": "sev-info",
    "low": "sev-muted",
}

GRADE_META = {
    "A+": ("#16a34a", "c-success", "g-success", "var(--success)"),
    "A": ("#16a34a", "c-success", "g-success", "var(--success)"),
    "B": ("#2563eb", "c-info", "g-info", "var(--info)"),
    "C": ("#d97706", "c-warning", "g-warning", "var(--warning)"),
    "D": ("#dc2626", "c-danger", "g-danger", "var(--danger)"),
    "F": ("#dc2626", "c-danger", "g-danger", "var(--danger)"),
}


def grade_meta(g):
    return GRADE_META.get(g, GRADE_META["D"])


# 关键发现 → 维度：优先用 finding 自带 dim/dimension/domain，否则按关键词推断
_DIM_KEYWORDS = {
    "schema": ["schema", "organization", "json-ld", "结构化", "logo", "@id", "productgroup",
               "publisher", "website", "contactpoint", "itemlist", "searchaction", "structured data",
               "aggregaterating", "faqpage", "medicalbusiness", "localbusiness", "postaladdress"],
    "entity": ["品牌写法", "邮箱域名", "公司名", "实体", "brand", "entity", "邮箱", "电话", "email",
               "consistency", "legal entity"],
    "ogp": ["og:", "开放图谱", "twitter", "分享", "ogp", "open graph", "og:image", "share card"],
    "richness": ["faq 页", "文章数量", "指南", "发布时间", "新鲜度", "datepublished", "内容覆盖",
                 "faq 问答", "内容资产", "llms.txt", "article count", "content coverage", "freshness"],
    "kg": ["sameas", "knowsabout", "权威", "外链", "官方账号", "业务范围", "成立日期",
           "foundingdate", "实体信号", "外部引用", "knowledge graph", "authority", "outbound"],
    "absorption": ["答案块", "可引用", "吸收", "证据块", "列表/表格", "首屏", "对题", "答案", "引用",
                   "answer block", "quotable", "absorb", "self-contained"],
    "trust": ["作者", "信任", "about", "contact", "合规", "团队", "资质", "爬虫", "默认模板",
              "robots", "author", "trust", "credential", "privacy", "compliance", "review"],
    "on_page": ["h1", "标题", "元描述", "canonical", "层级", "title", "meta", "标题层级",
                "heading", "metadata"],
    "quality": ["占位", "lorem", "计数器", "演示页", "索引膨胀", "重复", "模板", "绝对化", "空链接",
                "0 值", "placeholder", "duplicate", "template", "boilerplate"],
}

# 精确短语优先（避免关键词歧义/漏配）
_DIM_EXACT = [
    ("公司法定名", "entity"),
    ("结构化答案资产", "absorption"),
    ("列表/表格", "absorption"),
    ("发布时间信号", "richness"),
    ("合规页", "trust"),
    ("robots", "trust"),
    ("答案块", "absorption"),
    ("可引用", "absorption"),
    ("answer block", "absorption"),
    ("quotable", "absorption"),
    ("privacy policy", "trust"),
]


def dimension_key_for(f, dim_order):
    valid = dict(dim_order)
    key = f.get("dim") or f.get("dimension") or f.get("domain") or f.get("dim_key")
    if key and key in valid:
        return key
    hay = ((f.get("title") or "") + " " + (f.get("problem") or "")).lower()
    for phrase, k in _DIM_EXACT:
        if phrase.lower() in hay:
            return k
    for k, kws in _DIM_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in hay:
                return k
    return "absorption"


# ---------------------------------------------------------------------------
# flatten
# ---------------------------------------------------------------------------

def flatten(report, brand, lang="zh", escape_html=False):
    S = STRINGS[lang]
    DIM_ORDER = S["dim_order"]
    DIM_ADVICE = S["dim_advice"]
    dims = {d["key"]: d for d in report.get("dimensions", [])}
    details = {d["key"]: d.get("detail", "") for d in report.get("dimension_details", [])}
    # 站点专属「提升建议」覆盖（LLM 富化时写入 dimension_details[].advice）；
    # 缺省回退到通用建议 DIM_ADVICE（通用建议面向制造业，可能与本站在实际情况不符）
    advices = {d["key"]: (d.get("advice") or "") for d in report.get("dimension_details", [])}

    # HTML 模式下对正文做一次转义；Markdown 模式保持原文
    E = html_mod.escape if escape_html else (lambda s: s)

    # ---------- findings ----------
    findings = []
    for idx, f in enumerate(report.get("findings", []), 1):
        ev = f.get("evidence") or []
        ev_parts = []
        ev_md_parts = []
        ev_rows = []
        for e in ev:
            url = e.get("url") or ""
            quote = (e.get("quote") or "").strip()
            if not (url or quote):
                continue
            url_disp = url or ("site" if lang == "en" else "站点")
            url_txt = html_mod.escape(str(url_disp))
            quote_txt = html_mod.escape(str(quote))
            ev_parts.append(f"{url_disp}「{quote}」" if quote else url_disp)
            ev_md_parts.append(f"- `{url_disp}`「{quote}」" if quote else f"- `{url_disp}`")
            ev_rows.append(
                f'<li><code class="mono">{url_txt}</code><span>{quote_txt}</span></li>'
            )

        raw_title = f.get("title") or ""
        raw_problem = f.get("problem") or raw_title
        raw_impact = f.get("impact") or raw_problem
        raw_solution = f.get("solution") or S["default_solution"]
        code = f.get("code") or ""

        sev_key = _SEV_KEY.get(f.get("severity", "low"), "low")
        sev = S["sev_labels"][sev_key]
        sc = SEV_CLASS_BY_KEY[sev_key]
        owner_cls, owner_txt = S["sev_owner"][sev_key]
        # scored=False：只报不评的建议项（权威外链、内页 OGP、单一 off-domain 邮箱）。
        # 展示 Advisory 徽标，且不计入封面严重度色带。
        scored = f.get("scored", True) is not False
        advisory_span = "" if scored else f'<span class="sev sev-advisory" title="{S["advisory_hint"]}">{S["advisory_label"]}</span>'
        evcount = len(ev_rows)

        evidence_html = ""
        if ev_rows:
            evidence_html = (
                f'<div class="evrow"><span class="evlab">{S["evidence_label"]}</span>'
                f'<ul class="evlist">{"".join(ev_rows)}</ul></div>'
            )
        code_html = ""
        if code:
            code_html = (
                f'<div class="sublab">{S["code_label"]}'
                f'<span class="hint">{S["code_hint"]}</span></div>'
                f'<div class="codewrap"><div class="codebar"><span class="mono">{S["code_label"]}</span>'
                f'<button class="copy" type="button">{S["copy_label"]}</button></div>'
                f'<pre class="mono">{html_mod.escape(code)}</pre></div>'
            )

        findings.append({
            **f,
            "n": f"{idx:02d}",
            "dim_key": dimension_key_for(f, DIM_ORDER),
            "severity": sev,
            "severity_key": sev_key,
            "severity_display": sev if scored else f'{sev} · {S["advisory_label"]}',
            "scored": scored,
            "sev_class": sc,
            "sev_span": f'<span class="sev {sc}">{sev}</span>{advisory_span}',
            "owner_class": owner_cls,
            "owner": owner_txt,
            "evcount": evcount,
            "evidence_html": evidence_html,
            "evidence_md": "\n".join(ev_md_parts),
            "code_html": code_html,
            "code_md": (f"\n```html\n{code}\n```\n" if code else ""),
            "title": E(raw_title),
            "impact": E(raw_impact),
            "solution": E(raw_solution),
            "problem": E(raw_problem),
        })

    # 严重度分布（封面 severity strip）：只统计 scored=True 的项。
    # 建议项既然不计分，就不应该出现在「问题构成」里，否则读者会误以为已扣分。
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        if not f["scored"]:
            continue
        k = f["severity_key"]
        sev_counts[k] = sev_counts.get(k, 0) + 1
    total_f = max(1, sum(sev_counts.values()))
    scored_total = sum(sev_counts.values())
    advisory_total = len(findings) - scored_total
    sev_strip = (
        f'<span class="ss ss-danger" style="width:{sev_counts["critical"] / total_f * 100:.1f}%"></span>'
        f'<span class="ss ss-warning" style="width:{sev_counts["high"] / total_f * 100:.1f}%"></span>'
        f'<span class="ss ss-info" style="width:{sev_counts["medium"] / total_f * 100:.1f}%"></span>'
        f'<span class="ss ss-muted" style="width:{sev_counts["low"] / total_f * 100:.1f}%"></span>'
    )
    L = S["sev_labels"]
    if lang == "en":
        advisory_suffix = f" · {advisory_total} advisory" if advisory_total else ""
        sev_legend = (
            f'<span><i class="dot d-danger"></i>{L["critical"]} <b>{sev_counts["critical"]}</b></span>'
            f'<span><i class="dot d-warning"></i>{L["high"]} <b>{sev_counts["high"]}</b></span>'
            f'<span><i class="dot d-info"></i>{L["medium"]} <b>{sev_counts["medium"]}</b></span>'
            f'<span><i class="dot d-muted"></i>{L["low"]} <b>{sev_counts["low"]}</b></span>'
            f'<span class="dim">{scored_total} scored{advisory_suffix}</span>'
        )
    else:
        advisory_suffix = f"（另有 {advisory_total} 项建议）" if advisory_total else ""
        sev_legend = (
            f'<span><i class="dot d-danger"></i>{L["critical"]} <b>{sev_counts["critical"]}</b></span>'
            f'<span><i class="dot d-warning"></i>{L["high"]} <b>{sev_counts["high"]}</b></span>'
            f'<span><i class="dot d-info"></i>{L["medium"]} <b>{sev_counts["medium"]}</b></span>'
            f'<span><i class="dot d-muted"></i>{L["low"]} <b>{sev_counts["low"]}</b></span>'
            f'<span class="dim">共 {scored_total} 项{advisory_suffix}</span>'
        )

    # ---------- 页码布局 ----------
    N = len(findings)
    M = len(DIM_ORDER)
    total_pages = 12 + N + M
    p_dims_index = 8 + N
    p_actions = 9 + N + M
    p_scope = 10 + N + M
    p_conclusion = 11 + N + M
    p_glossary = 12 + N + M

    for i, f in enumerate(findings):
        page = 8 + i
        f["page"] = page
        f["page_pad"] = f"{page:02d}"
        f["anchor"] = f"p{page}"

    # ---------- dimensions ----------
    dim_pages = []
    for j, (key, name) in enumerate(DIM_ORDER):
        d = dims.get(key, {})
        # 显示值统一保留 2 位（6.7149… → 6.71），pct 用同一数值计算，保证报告内部自洽
        score = round(float(d.get("score", 0) or 0), 2)
        maxv = d.get("max", 0)
        grade = d.get("grade", "D") or "D"
        pct = round(score / maxv * 100, 1) if maxv else 0
        color, c_class, g_class, bar_var = grade_meta(grade)
        page = 9 + N + j
        anchor = f"p{page}"
        # 本维度分组 findings
        gfindings = [f for f in findings if f["dim_key"] == key]
        gf_html = ""
        gf_md = ""
        for gf in gfindings:
            gf_html += (
                '<div class="frow"><div class="frow-h">' + gf["sev_span"] +
                f'<h4>{gf["title"]}</h4></div>'
                f'<p class="fix">{gf["solution"]}</p>{gf["evidence_html"]}{gf["code_html"]}</div>'
            )
            gf_md += (
                f"### [{gf['severity_display']}] {gf.get('_raw_title', gf['title'])}\n\n"
                f"{gf['solution']}\n\n"
                f"{gf.get('evidence_md', '')}\n"
                f"{gf.get('code_md', '')}\n"
            )
        if not gfindings:
            gf_html = f'<p class="fix">{S["no_dim_findings"]}</p>'
            gf_md = f"_{S['no_dim_findings']}_\n"

        dim_pages.append({
            "n": f"{j + 1:02d}",
            "idx": f"{j + 1:02d} / {M:02d}",
            "key": key,
            "name": name,
            "score": f"{score:g}",
            "max": maxv,
            "grade": grade,
            "pct": pct,
            "remaining": round(100 - pct, 1),
            "color": color,
            "c_class": c_class,
            "g_class": g_class,
            "bar": bar_var,
            "page": page,
            "page_pad": f"{page:02d}",
            "anchor": anchor,
            "narr": E(details.get(key, "") or DIM_ADVICE.get(key, "")),
            "callout": E(advices.get(key) or DIM_ADVICE.get(key, "")),
            "findings_html": gf_html,
            "findings_md": gf_md,
        })

    # ---------- 目录 / 索引 ----------
    toc_findings_html = "".join(
        f'<li><span class="n mono">{f["n"]}</span>{f["sev_span"]}'
        f'<a href="#{f["anchor"]}">{f["title"]}</a><span class="dots"></span></li>'
        for f in findings
    )
    toc_dims_html = "".join(
        f'<li><span class="n mono">{d["n"]}</span><a href="#{d["anchor"]}">{html_mod.escape(d["name"])}</a>'
        f'<span class="dots"></span><span class="c mono">{d["score"]}/{d["max"]} · {d["grade"]}</span></li>'
        for d in dim_pages
    )

    # 右上角弹层索引（含固定章节 + 动态 findings/dims）
    index_html = (
        f'<a href="#p4"><span class="mono">04</span>{S["idx_overall"]}</a>'
        f'<a href="#p5"><span class="mono">05</span>{S["idx_strengths"]}</a>'
        f'<a href="#p6"><span class="mono">06</span>{S["idx_method"]}</a>'
        f'<a href="#p7"><span class="mono">07</span>{S["idx_findings"]}</a>'
        + "".join(
            f'<a href="#{f["anchor"]}"><span class="mono">{f["page"]:02d}</span>'
            f'{S["idx_findings"]} {f["n"]} · {f["title"]}</a>'
            for f in findings
        )
        + f'<a href="#p{p_dims_index}"><span class="mono">{p_dims_index:02d}</span>{S["idx_dims"]}</a>'
        + "".join(
            f'<a href="#{d["anchor"]}"><span class="mono">{d["page"]:02d}</span>'
            f'{S["idx_dim"]} {d["n"]} · {html_mod.escape(d["name"])}</a>'
            for d in dim_pages
        )
        + f'<a href="#p{p_actions}"><span class="mono">{p_actions:02d}</span>{S["idx_actions"]}</a>'
        f'<a href="#p{p_scope}"><span class="mono">{p_scope:02d}</span>{S["idx_scope"]}</a>'
        f'<a href="#p{p_conclusion}"><span class="mono">{p_conclusion:02d}</span>{S["idx_conclusion"]}</a>'
        f'<a href="#p{p_glossary}"><span class="mono">{p_glossary:02d}</span>{S["idx_glossary"]}</a>'
    )

    # ---------- 优先改进建议 action rows ----------
    action_rows = [
        {
            "sev_class": f["sev_class"],
            "sev": f["severity_display"],
            "sev_span": f["sev_span"],
            "action": f["title"],
            "detail": f["solution"],
            "owner": f["owner"],
            "owner_class": f["owner_class"],
        }
        for f in findings
    ]

    # ---------- adjustments ----------
    adj_rows = [
        {
            "type": "加分" if (a.get("points") or 0) > 0 else "扣分",
            "points": f"{'+' if (a.get('points') or 0) > 0 else ''}{a.get('points', 0)}",
            "reason": E(a.get("reason", "")),
        }
        for a in report.get("adjustments", [])
    ]
    if lang == "en":
        for r in adj_rows:
            r["type"] = "Bonus" if r["points"].startswith("+") else "Penalty"
    bonus = report.get("bonus", 0)
    penalty = report.get("penalty", 0)

    # ---------- scope ----------
    scope = report.get("scope", {})
    role_counts = scope.get("role_counts", {})
    roles = " / ".join(f"{k}={v}" for k, v in sorted(role_counts.items()))
    role_name = S["role_name"]
    scope_bars = "".join(
        f'<span class="sb sb-primary" style="width:{v / max(1, scope.get("sampled_count", 1)) * 100:.1f}%" '
        f'title="{role_name.get(k, k)}: {v}"></span>'
        for k, v in sorted(role_counts.items())
    )
    scope_legend = "".join(
        f'<span><i class="dot d-primary"></i>{role_name.get(k, k)} <b>{v}</b></span>'
        for k, v in sorted(role_counts.items())
    )
    # 爬虫状态优先取实测结果：robots.txt 放行不等于能抓到
    _cr = scope.get("crawler_access") or {}
    if _cr.get("reachable") is False or _cr.get("ai_blocked") or _cr.get("waf_challenge"):
        _crawler_state = S["scope_crawler"]["blocked_live"]
    elif _cr.get("reachable") is True:
        _crawler_state = S["scope_crawler"]["ok_live"]
    elif scope.get("blocked"):
        _crawler_state = S["scope_crawler"]["blocked_robots"]
    else:
        _crawler_state = S["scope_crawler"]["unknown"]
    scope_text = S["scope_fmt"].format(
        sitemap=scope.get("sitemap_count", 0),
        sampled=scope.get("sampled_count", 0),
        roles=roles or "—",
        blocked=_crawler_state,
        llms=S["scope_llms_yes"] if scope.get("has_llms") else S["scope_llms_no"],
    )
    scope_note = scope.get("note") or ""
    scope_note_html = f'<p class="note">{E(scope_note)}</p>' if scope_note else ""

    # 必检页缺失提示（run.py 后置补入时的 scope 警告）：告诉读者为什么某些维度可能偏低。
    missing_required = []
    for warning in (scope.get("scope_warnings") or []):
        if isinstance(warning, dict):
            name = warning.get("required") or ""
        else:
            name = str(warning).split(":")[-1].strip()
        if name:
            missing_required.append(S["required_page_name"].get(name, name))
    scope_warning_text = ""
    scope_warning_html = ""
    if missing_required:
        scope_warning_text = S["scope_warning_fmt"].format(items=S["scope_warning_sep"].join(missing_required))
        scope_warning_html = f'<p class="note scope-warning">{E(scope_warning_text)}</p>'

    # 结论页「下一步」：report.json 可用 next_steps 覆盖（站点定制），否则用默认三步
    _raw_steps = report.get("next_steps") or S["default_next_steps"]
    _labels = S["step_labels"]
    next_steps = [
        {
            "label": _labels[i] if i < len(_labels) else "",
            "title": E(st.get("title", "")),
            "body": E(st.get("body", "")),
        }
        for i, st in enumerate(_raw_steps)
    ]

    # 总评分数色阶（与分维一致：按等级取色，避免 A 级仍显示红色）
    _o_grade = report.get("grade", "D")
    _o_color, overall_c_class, overall_g_class, _o_bar = grade_meta(_o_grade)

    # 九维显示值的精确合计（去尾零：62.34 / 62.0 -> 62）
    _ds = sum(float(d.get("score", 0) or 0) for d in report.get("dimensions", []))
    dim_sum = f"{_ds:.2f}".rstrip("0").rstrip(".")

    _fallback = "this site" if lang == "en" else "本站"
    data = {
        "brand": brand or urlparse(report.get("url", "")).hostname or _fallback,
        "domain": urlparse(report.get("url", "")).hostname or _fallback,
        "url": report.get("url", ""),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "report_id": f"GEO-{datetime.now().strftime('%Y%m%d')}",
        # 口径版本从 report.json 读，不再在模板里硬编码「规则 1.0」
        "rules_version": (report.get("versions") or {}).get("rules_version", VERSION_FALLBACK),
        "scoring_version": (report.get("versions") or {}).get("scoring_version", VERSION_FALLBACK),
        "overall_score": report.get("overall_score", 0),
        "grade": report.get("grade", "D"),
        "grade_label": S["grade_label"].get(report.get("grade", "D"), ""),
        "overall_c_class": overall_c_class,
        "overall_g_class": overall_g_class,
        "base_score": report.get("base_score", 0),
        # 九维「显示值」的精确合计：让评分方法页的表格能自洽（列加起来 = 打印出来的合计）
        "dim_sum": dim_sum,
        # 总分/基础分的整数显示（避免 62.3 之类小数进入面向客户的表头）
        "bonus": f"+{bonus}" if bonus else ("none" if lang == "en" else "无"),
        "penalty": f"-{penalty}" if penalty else ("none" if lang == "en" else "无"),
        "ceiling_note": report.get("ceiling_note", ""),
        "ceiling_block": (f'<p>{E(report.get("ceiling_note", ""))}</p>'
                          if report.get("ceiling_note") else ""),
        "calc_rule": S["calc_rule"].format(dim_sum=dim_sum,
                                           base=report.get("base_score", 0),
                                           overall=report.get("overall_score", 0),
                                           grade=report.get("grade", "D")),
        # closing / overall_summary 允许含 <strong>/<br>，两种语言都不转义
        "closing": report.get("closing", ""),
        "overall_summary": report.get("overall_summary", report.get("closing", "")),
        "sitemap_count": report.get("sitemap_count", 0),
        "sampled_count": report.get("sampled_count", 0),
        "total_pages": total_pages,
        "total_pages_pad": f"{total_pages:02d}",
        "p_dims_index": p_dims_index,
        "p_actions": p_actions,
        "p_scope": p_scope,
        "p_conclusion": p_conclusion,
        "p_glossary": p_glossary,
        "p_dims_index_pad": f"{p_dims_index:02d}",
        "p_actions_pad": f"{p_actions:02d}",
        "p_scope_pad": f"{p_scope:02d}",
        "p_conclusion_pad": f"{p_conclusion:02d}",
        "p_glossary_pad": f"{p_glossary:02d}",
        "findings": findings,
        "findings_count": N,
        "scored_findings_count": scored_total,
        "advisory_count": advisory_total,
        "sev_strip": sev_strip,
        "sev_legend": sev_legend,
        "toc_findings_html": toc_findings_html,
        "toc_dims_html": toc_dims_html,
        "index_html": index_html,
        "dim_pages": dim_pages,
        # 仅在确实没有加减分项时提示「总分＝九维合计」，避免与已列出的扣分并存造成误读
        "adj_note": (S["adj_note_none"] if not adj_rows else ""),
        "action_rows": action_rows,
        "next_steps": next_steps,
        "adj_rows": adj_rows,
        "strengths": [E(s) for s in report.get("strengths", [])],
        "scope_text": scope_text,
        "scope_note_text": scope_note,
        "scope_note_html": scope_note_html,
        "scope_warning_text": scope_warning_text,
        "scope_warning_html": scope_warning_html,
        "scope_bars": scope_bars,
        "scope_legend": scope_legend,
    }
    return data


def main():
    args = sys.argv[1:]
    run_dir = args[0] if args else "."
    brand = None
    if "--brand" in args:
        brand = args[args.index("--brand") + 1]
    lang = args[args.index("--lang") + 1] if "--lang" in args else "en"
    suffix = args[args.index("--suffix") + 1] if "--suffix" in args else ""
    source = args[args.index("--source") + 1] if "--source" in args else "report.json"
    if lang not in STRINGS:
        print(f"[build_report] 未知语言 {lang!r}，可选 {sorted(STRINGS)}")
        sys.exit(2)

    report = load_report(run_dir, source)
    S = STRINGS[lang]

    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl_dir = os.path.join(skill_root, "report_templates")
    style = open(os.path.join(tpl_dir, "style.css"), encoding="utf-8").read()
    deck_js = open(os.path.join(tpl_dir, "deck.js"), encoding="utf-8").read()

    out_dir = os.path.join(run_dir, "report")
    os.makedirs(out_dir, exist_ok=True)

    # Markdown：正文保持原文（不转义），否则代码与 <h1> 字样会变成实体
    data_md = flatten(report, brand, lang=lang, escape_html=False)
    tpl_md = open(os.path.join(tpl_dir, S["template_md"]), encoding="utf-8").read()
    md = render(tpl_md, data_md)
    md_path = os.path.join(out_dir, f"report{suffix}.md")
    open(md_path, "w", encoding="utf-8").write(md)
    print(f"wrote {md_path} ({len(md)} chars)")

    # HTML：正文按语言单独转义一次（防止 <title> 等 raw-text 元素吞掉后续文档）
    data_html = flatten(report, brand, lang=lang, escape_html=True)
    data_html["style"] = style
    if lang == "en":
        deck_js = deck_js.replace("已复制", "Copied")
    data_html["script"] = deck_js
    tpl_html = open(os.path.join(tpl_dir, S["template_html"]), encoding="utf-8").read()
    html = render(tpl_html, data_html)
    html_path = os.path.join(out_dir, f"report{suffix}.html")
    open(html_path, "w", encoding="utf-8").write(html)
    print(f"wrote {html_path} ({len(html)} chars)")


if __name__ == "__main__":
    main()
