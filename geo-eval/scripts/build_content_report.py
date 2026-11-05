#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build standalone Content GEO report (Markdown + HTML) from content_report.json."""

from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime


def md_escape(s: str) -> str:
    return s or ""


def load_report(run_dir: str) -> dict:
    path = os.path.join(run_dir, "content_report.json")
    if not os.path.isfile(path):
        # fall back to engine
        path = os.path.join(run_dir, "content.engine.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_md(data: dict) -> str:
    brand = data.get("site_brand") or data.get("company_name") or data.get("domain") or "Website"
    domain = data.get("domain") or ""
    score = data.get("overall_score")
    grade = data.get("grade") or "—"
    conf = data.get("confidence") or ""
    score_line = "unevaluable" if data.get("unevaluable") or score is None else f"**{score} / 100 ({grade})**"
    lines = []
    lines.append(f"# {brand} — Content GEO Evaluation Report")
    lines.append("")
    lines.append(
        f"> **{domain}** · {data.get('generated_at', '')[:10]} · Content GEO {score_line}"
        f"{' · confidence: ' + conf if conf else ''}"
    )
    lines.append("")
    lines.append(
        "This standalone report evaluates **SEO content discoverability** and **GEO content citability** "
        "(answerability, evidence publishing, and whether target buyer questions surface the official site). "
        "It is **not** the technical 9-dimension on-site readiness score. "
        "**GEO = Generative Engine Optimization** (websites), not geography."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Overall assessment")
    lines.append("")
    lines.append(md_escape(data.get("overall_summary") or "_Pending enrichment._"))
    lines.append("")
    lines.append(f"> **One-line conclusion**: {md_escape(data.get('closing') or '—')}")
    lines.append("")
    if data.get("fetch_disclosure"):
        lines.append(f"**Fetch disclosure**: {data['fetch_disclosure']}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Content GEO scoring method")
    lines.append("")
    lines.append(
        "Six dimensions sum to 100. This scale is independent of the technical GEO Checker score."
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
        lines.append(md_escape(d.get("narr") or " ".join(d.get("notes") or []) or "—"))
        lines.append("")
        if d.get("callout"):
            lines.append(f"**How to improve**: {d['callout']}")
            lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Information architecture — current vs recommended")
    lines.append("")
    ia = data.get("recommended_ia_tree") or []
    if data.get("current_ia_notes"):
        lines.append(data["current_ia_notes"])
        lines.append("")
    if ia:
        lines.append("Recommended tree:")
        lines.append("")
        for node in ia:
            if isinstance(node, str):
                lines.append(f"- {node}")
            else:
                lines.append(f"- **{node.get('section')}**: {node.get('detail', '')}")
        lines.append("")
    else:
        lines.append("_See dimension C-IA narrative._")
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
            must = b.get("must_have") or []
            if must:
                for m in must:
                    lines.append(f"- {m}")
                lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. Target questions × on-site support")
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
    lines.append("## 7. Target questions × AI / search visibility")
    lines.append("")
    lines.append(
        "Checks are labeled by method. `web_retrieval_proxy` = public web/search results used as a "
        "proxy for what retrieval-augmented AI systems are likely to ground on when live ChatGPT / "
        "Perplexity / Gemini product UIs were not available in this environment. "
        "**No engine quotes were invented.**"
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
    lines.append("## 8. Authority content to publish on-site")
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
    else:
        lines.append("_No off-site evidence inventory._")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 9. Key findings")
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
    lines.append("## 10. Priority actions")
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
    lines.append("## 11. Scope")
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
    lines.append("## 12. Conclusion")
    lines.append("")
    lines.append(md_escape(data.get("closing") or "—"))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Prepared by Beansmile · GEO Checker*")
    lines.append("")
    return "\n".join(lines)


def render_html(md_text: str, data: dict) -> str:
    # Minimal markdown-ish to HTML for client reading
    body = html.escape(md_text)
    # restore structure lightly: headings and tables left as pre-wrapped markdown in <pre> is ugly;
    # convert basic patterns
    out = []
    in_table = False
    for line in md_text.splitlines():
        if line.startswith("|") and "---" not in line:
            if not in_table:
                out.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            tag = "th" if False else "td"
            out.append("<tr>" + "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table and not line.startswith("|"):
            out.append("</table>")
            in_table = False
        if re.match(r"^\|\s*---", line or ""):
            continue
        if line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("#### "):
            out.append(f"<h4>{html.escape(line[5:])}</h4>")
        elif line.startswith("> "):
            out.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        elif line.startswith("- "):
            out.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip() == "":
            out.append("<br>")
        else:
            # bold ** **
            frag = html.escape(line)
            frag = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", frag)
            frag = re.sub(r"`(.+?)`", r"<code>\1</code>", frag)
            out.append(f"<p>{frag}</p>")
    if in_table:
        out.append("</table>")
    score = data.get("overall_score")
    grade = data.get("grade")
    title = f"{data.get('domain')} — Content GEO"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 920px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; line-height: 1.55; }}
h1 {{ font-size: 1.8rem; }} h2 {{ margin-top: 2rem; border-bottom: 1px solid #ddd; padding-bottom: .3rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: .92rem; margin: 1rem 0; }}
td, th {{ border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }}
blockquote {{ background: #f6f8fa; border-left: 4px solid #3b82f6; margin: 1rem 0; padding: .6rem 1rem; }}
code {{ background: #f3f4f6; padding: 1px 4px; border-radius: 3px; }}
.badge {{ display: inline-block; background: #111; color: #fff; padding: 4px 10px; border-radius: 999px; font-size: .85rem; }}
footer {{ margin-top: 3rem; color: #666; font-size: .9rem; }}
</style>
</head>
<body>
<p><span class="badge">Content GEO {html.escape(str(score))} / 100 · {html.escape(str(grade))}</span>
&nbsp; GEO Checker by Beansmile</p>
{''.join(out)}
<footer>Prepared by Beansmile · GEO Checker · {html.escape(str(data.get('generated_at') or '')[:19])}</footer>
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        print("Usage: build_content_report.py <run_dir>")
        sys.exit(2)
    run_dir = sys.argv[1]
    data = load_report(run_dir)
    # Prefer enriched report
    rp = os.path.join(run_dir, "content_report.json")
    if os.path.isfile(rp):
        data = json.load(open(rp, encoding="utf-8"))
    out_dir = os.path.join(run_dir, "report")
    os.makedirs(out_dir, exist_ok=True)
    md = render_md(data)
    md_path = os.path.join(out_dir, "content_report.md")
    html_path = os.path.join(out_dir, "content_report.html")
    open(md_path, "w", encoding="utf-8").write(md)
    open(html_path, "w", encoding="utf-8").write(render_html(md, data))
    print(f"Wrote {md_path}")
    print(f"Wrote {html_path}")


if __name__ == "__main__":
    main()
