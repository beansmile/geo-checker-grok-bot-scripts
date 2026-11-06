#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build standalone Content GEO report (HTML) from content_report.json.

HTML reuses report_templates/style.css so the deliverable matches the technical
GEO readiness report visually. SEO discoverability is NOT part of this report
(see technical report / seo_scoring.md).

Client deliverable is HTML only. Pass --also-md to also write Markdown (internal).
"""

from __future__ import annotations

import html as html_mod
import json
import os
import re
import sys
from datetime import datetime


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


def inline_md(s: str) -> str:
    """Light **bold** and `code` for HTML prose (already escaped)."""
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def render_md(data: dict) -> str:
    brand = data.get("site_brand") or data.get("company_name") or data.get("domain") or "Website"
    domain = data.get("domain") or ""
    score = data.get("overall_score")
    grade = data.get("grade") or "—"
    conf = data.get("confidence") or ""
    score_line = "unevaluable" if data.get("unevaluable") or score is None else f"**{score} / 100 ({grade})**"
    lines: list[str] = []
    lines.append(f"# {brand} — Content GEO Evaluation Report")
    lines.append("")
    lines.append(
        f"> **{domain}** · {(data.get('generated_at') or '')[:10]} · Content GEO {score_line}"
        f"{' · confidence: ' + conf if conf else ''}"
    )
    lines.append("")
    lines.append(
        "This report evaluates whether the site’s **content** can be understood, trusted, and cited "
        "by generative engines: information architecture, page types and gaps, writing quality, "
        "authority evidence, and coverage of real buyer questions (including labeled AI / search "
        "visibility checks). **GEO = Generative Engine Optimization** (websites), not geography."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Overall assessment")
    lines.append("")
    lines.append(data.get("overall_summary") or "_Pending enrichment._")
    lines.append("")
    lines.append(f"> **One-line conclusion**: {data.get('closing') or '—'}")
    lines.append("")
    if data.get("fetch_disclosure"):
        lines.append(f"**Fetch disclosure**: {data['fetch_disclosure']}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Content GEO scoring method")
    lines.append("")
    lines.append(
        "Five dimensions sum to 100. SEO content discoverability (titles, crawl paths, sitemap/robots "
        "as discovery aids) is scored in the technical GEO readiness report, not here."
    )
    lines.append("")
    lines.append("| Dimension | Score | Max | Grade |")
    lines.append("|---|---|---|---|")
    for d in data.get("dimensions") or []:
        lines.append(
            f"| {d.get('name')} | {d.get('score')} | /{d.get('max')} | {d.get('grade')} |"
        )
    if score is not None:
        lines.append(f"| **Content GEO total** | **{score}** | **/100** | {grade} |")
    lines.append("")
    lines.append("Grade scale: A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D < 60 · F = unevaluable.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 3. What's already working")
    lines.append("")
    strengths = data.get("strengths") or []
    if strengths:
        for s in strengths:
            lines.append(f"- {s}")
    else:
        lines.append("- _(None listed)_")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 4. Dimension assessment")
    lines.append("")
    for i, d in enumerate(data.get("dimensions") or [], 1):
        lines.append(f"### {i} · {d.get('name')} ({d.get('score')} / {d.get('max')} · {d.get('grade')})")
        lines.append("")
        lines.append(d.get("narr") or " ".join(d.get("notes") or []) or "—")
        lines.append("")
        if d.get("callout"):
            lines.append(f"**How to improve**: {d['callout']}")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Information architecture — current vs recommended")
    lines.append("")
    if data.get("current_ia_notes"):
        lines.append(data["current_ia_notes"])
        lines.append("")
    ia = data.get("recommended_ia_tree") or []
    if ia:
        lines.append("Recommended tree:")
        lines.append("")
        for node in ia:
            if isinstance(node, str):
                lines.append(f"- {node}")
            else:
                lines.append(f"- **{node.get('section')}**: {node.get('detail', '')}")
        lines.append("")
    briefs = data.get("page_briefs") or []
    if briefs:
        lines.append("### Page briefs to create or upgrade")
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
    lines.append("## 6. Content taxonomy & gaps")
    lines.append("")
    tax = next((d for d in (data.get("dimensions") or []) if d.get("id") == "C-TAX" or d.get("key") == "taxonomy_gaps"), None)
    if tax and tax.get("narr"):
        lines.append(tax["narr"])
        lines.append("")
    counts = data.get("page_type_counts") or {}
    if counts:
        lines.append("| Page type | Count in sample |")
        lines.append("|---|---|")
        for k, v in sorted(counts.items()):
            lines.append(f"| {k} | {v} |")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. Writing quality")
    lines.append("")
    wr = next((d for d in (data.get("dimensions") or []) if d.get("id") == "C-WRITE" or d.get("key") == "writing_quality"), None)
    if wr:
        lines.append(wr.get("narr") or "—")
        lines.append("")
        if wr.get("callout"):
            lines.append(f"**How to improve**: {wr['callout']}")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 8. Authority & evidence publishing")
    lines.append("")
    au = next((d for d in (data.get("dimensions") or []) if d.get("id") == "C-AUTH" or d.get("key") == "authority_evidence"), None)
    if au:
        lines.append(au.get("narr") or "—")
        lines.append("")
    off = data.get("offsite_evidence") or []
    if off:
        lines.append("| Evidence | Where it lives today | Action |")
        lines.append("|---|---|---|")
        for o in off:
            lines.append(
                f"| {o.get('title')} | {o.get('source_url') or o.get('where')} | {o.get('action')} |"
            )
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 9. Target questions × on-site support")
    lines.append("")
    tq = data.get("target_questions") or []
    if tq:
        lines.append("| # | Question | Intent | On-site support (0–3) | Gaps |")
        lines.append("|---|---|---|---|---|")
        for i, q in enumerate(tq, 1):
            gaps = "; ".join(q.get("knowledge_gaps") or []) or "—"
            lines.append(
                f"| {i} | {q.get('question')} | {q.get('intent')} | {q.get('on_site_support')} | {gaps} |"
            )
        lines.append("")
    else:
        lines.append("_No target questions recorded._")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 10. Target questions × AI / search visibility")
    lines.append("")
    lines.append(
        "Checks are labeled by method. `web_retrieval_proxy` = public web/search results used as a "
        "proxy for what retrieval-augmented systems are likely to ground on when live ChatGPT / "
        "Perplexity / Gemini product UIs were not available. **No engine quotes were invented.**"
    )
    lines.append("")
    for lim in data.get("ai_check_limits") or []:
        lines.append(f"- Constraint: {lim}")
    if data.get("ai_check_limits"):
        lines.append("")
    checks = data.get("ai_checks") or []
    if checks:
        lines.append(
            "| Question | Method | Engines / tools | Brand mentioned? | Official domain cited? | Sources seen | Notes |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for c in checks:
            sources = "; ".join((c.get("sources_seen") or [])[:4]) or "—"
            lines.append(
                f"| {c.get('question')} | `{c.get('check_type')}` | {c.get('engines_or_methods')} | "
                f"{'yes' if c.get('mentioned_brand') else 'no'} | "
                f"{'yes' if c.get('cited_official_domain') else 'no'} | {sources} | "
                f"{(c.get('notes') or '')[:160]} |"
            )
        lines.append("")
        for c in checks:
            if c.get("answer_summary"):
                lines.append(f"- **{c.get('question')}** — {c['answer_summary']}")
        lines.append("")
    else:
        lines.append("_No AI/search visibility checks attached._")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 11. Key findings")
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
                lines.append(f"**Problem**: {f.get('problem')}")
                lines.append("")
                lines.append(f"**Impact**: {f.get('impact')}")
                lines.append("")
                lines.append(f"**Fix**: {f.get('solution')}")
                lines.append("")
                ev = f.get("evidence") or []
                if ev:
                    lines.append("Evidence:")
                    for e in ev:
                        lines.append(f"- {e}")
                    lines.append("")
    else:
        lines.append("_See dimension narratives._")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 12. Priority actions")
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
    lines.append("## 13. Scope")
    lines.append("")
    lines.append(data.get("scope_note") or "")
    lines.append("")
    lines.append(f"- Pages analyzed: {data.get('pages_analyzed')}")
    lines.append(f"- Fetch mode: `{data.get('fetch_mode')}`")
    lines.append(f"- Sample URLs / files: {len(data.get('sample_urls') or [])}")
    for u in (data.get("sample_urls") or [])[:24]:
        lines.append(f"  - {u}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 14. Conclusion")
    lines.append("")
    lines.append(data.get("closing") or "—")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Prepared by Beansmile · GEO Checker*")
    lines.append("")
    return "\n".join(lines)


def render_html(data: dict, style_css: str) -> str:
    brand = data.get("site_brand") or data.get("company_name") or data.get("domain") or "Website"
    domain = data.get("domain") or ""
    score = data.get("overall_score")
    grade = data.get("grade") or "—"
    conf = data.get("confidence") or "—"
    date = (data.get("generated_at") or datetime.now().isoformat())[:10]
    score_disp = "—" if score is None else str(score)
    _, c_class, g_class, bar = grade_meta(grade if score is not None else "F")
    pct = 0 if score is None else max(0, min(100, float(score)))

    dims = data.get("dimensions") or []
    dim_rows = "".join(
        f"<tr><td>{esc(d.get('name'))}</td><td class=\"num mono\">{esc(str(d.get('score')))}</td>"
        f"<td class=\"dim mono\">/{esc(str(d.get('max')))}</td>"
        f"<td class=\"dim mono r\">{esc(str(d.get('grade')))}</td></tr>"
        for d in dims
    )
    if score is not None:
        dim_rows += (
            f"<tr class=\"total\"><td>Content GEO total</td><td class=\"num mono\">{esc(str(score))}</td>"
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
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">Dimension {i:02d}</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">Dimension · {i:02d}</div>
    <h2>{esc(d.get('name'))}</h2></div>
    <div class="pmeta"><span class="scorechip {dc}"><b>{esc(str(d.get('score')))}</b>
    <span>/{esc(str(d.get('max')))}</span><em class="g {dg}">{esc(str(d.get('grade')))}</em></span></div></div>
  <div class="mini"><i style="width:{dp}%;background:{dbar}"></i></div>
  <div class="narr">{inline_md(d.get('narr') or '')}</div>
  {"<div class='sublab'>Engine notes</div><ul class='plain'>" + notes_html + "</ul>" if notes_html else ""}
  {"<div class='callout'><b>How to improve</b><p>" + inline_md(d.get('callout') or '') + "</p></div>" if d.get('callout') else ""}
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>"""

    strengths = "".join(f"<li>{esc(s)}</li>" for s in (data.get("strengths") or [])) or "<li>—</li>"

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
        gaps = "; ".join(q.get("knowledge_gaps") or []) or "—"
        tq_rows += (
            f"<tr><td class=\"mono\">{i}</td><td>{esc(q.get('question'))}</td>"
            f"<td>{esc(q.get('intent'))}</td><td class=\"num mono\">{esc(str(q.get('on_site_support')))}</td>"
            f"<td>{esc(gaps)}</td></tr>"
        )

    ai_rows = ""
    for c in data.get("ai_checks") or []:
        sources = "; ".join((c.get("sources_seen") or [])[:3]) or "—"
        ai_rows += (
            f"<tr><td>{esc(c.get('question'))}</td><td><code>{esc(c.get('check_type'))}</code></td>"
            f"<td>{esc(c.get('engines_or_methods'))}</td>"
            f"<td>{'yes' if c.get('mentioned_brand') else 'no'}</td>"
            f"<td>{'yes' if c.get('cited_official_domain') else 'no'}</td>"
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
        ev = "".join(f"<li>{esc(e)}</li>" for e in (f.get("evidence") or []))
        findings_html += f"""
<div class="frow" id="f{i}">
  <div class="frow-h"><span class="sev sev-{sev}">{sev}</span><h4>{i} · {esc(f.get('title'))}</h4></div>
  <p><b>Problem</b>: {esc(f.get('problem'))}</p>
  <p><b>Impact</b>: {esc(f.get('impact'))}</p>
  <p class="fix"><b>Fix</b>: {esc(f.get('solution'))}</p>
  {"<ul class='plain'>" + ev + "</ul>" if ev else ""}
</div>"""

    actions_html = ""
    for a in data.get("priority_actions") or []:
        if isinstance(a, str):
            actions_html += f"<div class='arow'><div><h4>{esc(a)}</h4></div></div>"
        else:
            actions_html += (
                f"<div class='arow'><div><h4>[{esc(a.get('sev','P1'))}] {esc(a.get('action'))}</h4>"
                f"<p>{esc(a.get('detail',''))}</p></div>"
                f"<span class='owner owner-info'>{esc(a.get('owner','content'))}</span></div>"
            )

    sample = "".join(f"<li class='mono'>{esc(u)}</li>" for u in (data.get("sample_urls") or [])[:24])

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(brand)} Content GEO Report · {esc(domain)}</title>
<meta name="description" content="Content GEO evaluation for {esc(domain)}: {esc(score_disp)}/100 ({esc(str(grade))}).">
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
  <span class="doc">{esc(brand)} · Content GEO · {esc(domain)}</span>
  <span class="right"><span class="now mono">{esc(date)}</span></span>
