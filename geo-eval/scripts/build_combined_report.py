#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a combined GEO Checker HTML report from technical + content packages.

Usage:
    python3 scripts/build_combined_report.py <tech_run_dir> [--content-run <content_run_dir>]
        [--lang en|zh] [--out-dir <dir>] [--brand NAME]

Defaults:
  - Content JSON is read from the same run dir if present, else --content-run is required.
  - Writes report/combined_report.html (or combined_report.zh.html when --lang zh).
  - Client deliverable is HTML only (no .md).

Scores stay separate: technical /100, SEO discoverability /25, Content GEO /100.
Never invent a single merged total. Never invent AI engine quotes.
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


STRINGS = {
    "en": {
        "doc_title": "Combined GEO Report",
        "cover_kicker": "Generative Engine Optimization · Combined package",
        "cover_h1": "Combined GEO Report",
        "cover_sub": (
            "This package brings together the technical on-site readiness evaluation "
            "(nine dimensions + SEO content discoverability) and the Content GEO evaluation "
            "(architecture, taxonomy, writing, authority evidence, buyer-question coverage). "
            "Scores are reported separately so each track stays actionable."
        ),
        "site": "Site",
        "report_date": "Report date",
        "tech_label": "Technical readiness",
        "seo_label": "SEO discoverability",
        "content_label": "Content GEO",
        "grade_scale": "Grade scale",
        "intro_kicker": "01 Purpose",
        "intro_h2": "What this combined report is for",
        "intro_body": (
            "Use this report as an executive package: see the technical crawl/readiness picture, "
            "the SEO content discoverability picture, and the content architecture / buyer-question "
            "picture side by side, then follow one phased remediation timeline. "
            "<strong>GEO = Generative Engine Optimization</strong> (websites), not geography. "
            "Detailed evidence lives in the standalone technical and Content GEO HTML reports."
        ),
        "scores_kicker": "02 Score snapshot",
        "scores_h2": "Three scores, kept separate",
        "scores_note": (
            "Technical readiness is /100 (nine dimensions). SEO content discoverability is /25 "
            "and is not added into the technical 100. Content GEO is /100 across five dimensions. "
            "Do not average or sum these into a single total."
        ),
        "max": "Max",
        "grade": "Grade",
        "track": "Track",
        "score": "Score",
        "confidence": "Confidence",
        "tech_kicker": "03 Technical highlights",
        "tech_h2": "On-site readiness & SEO discoverability",
        "tech_nine": "Nine-dimension readiness",
        "tech_seo": "SEO content discoverability",
        "provisional": "Provisional / crawl limited",
        "strengths": "Strengths",
        "key_findings": "Key findings",
        "content_kicker": "04 Content GEO highlights",
        "content_h2": "Architecture, writing, evidence & questions",
        "dimensions": "Dimensions",
        "shared_kicker": "05 Shared findings",
        "shared_h2": "Issues that span both tracks",
        "timeline_kicker": "06 Remediation timeline",
        "timeline_h2": "Suggested phased plan (W0–W16)",
        "timeline_intro": (
            "Suggested calendar assuming a focused remediation team. Adjust owners and "
            "durations to your capacity; re-test after W16 against the same question set."
        ),
        "phase": "Phase",
        "weeks": "Weeks",
        "focus": "Focus",
        "work": "Work items",
        "owner": "Owner",
        "outcome": "Expected outcome",
        "actions_kicker": "07 Priority actions",
        "actions_h2": "Ordered next steps from both tracks",
        "scope_kicker": "08 Scope & disclosure",
        "scope_h2": "What was evaluated",
        "closing": "Conclusion",
        "footer": "GEO Checker · Combined package",
        "docfoot": (
            "Combined GEO package by Beansmile · GEO Checker. Technical, SEO discoverability, "
            "and Content GEO scores are reported separately — not rankings, traffic, or guaranteed AI mentions."
        ),
        "problem": "Problem",
        "impact": "Impact",
        "fix": "Fix",
        "none": "—",
        "fetch_disclosure": "Fetch disclosure",
        "phases": [
            {
                "id": "W0-W2",
                "weeks": "W0–W2",
                "focus": "Crawl & HTTPS stability",
                "owner": "eng / ops",
                "outcome": "Live HTML, robots, and sitemap verifiable; technical re-score possible",
                "default_items": [
                    "Restore stable HTTP(S) responses (fix 500 / TLS failures)",
                    "Allowlist Googlebot, Bingbot, OAI-SearchBot; confirm in access logs / GSC",
                    "Verify robots.txt and sitemap.xml are reachable",
                ],
            },
            {
                "id": "W3-W4",
                "weeks": "W3–W4",
                "focus": "Titles, thin pages, internal paths",
                "owner": "content / eng",
                "outcome": "Unique title/H1/meta; thinner pages upgraded or consolidated",
                "default_items": [
                    "Unique title / H1 / meta description per important URL",
                    "Upgrade or consolidate thin product and case pages",
                    "Strengthen hub → product / case internal links",
                ],
            },
            {
                "id": "W5-W8",
                "weeks": "W5–W8",
                "focus": "Evergreen GEO answer pages",
                "owner": "content",
                "outcome": "Intent-matched pages for losing non-branded procurement questions",
                "default_items": [
                    "Ship 3+ evergreen answer-first pages mapped to losing buyer questions",
                    "Rebuild product templates with specs, modules, and standards",
                ],
            },
            {
                "id": "W9-W12",
                "weeks": "W9–W12",
                "focus": "Proof hub & case narratives",
                "owner": "content / PR",
                "outcome": "On-site authority evidence that generative engines can cite",
                "default_items": [
                    "Launch proof hubs (awards, patents, qualifications) with source links",
                    "Upgrade top project cases to full narratives with measurable outcomes",
                    "Unify brand / entity naming across pages",
                ],
            },
            {
                "id": "W13-W16",
                "weeks": "W13–W16",
                "focus": "Export language & re-test",
                "owner": "content / GEO lead",
                "outcome": "EN intent coverage for export buyers; refreshed GEO scores",
                "default_items": [
                    "Add English intent pages for export / international buyers",
                    "Re-run technical + Content GEO evaluation on the same question set",
                    "Compare AI / search visibility checks against the baseline",
                ],
            },
        ],
    },
    "zh": {
        "doc_title": "GEO 综合评测报告",
        "cover_kicker": "生成式引擎优化 · 综合包",
        "cover_h1": "GEO 综合评测报告",
        "cover_sub": (
            "本综合包汇总技术侧站内就绪评测（九维 + SEO 内容可发现性）与内容侧 Content GEO 评测"
            "（信息架构、分类与缺口、编写质量、权威证据、采购问题覆盖）。"
            "各项分数分开呈现，便于分别整改。"
        ),
        "site": "站点",
        "report_date": "报告日期",
        "tech_label": "技术就绪度",
        "seo_label": "SEO 可发现性",
        "content_label": "内容 GEO",
        "grade_scale": "等级刻度",
        "intro_kicker": "01 用途说明",
        "intro_h2": "这份综合报告用来做什么",
        "intro_body": (
            "把它当作管理层可读的总包：并排查看技术抓取/就绪情况、SEO 内容可发现性、"
            "以及内容架构/采购问题覆盖，再按同一套分阶段整改时间表推进。"
            "<strong>GEO = 生成式引擎优化</strong>（网站），不是地理。"
            "完整证据仍以独立的技术报告与内容 GEO 报告为准。"
        ),
        "scores_kicker": "02 分数快照",
        "scores_h2": "三项分数，分开记录",
        "scores_note": (
            "技术就绪度为 /100（九维）。SEO 内容可发现性为 /25，不并入技术百分制。"
            "内容 GEO 为 /100（五维）。请勿把三项平均或加总成一个总分。"
        ),
        "max": "满分",
        "grade": "等级",
        "track": "轨道",
        "score": "得分",
        "confidence": "置信度",
        "tech_kicker": "03 技术侧重点",
        "tech_h2": "站内就绪度与 SEO 可发现性",
        "tech_nine": "九维就绪度",
        "tech_seo": "SEO 内容可发现性",
        "provisional": "暂定 / 抓取受限",
        "strengths": "已有基础",
        "key_findings": "关键发现",
        "content_kicker": "04 内容 GEO 重点",
        "content_h2": "架构、写作、证据与问题覆盖",
        "dimensions": "维度",
        "shared_kicker": "05 共通发现",
        "shared_h2": "跨轨道共性问题",
        "timeline_kicker": "06 建议整改时间表",
        "timeline_h2": "分阶段计划（W0–W16）",
        "timeline_intro": (
            "以下为聚焦整改团队的建议日历。可按实际产能调整负责人与周期；"
            "W16 后用同一套问题集复测。"
        ),
        "phase": "阶段",
        "weeks": "周次",
        "focus": "重点",
        "work": "工作项",
        "owner": "负责人",
        "outcome": "预期结果",
        "actions_kicker": "07 优先行动",
        "actions_h2": "来自两侧的有序下一步",
        "scope_kicker": "08 范围与披露",
        "scope_h2": "本次评测覆盖范围",
        "closing": "结论",
        "footer": "GEO Checker · 综合包",
        "docfoot": (
            "Beansmile · GEO Checker 综合包。技术、SEO 可发现性与内容 GEO 分数分开呈现——"
            "不代表排名、流量或保证被 AI 引用。"
        ),
        "problem": "问题",
        "impact": "影响",
        "fix": "整改",
        "none": "—",
        "fetch_disclosure": "抓取披露",
        "phases": [
            {
                "id": "W0-W2",
                "weeks": "W0–W2",
                "focus": "抓取与 HTTPS 稳定",
                "owner": "工程 / 运维",
                "outcome": "可验证直播 HTML、robots、sitemap；具备技术复测条件",
                "default_items": [
                    "恢复稳定 HTTP(S)（修复 500 / TLS 失败）",
                    "放行 Googlebot、Bingbot、OAI-SearchBot；在日志 / GSC 核实",
                    "确认 robots.txt 与 sitemap.xml 可访问",
                ],
            },
            {
                "id": "W3-W4",
                "weeks": "W3–W4",
                "focus": "标题、薄页与内链",
                "owner": "内容 / 工程",
                "outcome": "重要 URL 具备独立 title/H1/meta；薄页升级或合并",
                "default_items": [
                    "重要 URL 独立 title / H1 / meta description",
                    "升级或合并偏薄的产品与案例页",
                    "加强枢纽页 → 产品 / 案例内链",
                ],
            },
            {
                "id": "W5-W8",
                "weeks": "W5–W8",
                "focus": "常青 GEO 答案页",
                "owner": "内容",
                "outcome": "针对落败的非品牌采购问题提供意图匹配答案页",
                "default_items": [
                    "按落败采购问题发布 3+ 页答案优先的常青内容",
                    "重建产品模板：规格、模块与标准",
                ],
            },
            {
                "id": "W9-W12",
                "weeks": "W9–W12",
                "focus": "证明中心与案例叙事",
                "owner": "内容 / 公关",
                "outcome": "站内权威证据可被生成式引擎引用",
                "default_items": [
                    "上线证明中心（奖项、专利、资质）并附来源链接",
                    "将头部项目案例升级为含可量化结果的完整叙事",
                    "统一品牌 / 实体命名",
                ],
            },
            {
                "id": "W13-W16",
                "weeks": "W13–W16",
                "focus": "外销语言与复测",
                "owner": "内容 / GEO 负责人",
                "outcome": "覆盖外销英文意图；刷新 GEO 分数",
                "default_items": [
                    "为外销 / 国际买家补充英文意图页",
                    "用同一问题集重跑技术 + 内容 GEO 评测",
                    "对比基线与 AI / 搜索可见性检查结果",
                ],
            },
        ],
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


def _action_text(a) -> str:
    if isinstance(a, str):
        return a
    return " ".join(
        [
            str(a.get("sev") or ""),
            str(a.get("action") or ""),
            str(a.get("detail") or ""),
            str(a.get("owner") or ""),
        ]
    )


PHASE_KEYWORDS = {
    "W0-W2": [
        "http",
        "https",
        "tls",
        "crawl",
        "crawler",
        "robots",
        "sitemap",
        "500",
        "waf",
        "pingora",
        "抓取",
        "爬虫",
        "稳定",
    ],
    "W3-W4": [
        "title",
        "meta",
        "h1",
        "thin",
        "duplicate",
        "internal link",
        "snippet",
        "薄",
        "标题",
        "内链",
        "模板",
        "product template",
        "rebuild product",
    ],
    "W5-W8": [
        "evergreen",
        "answer-first",
        "buyer question",
        "procurement",
        "intent",
        "losing",
        "常青",
        "答案",
        "选型",
        "采购问题",
        "geo page",
    ],
    "W9-W12": [
        "proof",
        "patent",
        "award",
        "qualification",
        "case",
        "authority",
        "evidence",
        "证明",
        "专利",
        "资质",
        "案例",
        "奖项",
    ],
    "W13-W16": [
        "english",
        "export",
        "re-test",
        "retest",
        "quarterly",
        "live ai",
        "英文",
        "外销",
        "复测",
        "国际",
    ],
}


def map_actions_to_phases(actions: list, findings: list, lang: str) -> dict:
    """Attach data-driven work items to default phases when keywords match."""
    S = STRINGS[lang]
    buckets = {p["id"]: list(p["default_items"]) for p in S["phases"]}
    seen = {pid: set(x.lower() for x in items) for pid, items in buckets.items()}

    def add(pid: str, text: str):
        key = text.strip().lower()
        if not text.strip() or key in seen[pid]:
            return
        buckets[pid].append(text.strip())
        seen[pid].add(key)

    pool = []
    for a in actions or []:
        if isinstance(a, str):
            pool.append(a)
        else:
            label = a.get("action") or ""
            detail = a.get("detail") or ""
            sev = a.get("sev") or ""
            text = f"[{sev}] {label}" if sev else label
            if detail:
                text = f"{text} — {detail}"
            pool.append(text)
    for f in findings or []:
        if isinstance(f, dict) and f.get("solution"):
            pool.append(f.get("solution"))

    for text in pool:
        blob = text.lower()
        matched = None
        for pid, kws in PHASE_KEYWORDS.items():
            if any(k in blob for k in kws):
                matched = pid
                break
        if matched:
            # Prefer short action line without huge detail for table readability
            short = text.split(" — ")[0].strip()
            add(matched, short)

    return buckets


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
        for token in ("http", "https", "tls", "crawl", "thin", "title", "sitemap", "robots", "抓取", "薄"):
            if token in t:
                return token
        return t[:40]

    content_norms = {_finding_title(f): f for f in content_findings}
    content_keys = {norm(_finding_title(f)): f for f in content_findings}

    for f in tech_findings + content_findings:
        title = _finding_title(f)
        key = norm(title)
        if key in used:
            continue
        # Prefer content dict structure when available for richer fields
        chosen = content_keys.get(key) or f
        shared.append(chosen)
        used.add(key)
        if len(shared) >= limit:
            break
    return shared


def render_finding_blocks(findings: list, S: dict, limit: int = 5) -> str:
    out = []
    for i, f in enumerate(findings[:limit], 1):
        if isinstance(f, str):
            out.append(f'<div class="frow"><h4>{i} · {esc(f)}</h4></div>')
            continue
        sev = (f.get("severity") or "medium").lower()
        out.append(
            f"""<div class="frow">
  <div class="frow-h"><span class="sev sev-{esc(sev)}">{esc(sev)}</span>
  <h4>{i} · {esc(f.get('title') or '')}</h4></div>
  <p><b>{esc(S['problem'])}</b>: {esc(f.get('problem') or '')}</p>
  <p><b>{esc(S['impact'])}</b>: {esc(f.get('impact') or '')}</p>
  <p class="fix"><b>{esc(S['fix'])}</b>: {esc(f.get('solution') or '')}</p>
</div>"""
        )
    return "".join(out) or f"<p class='note'>{esc(S['none'])}</p>"


def render_html(tech: dict, content: dict, style_css: str, lang: str, brand: str | None) -> str:
    S = STRINGS[lang]
    domain = (
        content.get("domain")
        or tech.get("domain")
        or urlparse(tech.get("url") or "").hostname
        or "site"
    )
    brand = (
        brand
        or content.get("site_brand")
        or content.get("company_name")
        or tech.get("brand")
        or domain
    )
    date = (
        (content.get("generated_at") or "")[:10]
        or (tech.get("generated_at") or "")[:10]
        or datetime.now().strftime("%Y-%m-%d")
    )

    tech_score = tech.get("overall_score")
    tech_grade = tech.get("grade") or "—"
    seo = tech.get("seo_discoverability") or {}
    seo_score = seo.get("score")
    seo_max = seo.get("max") or 25
    seo_grade = seo.get("grade") or "—"
    seo_conf = seo.get("confidence") or ("provisional" if tech.get("provisional") else "—")
    content_score = content.get("overall_score")
    content_grade = content.get("grade") or "—"
    content_conf = content.get("confidence") or "—"

    _, tc, tg, _ = grade_meta(tech_grade if tech_score is not None else "F")
    _, sc, sg, _ = grade_meta(seo_grade if seo_score is not None else "F")
    _, cc, cg, _ = grade_meta(content_grade if content_score is not None else "F")

    tech_disp = "—" if tech_score is None else str(tech_score)
    seo_disp = "—" if seo_score is None else str(seo_score)
    content_disp = "—" if content_score is None else str(content_score)

    # Progress bar uses content score when available, else tech
    pct_source = content_score if content_score is not None else tech_score
    pct = 0 if pct_source is None else max(0, min(100, float(pct_source)))

    provisional_badge = ""
    if tech.get("provisional") or (seo.get("confidence") or "").lower() == "provisional":
        provisional_badge = f'<span class="sev sev-warning">{esc(S["provisional"])}</span>'

    tech_summary = tech.get("overall_summary") or tech.get("closing") or ""
    # Prefer readable plain text on combined page if heavy HTML
    if "<" in tech_summary and ">" in tech_summary:
        tech_summary_html = tech_summary  # already contains safe enrichment tags from our pipeline
    else:
        tech_summary_html = inline_md(tech_summary)

    seo_narr = seo.get("narr") or seo.get("callout") or ""
    content_summary = content.get("overall_summary") or ""

    tech_strengths = "".join(f"<li>{esc(s)}</li>" for s in (tech.get("strengths") or [])[:6]) or f"<li>{esc(S['none'])}</li>"
    content_strengths = "".join(f"<li>{esc(s)}</li>" for s in (content.get("strengths") or [])[:6]) or f"<li>{esc(S['none'])}</li>"

    tech_findings = list(tech.get("findings") or [])
    tech_findings.extend((seo.get("findings") or []))
    content_findings = list(content.get("findings") or [])

    dim_rows = "".join(
        f"<tr><td>{esc(d.get('name'))}</td>"
        f"<td class='num mono'>{esc(str(d.get('score')))}</td>"
        f"<td class='dim mono'>/{esc(str(d.get('max')))}</td>"
        f"<td class='dim mono r'>{esc(str(d.get('grade')))}</td></tr>"
        for d in (content.get("dimensions") or [])
    )

    shared = collect_shared_findings(tech, content)
    shared_html = render_finding_blocks(shared, S, limit=6)

    actions = list(content.get("priority_actions") or [])
    # Tech rarely has priority_actions; fold SEO solutions
    for f in seo.get("findings") or []:
        if isinstance(f, dict) and f.get("solution"):
            actions.append(
                {
                    "sev": "P0" if (f.get("severity") or "") == "critical" else "P1",
                    "action": f.get("title") or f.get("solution"),
                    "detail": f.get("solution") or "",
                    "owner": "eng/ops" if "crawl" in _finding_blob(f) or "http" in _finding_blob(f) else "content",
                }
            )

    phase_items = map_actions_to_phases(actions, content_findings + tech_findings, lang)
    timeline_rows = ""
    for p in S["phases"]:
        items = phase_items.get(p["id"], p["default_items"])
        # Cap length for readability
        items = items[:6]
        ul = "<ul class='plain'>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"
        timeline_rows += (
            f"<tr><td class='mono'><b>{esc(p['weeks'])}</b></td>"
            f"<td><b>{esc(p['focus'])}</b></td>"
            f"<td>{ul}</td>"
            f"<td>{esc(p['owner'])}</td>"
            f"<td>{esc(p['outcome'])}</td></tr>"
        )

    actions_html = ""
    for a in actions[:12]:
        if isinstance(a, str):
            actions_html += f"<div class='arow'><div><h4>{esc(a)}</h4></div></div>"
        else:
            actions_html += (
                f"<div class='arow'><div><h4>[{esc(a.get('sev','P1'))}] {esc(a.get('action') or '')}</h4>"
                f"<p>{esc(a.get('detail') or '')}</p></div>"
                f"<span class='owner owner-info'>{esc(a.get('owner') or '')}</span></div>"
            )

    tech_finding_html = render_finding_blocks(tech_findings, S, limit=4)
    content_finding_html = render_finding_blocks(content_findings, S, limit=5)

    scope_note = content.get("scope_note") or (tech.get("scope") or {}).get("note") or ""
    fetch_disclosure = content.get("fetch_disclosure") or ""
    closing = content.get("closing") or tech.get("closing") or ""

    site_url = content.get("site_url") or tech.get("url") or f"https://{domain}"

    return f"""<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(brand)} {esc(S['doc_title'])} · {esc(domain)}</title>
<meta name="description" content="Combined GEO package for {esc(domain)}: technical {esc(tech_disp)}/100, SEO {esc(seo_disp)}/{esc(str(seo_max))}, Content GEO {esc(content_disp)}/100.">
<style>{style_css}
/* Combined report extras on shared technical stylesheet */
.page {{ min-height: auto; padding-bottom: 2rem; }}
.deck {{ max-width: 920px; margin: 0 auto; }}
.sev {{ display:inline-block; font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; padding:2px 8px; border-radius:999px; background:#eee; }}
.sev-critical {{ background:#fee2e2; color:#991b1b; }}
.sev-high {{ background:#ffedd5; color:#9a3412; }}
.sev-medium {{ background:#e0e7ff; color:#3730a3; }}
.sev-low {{ background:#ecfdf5; color:#065f46; }}
.sev-warning {{ background:#ffedd5; color:#9a3412; }}
.c-a{{color:var(--success)}}.c-b{{color:var(--info)}}.c-c{{color:var(--warning)}}.c-d{{color:var(--danger)}}
.g-a{{color:var(--success)}}.g-b{{color:var(--info)}}.g-c{{color:var(--warning)}}.g-d{{color:var(--danger)}}
.score-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:var(--space-5)}}
.score-card{{background:var(--surface-2);border:1px solid var(--border);border-radius:12px;padding:16px 18px}}
.score-card .label{{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3);font-weight:600}}
.score-card .val{{font-family:var(--font-mono);font-size:28px;font-weight:650;margin-top:6px}}
.score-card .val small{{font-size:13px;color:var(--text-3);font-weight:500}}
.score-card .sub{{font-size:12.5px;color:var(--text-3);margin-top:4px}}
@media (max-width:720px){{.score-grid{{grid-template-columns:1fr}}}}
.mtable ul.plain{{margin:0;padding-left:1.1em}}
.mtable td ul.plain li{{margin:2px 0}}
</style></head><body>
<div class="topbar"><div class="topbar-in">
  <span class="brand"><b>GEO Checker</b></span>
  <span class="doc">{esc(brand)} · {esc(S['doc_title'])} · {esc(domain)}</span>
  <span class="right"><span class="now mono">{esc(date)}</span></span>
</div><div class="progress"><i style="width:{pct}%"></i></div></div>

<div class="deck">

<section class="page page-dark cover" id="cover">
  <div class="cover-top"><span class="brand"><b>GEO Checker</b></span>
    <span class="cover-no mono">Beansmile · GEO Checker</span></div>
  <div class="cover-mid">
    <div class="pkicker light">{esc(S['cover_kicker'])}</div>
    <h1>{esc(brand)}<br>{esc(S['cover_h1'])}</h1>
    <p class="cover-sub">{esc(S['cover_sub'])}</p>
    <div class="cover-score">
      <div class="cbig">{esc(content_disp)}<small>/100</small><em>{esc(S['content_label'])} {esc(str(content_grade))}</em></div>
      <div><div class="cmeter"><div class="cm-track"><span class="cm-fill" style="width:{pct}%"></span></div>
      <div class="cm-scale"><span>0</span><span>Pass 60</span><span>Good 80</span><span>100</span></div></div>
      <p class="cover-score-note">{esc(S['tech_label'])}: {esc(tech_disp)}/100 ({esc(str(tech_grade))}) · {esc(S['seo_label'])}: {esc(seo_disp)}/{esc(str(seo_max))} ({esc(str(seo_grade))})</p></div>
    </div>
  </div>
  <dl class="cover-facts">
    <div class="wide"><dt>{esc(S['site'])}</dt><dd class="mono">{esc(site_url)}</dd></div>
    <div><dt>{esc(S['report_date'])}</dt><dd class="mono">{esc(date)}</dd></div>
    <div><dt>{esc(S['confidence'])}</dt><dd>{esc(str(content_conf))} / SEO {esc(str(seo_conf))}</dd></div>
    <div><dt>{esc(S['grade_scale'])}</dt><dd class="mono">A+≥90 · A≥80 · B≥70 · C≥60 · D&lt;60 · F</dd></div>
  </dl>
  <div class="cover-sign"><span>Prepared by Beansmile · GEO Checker</span> {provisional_badge}</div>
</section>

<section class="page" id="intro">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">01</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['intro_kicker'])}</div>
    <h2>{esc(S['intro_h2'])}</h2></div></div>
  <div class="narr lead">{S['intro_body']}</div>
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
    <div class="score-card">
      <div class="label">{esc(S['tech_label'])}</div>
      <div class="val {tc}">{esc(tech_disp)}<small>/100</small> <em class="g {tg}">{esc(str(tech_grade))}</em></div>
      <div class="sub">9 dimensions · on-site readiness</div>
    </div>
    <div class="score-card">
      <div class="label">{esc(S['seo_label'])}</div>
      <div class="val {sc}">{esc(seo_disp)}<small>/{esc(str(seo_max))}</small> <em class="g {sg}">{esc(str(seo_grade))}</em></div>
      <div class="sub">{esc(S['confidence'])}: {esc(str(seo_conf))}</div>
    </div>
    <div class="score-card">
      <div class="label">{esc(S['content_label'])}</div>
      <div class="val {cc}">{esc(content_disp)}<small>/100</small> <em class="g {cg}">{esc(str(content_grade))}</em></div>
      <div class="sub">5 dimensions · {esc(S['confidence'])}: {esc(str(content_conf))}</div>
    </div>
  </div>
  <table class="mtable" style="margin-top:24px"><thead>
    <tr><th>{esc(S['track'])}</th><th>{esc(S['score'])}</th><th>{esc(S['max'])}</th><th class="r">{esc(S['grade'])}</th></tr>
  </thead><tbody>
    <tr><td>{esc(S['tech_label'])}</td><td class="num mono">{esc(tech_disp)}</td><td class="dim mono">/100</td><td class="r">{esc(str(tech_grade))}</td></tr>
    <tr><td>{esc(S['seo_label'])}</td><td class="num mono">{esc(seo_disp)}</td><td class="dim mono">/{esc(str(seo_max))}</td><td class="r">{esc(str(seo_grade))}</td></tr>
    <tr class="total"><td>{esc(S['content_label'])}</td><td class="num mono">{esc(content_disp)}</td><td class="dim mono">/100</td><td class="r">{esc(str(content_grade))}</td></tr>
  </tbody></table>
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
  <div class="sublab" style="margin-top:1.2rem">{esc(S['tech_seo'])} — {esc(seo_disp)}/{esc(str(seo_max))} ({esc(str(seo_grade))})</div>
  <div class="narr">{inline_md(seo_narr)}</div>
  <div class="sublab">{esc(S['strengths'])}</div>
  <ul class="plain">{tech_strengths}</ul>
  <div class="sublab">{esc(S['key_findings'])}</div>
  {tech_finding_html}
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
  <div class="callout"><b>{esc(S['closing'])}</b><p>{inline_md(closing)}</p></div>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="shared">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">05</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['shared_kicker'])}</div>
    <h2>{esc(S['shared_h2'])}</h2></div></div>
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
  <table class="mtable"><thead>
    <tr><th>{esc(S['weeks'])}</th><th>{esc(S['focus'])}</th><th>{esc(S['work'])}</th><th>{esc(S['owner'])}</th><th>{esc(S['outcome'])}</th></tr>
  </thead><tbody>{timeline_rows}</tbody></table>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="actions">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">07</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['actions_kicker'])}</div>
    <h2>{esc(S['actions_h2'])}</h2></div></div>
  <div class="actions">{actions_html or "<p class='note'>" + esc(S['none']) + "</p>"}</div>
  <footer class="pf"><span>{esc(S['footer'])}</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="scope">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">08</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">{esc(S['scope_kicker'])}</div>
    <h2>{esc(S['scope_h2'])}</h2></div></div>
  <p class="narr">{inline_md(scope_note)}</p>
  {"<p class='note'><b>" + esc(S['fetch_disclosure']) + "</b>: " + esc(fetch_disclosure) + "</p>" if fetch_disclosure else ""}
  <div class="callout"><b>{esc(S['closing'])}</b><p>{inline_md(closing)}</p></div>
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

    html = render_html(tech, content, style, lang=lang, brand=args.brand)
    suffix = ".zh" if lang == "zh" else ""
    html_path = os.path.join(out_dir, f"combined_report{suffix}.html")
    open(html_path, "w", encoding="utf-8").write(html)
    print(f"Wrote {html_path} ({len(html)} chars)")


if __name__ == "__main__":
    main()