</div><div class="progress"><i style="width:{pct}%"></i></div></div>

<div class="deck">

<section class="page page-dark cover" id="cover">
  <div class="cover-top"><span class="brand"><b>GEO Checker</b></span>
    <span class="cover-no mono">Beansmile · GEO Checker</span></div>
  <div class="cover-mid">
    <div class="pkicker light">Generative Engine Optimization · Content evaluation</div>
    <h1>{esc(brand)}<br>Content GEO Report</h1>
    <p class="cover-sub">Whether site content can be understood, trusted, and cited — architecture, page types, writing, authority evidence, and buyer-question coverage.</p>
    <div class="cover-score"><div class="cbig">{esc(score_disp)}<small>/100</small><em>Content GEO {esc(str(grade))}</em></div>
    <div><div class="cmeter"><div class="cm-track"><span class="cm-fill" style="width:{pct}%"></span></div>
    <div class="cm-scale"><span>0</span><span>Pass 60</span><span>Good 80</span><span>100</span></div></div>
    <p class="cover-score-note">Confidence: {esc(conf)}. Not a search-ranking audit.</p></div></div>
  </div>
  <dl class="cover-facts">
    <div class="wide"><dt>Site</dt><dd class="mono">{esc(data.get('site_url') or domain)}</dd></div>
    <div><dt>Report date</dt><dd class="mono">{esc(date)}</dd></div>
    <div><dt>Pages analyzed</dt><dd>{esc(str(data.get('pages_analyzed') or '—'))}</dd></div>
    <div><dt>Grade scale</dt><dd class="mono">A+≥90 · A≥80 · B≥70 · C≥60 · D&lt;60</dd></div>
  </dl>
  <div class="cover-sign"><span>Prepared by Beansmile · GEO Checker</span></div>
</section>

<section class="page" id="overall">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">01 Overall</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">01 Overall assessment</div>
    <h2>Content GEO: {esc(score_disp)} / 100 ({esc(str(grade))})</h2></div>
    <div class="pmeta"><span class="scorechip {c_class}"><b>{esc(score_disp)}</b><span>/100</span></span></div></div>
  <div class="narr lead">{inline_md(data.get('overall_summary') or '')}</div>
  {"<p class='note'><b>Fetch disclosure</b>: " + esc(data.get('fetch_disclosure') or '') + "</p>" if data.get('fetch_disclosure') else ""}
  <div class="callout"><b>One-line conclusion</b><p>{inline_md(data.get('closing') or '')}</p></div>
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="method">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">02 Scoring method</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">02 Scoring method</div>
    <h2>How the Content GEO score is calculated</h2></div></div>
  <p class="narr">Five dimensions sum to 100. Titles, crawl paths, and sitemap/robots as discovery aids are covered in the technical report’s SEO chapter.</p>
  <table class="mtable"><thead><tr><th>Dimension</th><th>Score</th><th>Max</th><th class="r">Grade</th></tr></thead>
  <tbody>{dim_rows}</tbody></table>
  <p class="note">Grade scale: A+ ≥ 90 · A ≥ 80 · B ≥ 70 · C ≥ 60 · D &lt; 60 · F = unevaluable. Rubric: {esc(data.get('rubric_version') or 'content_scoring.md v1.1')}.</p>
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="strengths">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">03 Strengths</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">03 What's already working</div><h2>Existing foundations</h2></div></div>
  <ul class="plain">{strengths}</ul>
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

{dim_cards}

<section class="page" id="ia">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">Architecture</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">Information architecture</div>
    <h2>Current vs recommended</h2></div></div>
  <p class="narr">{inline_md(data.get('current_ia_notes') or '')}</p>
  <div class="sublab">Recommended tree</div>
  <ul class="plain">{ia_nodes or '<li>—</li>'}</ul>
  <div class="sublab">Page briefs</div>
  {briefs_html or '<p class="note">No page briefs.</p>'}
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="questions">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">Questions</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">Target questions</div>
    <h2>On-site support</h2></div></div>
  <table class="mtable"><thead><tr><th>#</th><th>Question</th><th>Intent</th><th>Support</th><th>Gaps</th></tr></thead>
  <tbody>{tq_rows or '<tr><td colspan="5">No questions recorded.</td></tr>'}</tbody></table>
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="ai">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">AI visibility</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">AI / search visibility</div>
    <h2>Would retrieval surface the official site?</h2></div></div>
  <p class="note">Methods are labeled. No engine quotes were invented.</p>
  {"<ul class='plain'>" + ai_limits + "</ul>" if ai_limits else ""}
  <table class="mtable"><thead><tr><th>Question</th><th>Method</th><th>Tools</th><th>Brand?</th><th>Official?</th><th>Sources</th><th>Notes</th></tr></thead>
  <tbody>{ai_rows or '<tr><td colspan="7">No checks attached.</td></tr>'}</tbody></table>
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="evidence">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">Authority</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">Authority evidence</div>
    <h2>What to publish on-site</h2></div></div>
  <table class="mtable"><thead><tr><th>Evidence</th><th>Where today</th><th>Action</th></tr></thead>
  <tbody>{off_rows or '<tr><td colspan="3">No off-site inventory.</td></tr>'}</tbody></table>
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="findings">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">Findings</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">Key findings</div><h2>Issues to prioritise</h2></div></div>
  {findings_html or '<p class="note">See dimension narratives.</p>'}
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="actions">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">Actions</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">Priority actions</div><h2>Ordered next steps</h2></div></div>
  <div class="actions">{actions_html or '<p class="note">—</p>'}</div>
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

<section class="page" id="scope">
  <header class="ph"><span class="brand"><b>GEO Checker</b></span>
    <span class="ph-url mono">{esc(domain)}</span><span class="ph-sec">Scope</span>
    <span class="ph-right"><span class="mono">{esc(date)}</span></span></header>
  <div class="ptitle"><div><div class="pkicker">Scope</div><h2>What this assessment covered</h2></div></div>
  <p class="narr">{inline_md(data.get('scope_note') or '')}</p>
  <p class="note">Fetch mode: <code>{esc(data.get('fetch_mode') or '')}</code> · Pages analyzed: {esc(str(data.get('pages_analyzed') or '—'))}</p>
  <div class="sublab">Sample URLs</div>
  <ul class="plain">{sample or '<li>—</li>'}</ul>
  <div class="callout"><b>Conclusion</b><p>{inline_md(data.get('closing') or '')}</p></div>
  <footer class="pf"><span>GEO Checker · Content GEO</span><span class="mono">Beansmile</span></footer>
</section>

</div>
<p class="docfoot">Content GEO evaluation by Beansmile · GEO Checker. Measures whether website content can be understood, trusted and cited — not rankings, traffic, or guaranteed AI mentions.</p>
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

    data = load_report(run_dir)
    rp = os.path.join(run_dir, "content_report.json")
    if os.path.isfile(rp):
        data = json.load(open(rp, encoding="utf-8"))

    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    style_path = os.path.join(skill_root, "report_templates", "style.css")
    style = open(style_path, encoding="utf-8").read() if os.path.isfile(style_path) else ""

    out_dir = os.path.join(run_dir, "report")
    os.makedirs(out_dir, exist_ok=True)

    # Prefer Chinese narrative fields if present when --lang zh
    if lang == "zh" and data.get("overall_summary_zh"):
        data = dict(data)
        for k in ("overall_summary", "closing", "fetch_disclosure", "scope_note", "current_ia_notes"):
            zk = f"{k}_zh"
            if data.get(zk):
                data[k] = data[zk]

    suffix = ".zh" if lang == "zh" else ""
    html_path = os.path.join(out_dir, f"content_report{suffix}.html")
    open(html_path, "w", encoding="utf-8").write(render_html(data, style))
    print(f"Wrote {html_path}")

    if "--also-md" in sys.argv:
        md = render_md(data)
        md_path = os.path.join(out_dir, f"content_report{suffix}.md")
        open(md_path, "w", encoding="utf-8").write(md)
        print(f"Wrote {md_path} (--also-md)")


if __name__ == "__main__":
    main()
