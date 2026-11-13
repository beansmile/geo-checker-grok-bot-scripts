#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Heuristic Content GEO scoring (v1.2 / product scoring v1.3, five dims).

From content_extract.json (+ optional AI checks).
SEO discoverability lives in the technical report (seo_scoring.md / seo_analyze.py).
Writes content.engine.json. Agent enrichment fills narratives into content_report.json.
Does NOT touch the technical 10-dimension /100 formula in scoring.md.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime

import page_coverage

DIMS = [
    ("information_architecture", "C-IA", "Information architecture", 20),
    ("taxonomy_gaps", "C-TAX", "Content taxonomy & gaps", 15),
    ("writing_quality", "C-WRITE", "Writing quality", 20),
    ("authority_evidence", "C-AUTH", "Authority & evidence publishing", 20),
    ("query_coverage", "C-QUERY", "Target query coverage", 25),
]


def grade_for(score: float, max_score: float | None = None) -> str:
    if max_score is not None and max_score > 0:
        pct = 100.0 * score / max_score
    else:
        pct = score
    if pct >= 90:
        return "A+"
    if pct >= 80:
        return "A"
    if pct >= 70:
        return "B"
    if pct >= 60:
        return "C"
    return "D"


def clamp(n, lo, hi):
    return max(lo, min(hi, n))



def snap_half(n) -> float:
    """Nearest 0.5; halfway cases move away from zero.

    Shared helper for published customer scores: technical dimension scores,
    Content GEO dimension and overall scores, and the combined /100.
    They only use 0 / 0.5 increments (e.g. 7.5, 15), never 0.1-level
    precision such as 7.3, 5.4, or 15.1. Technical overall stays an integer.
    """
    x = float(n)
    if x >= 0:
        return math.floor(x * 2 + 0.5) / 2.0
    return -math.floor(-x * 2 + 0.5) / 2.0





def score_ia(types: dict, pages: list | None = None, corpus_text: str = "") -> tuple[float, list]:
    notes = []
    pages = pages or []
    try:
        import geo_signals_v13 as v13
        cov = v13.intent_coverage(types, pages, corpus_text)
        present = cov["present"]
        missing = cov["missing"]
        notes.append(cov["note"])
        if cov["multi_market_claim"] and not cov["market_pages_in_sample"]:
            notes.append(
                "Site claims multi-market coverage but sample lacks independent "
                "market/region/project URLs (answerability gap — not city-keyword SEO)."
            )
    except Exception:
        needed = ["product", "case", "about", "solution", "rd", "news"]
        present = [n for n in needed if types.get(n, 0) > 0]
        missing = [n for n in needed if not types.get(n)]
    # Scaled to /20: base + presence + knowledge extras (weights unchanged)
    score = 3
    score += 2.5 * min(6, len([p for p in present if p != "market"]))
    if types.get("faq") or types.get("download"):
        score += 2
    if "market" in present:
        score += 1
    coverage = (pages and (pages[0].get("_coverage") if pages else None)) or {}
    # Prefer explicit coverage when the caller attached it; else we only know sampled types.
    uneval = set((coverage or {}).get("unevaluated_types") or [])
    if missing:
        still_missing, not_eval = [], []
        for m in missing:
            if m in uneval or m == "product" and "product_detail" in uneval:
                not_eval.append(m)
            else:
                still_missing.append(m)
        if not_eval:
            notes.append("未评估（已发现但未抽样）的页面类型：" + "、".join(not_eval) + "。不按缺失计 0。")
        if still_missing:
            notes.append("抽样与发现范围内未见：" + "、".join(still_missing) + "（范围内观察，不是对未抓页面的断言）。")
    if types.get("product", 0) and types.get("case", 0) == 0:
        if "case" in uneval:
            notes.append("产品页已抽样，案例页标为未评估，不把经销商大会或新闻当成交付案例。")
        else:
            notes.append("抽样中有产品页，但未见深度项目案例页。经销商峰会/大会不算交付案例。")
    if types.get("about") and not types.get("rd"):
        if "rd" in uneval:
            notes.append("研发/规格页未评估，不因 About 页未穷尽集团业务而记缺口。")
        else:
            notes.append("抽样未见独立研发/规格 URL；这不等于要求 About 页列出全部集团业务。")
    return clamp(snap_half(score), 0, 20), notes


def score_taxonomy(types: dict, pages: list) -> tuple[float, list]:
    notes = []
    score = 7  # /15 scale
    score += min(6, len([k for k, v in types.items() if v > 0 and k != "other"]))
    products = [p for p in pages if p.get("page_type") == "product"]
    thin_prod = [p for p in products if p.get("word_count", 0) < 120]
    if thin_prod:
        score -= min(4, len(thin_prod) * 1.5)
        notes.append(f"{len(thin_prod)} product page(s) are thin — taxonomy exists but depth is weak.")
    cases = [p for p in pages if p.get("page_type") == "case"]
    empty_cases = [p for p in cases if p.get("word_count", 0) < 60]
    if empty_cases:
        score -= 3
        notes.append("Case pages in sample lack extractable project narrative.")
    if types.get("news", 0) >= 2 and types.get("case", 0) <= 1:
        notes.append("Evidence is skewed to news posts rather than structured case/product knowledge pages.")
        score -= 1.5
    return clamp(snap_half(score), 0, 15), notes


def score_writing(pages: list) -> tuple[float, list]:
    notes = []
    if not pages:
        return 0.0, ["No text to assess writing quality."]
    score = 0.0
    for p in pages:
        wc = p.get("word_count", 0)
        local = 0
        if wc >= 200:
            local += 1.2
        elif wc >= 80:
            local += 0.6
        if p.get("spec_hits", 0) >= 2:
            local += 1.0
        if p.get("evidence_hits", 0) >= 2:
            local += 0.8
        # slogan-heavy without specs
        if p.get("slogan_hits", 0) >= 3 and p.get("spec_hits", 0) < 2:
            local -= 0.8
        if len(p.get("headings") or []) >= 3:
            local += 0.5
        score += clamp(local, 0, 3)
    # normalize to 20 (v1.1)
    avg = score / max(1, len(pages))
    final = clamp(snap_half(avg * (20 / 3)), 0, 20)  # avg~3 → 20
    slogan_pages = sum(1 for p in pages if p.get("slogan_hits", 0) >= 3 and p.get("spec_hits", 0) < 2)
    if slogan_pages:
        notes.append(f"{slogan_pages} page(s) lean on slogans without enough specs/standards.")
    if not any(p.get("spec_hits", 0) >= 3 for p in pages):
        notes.append("Few extractable specification blocks across the sampled pages (not a claim about unfetched product-detail URLs).")
    locked_pages = [p for p in pages if p.get("image_locked")]
    if locked_pages:
        final = clamp(snap_half(final - min(6.0, 1.5 * len(locked_pages))), 0, 20)
        notes.append(
            f"{len(locked_pages)} page(s) appear image-locked / non-extractable — "
            "move key facts into HTML text (product/case/article field checklists)."
        )
    return final, notes


def score_authority(pages: list, offsite: list | None = None) -> tuple[float, list]:
    """Score the *publishing system*, not raw credential keyword density."""
    notes = []
    score = 2.0  # baseline if any corporate site
    deep_cases = [p for p in pages if p.get("page_type") == "case" and p.get("word_count", 0) >= 100]
    thin_cases = [p for p in pages if p.get("page_type") == "case" and p.get("word_count", 0) < 100]
    if deep_cases:
        score += min(4, 2 * len(deep_cases))
    else:
        notes.append("No deep on-site delivery case study observed in the sample. A dealer summit or event page is not a delivery case study.")
        if thin_cases:
            score += 0.5
            notes.append("Case-like URLs exist but are too thin to cite.")
    if any(p.get("page_type") == "rd" for p in pages):
        score += 2
    else:
        notes.append("No dedicated R&D/patent URL in sample — patents may only appear in About copy.")
    about = [p for p in pages if p.get("page_type") == "about"]
    if about and about[0].get("evidence_hits", 0) >= 5:
        score += 2  # raw assets exist
        notes.append("About page carries dense credentials — better split into proof pages with source links.")
    news_ev = [p for p in pages if p.get("page_type") == "news" and p.get("evidence_hits", 0) >= 3]
    if news_ev:
        score += min(2, len(news_ev))
        notes.append("Awards/proof appear mainly as news posts rather than evergreen proof hubs.")
    if offsite:
        # Off-site assets help only a little until mirrored on-site
        score += min(2, 0.5 * len(offsite))
        notes.append(f"{len(offsite)} off-site evidence item(s) listed — should be mirrored onto official URLs with source links.")
    # v1.3: unverified marketing claims (round numbers / superlatives without proof links)
    claim_pages = 0
    claim_examples = []
    for p in pages:
        claims = p.get("unverified_claims") or []
        if not claims:
            try:
                import geo_signals_v13 as v13
                claims = v13.detect_unverified_claims(p.get("text_excerpt") or "", [])
            except Exception:
                claims = []
        if claims:
            claim_pages += 1
            claim_examples.extend(c.get("claim") for c in claims[:2])
    if claim_pages:
        score -= min(4.0, 1.5 * claim_pages)
        notes.append(
            f"{claim_pages} page(s) state large round numbers or superlatives without nearby "
            f"evidence links (e.g. {', '.join(str(x) for x in claim_examples[:3])}). "
            "Publish proof pages and link claims to them — entity trust for AI citation, not local SEO."
        )
    return clamp(snap_half(score), 0, 20), notes


def score_query(pages: list, ai_checks: list | None = None) -> tuple[float, list]:
    """Baseline heuristic from page types; AI checks refine in enrichment. Max 25 (v1.1)."""
    notes = []
    types = {p.get("page_type") for p in pages}
    score = 5  # brand home exists
    if "product" in types:
        score += 4
    if "case" in types:
        score += 4
    if "about" in types:
        score += 3
    if "solution" in types:
        score += 3
    if "faq" in types or "rd" in types:
        score += 3
    if ai_checks:
        cited = sum(1 for c in ai_checks if c.get("cited_official_domain"))
        mentioned = sum(1 for c in ai_checks if c.get("mentioned_brand"))
        n = max(1, len(ai_checks))
        score = score * 0.5 + 12.5 * (0.4 * mentioned / n + 0.6 * cited / n)
        notes.append(
            f"AI/search checks: brand mentioned in {mentioned}/{n}; official domain cited in {cited}/{n}."
        )
        if cited == 0:
            notes.append("No checked question cited the official domain in retrieval proxies.")
    else:
        notes.append("AI mention checks not attached yet — Agent should fill query × engine table.")
    return clamp(snap_half(score), 0, 25), notes


def analyze(run_dir: str, ai_checks: list | None = None, offsite: list | None = None) -> dict:
    extract_path = os.path.join(run_dir, "content_extract.json")
    if not os.path.isfile(extract_path):
        raise SystemExit(f"Missing {extract_path}; run content_extract.py first")
    extract = json.load(open(extract_path, encoding="utf-8"))
    pages = extract.get("pages") or []
    types = extract.get("page_type_counts") or {}
    site = {}
    sp = os.path.join(run_dir, "site.json")
    if os.path.isfile(sp):
        try:
            site = json.load(open(sp, encoding="utf-8"))
        except (ValueError, OSError):
            site = {}
    sitemap_urls = page_coverage.load_sitemap_urls(run_dir)
    coverage = page_coverage.coverage_report(pages, site, sitemap_urls)
    for p in pages:
        p["_coverage"] = coverage
    # Event pages (dealer summit, etc.) must not inflate case counts.
    if types.get("event"):
        types = dict(types)

    crawl_probe = {}
    probe_path = os.path.join(run_dir, "evidence", "crawl_probe.json")
    if os.path.isfile(probe_path):
        crawl_probe = json.load(open(probe_path, encoding="utf-8"))

    robots_ok = os.path.isfile(os.path.join(run_dir, "evidence", "robots.txt")) and \
        os.path.getsize(os.path.join(run_dir, "evidence", "robots.txt")) > 20
    sitemap_ok = os.path.isfile(os.path.join(run_dir, "evidence", "sitemap.xml")) and \
        os.path.getsize(os.path.join(run_dir, "evidence", "sitemap.xml")) > 50

    # Detect failed direct crawl
    crawl_ok = False
    if crawl_probe.get("box_curl_results"):
        crawl_ok = any(r.get("status") == 200 for r in crawl_probe["box_curl_results"])
    else:
        # if we have real HTML with status from site.json
        site = {}
        sp = os.path.join(run_dir, "site.json")
        if os.path.isfile(sp):
            site = json.load(open(sp, encoding="utf-8"))
        crawl_ok = any((p.get("status") == 200) for p in site.get("pages_sampled") or [])

    unevaluable = len(pages) == 0
    corpus = " ".join((p.get("text_excerpt") or "") for p in pages)
    ia_s, ia_n = score_ia(types, pages, corpus)
    tax_s, tax_n = score_taxonomy(types, pages)
    wr_s, wr_n = score_writing(pages)
    au_s, au_n = score_authority(pages, offsite)
    qu_s, qu_n = score_query(pages, ai_checks)

    dimensions = []
    for key, cid, name, mx in DIMS:
        val = {
            "information_architecture": ia_s,
            "taxonomy_gaps": tax_s,
            "writing_quality": wr_s,
            "authority_evidence": au_s,
            "query_coverage": qu_s,
        }[key]
        notes = {
            "information_architecture": ia_n,
            "taxonomy_gaps": tax_n,
            "writing_quality": wr_n,
            "authority_evidence": au_n,
            "query_coverage": qu_n,
        }[key]
        dimensions.append({
            "id": cid,
            "key": key,
            "name": name,
            "score": val,
            "max": mx,
            "grade": grade_for(val, mx),
            "notes": notes,
            "narr": "",
            "callout": "",
        })

    total = snap_half(sum(d["score"] for d in dimensions))
    confidence = "high" if crawl_ok and pages else ("provisional" if pages else "none")
    grade = "F" if unevaluable else grade_for(total, 100)
    complete_deferred = bool(coverage.get("complete_total_deferred"))

    engine = {
        "schema": "content_geo.engine.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": run_dir,
        "domain": extract.get("domain"),
        "site_url": extract.get("site_url"),
        "unevaluable": unevaluable,
        "confidence": confidence,
        "fetch_mode": "direct_crawl" if crawl_ok else "alternate_or_snapshot",
        "crawl_probe": crawl_probe,
        "overall_score": None if unevaluable else total,
        "grade": grade,
        "score_scope": "sampled_pages",
        "complete_total_deferred": complete_deferred,
        "coverage": coverage,
        "unevaluated_types": coverage.get("unevaluated_types") or [],
        "score_scope_note": coverage.get("note_zh") or coverage.get("note_en"),
        "dimensions": dimensions,
        "page_type_counts": types,
        "pages_analyzed": len(pages),
        "ai_checks": ai_checks or [],
        "offsite_evidence": offsite or [],
        "sample_urls": [p.get("url") or p.get("path") for p in pages],
        "strengths": [],
        "findings": [],
        "priority_actions": [],
        "overall_summary": "",
        "closing": "",
        "rubric": "content_scoring.md v1.2",
        "scoring_version": "v1.3",
        "note": "Heuristic engine scores. Agent must enrich narratives and AI-check table per content_prompts.md.",
    }
    # Attach v1.3 structured findings (agent may rewrite prose)
    findings = []
    locked = [p for p in pages if p.get("image_locked")]
    if locked:
        findings.append({
            "severity": "高",
            "id": "C-WRITE-IMG",
            "title": "Main content appears image-locked or non-extractable",
            "problem": f"{len(locked)} sampled page(s) lack enough extractable prose for AI citation.",
            "impact": "Generative engines cannot reliably lift specs, outcomes, or definitions when facts live only in images or empty fields.",
            "solution": "Use product / case / article field checklists; put citeable facts in HTML text.",
            "evidence": [{"url": p.get("url") or "", "quote": "; ".join((p.get("image_locked_reasons") or [])[:2])} for p in locked[:4]],
        })
    if any(d["id"] == "C-AUTH" or d["key"] == "authority_evidence" for d in dimensions):
        # surface claim note if present in authority notes
        au_notes = next((d["notes"] for d in dimensions if d["key"] == "authority_evidence"), [])
        if any("superlatives" in n or "round numbers" in n for n in au_notes):
            findings.append({
                "severity": "中",
                "id": "C-AUTH-CLAIM",
                "title": "Unverified marketing claims without on-site evidence links",
                "problem": "Large round numbers or superlatives appear without nearby proof URLs.",
                "impact": "AI systems may omit the brand or refuse to cite unverifiable claims.",
                "solution": "Publish proof pages (certs, patents, cases) and link each claim to evidence.",
            })
    engine["findings"] = findings
    out = os.path.join(run_dir, "content.engine.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(engine, f, ensure_ascii=False, indent=2)
    return engine


def main():
    if len(sys.argv) < 2:
        print("Usage: content_analyze.py <run_dir> [--ai-checks path.json] [--offsite path.json]")
        sys.exit(2)
    run_dir = sys.argv[1]
    ai_checks = None
    offsite = None
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--ai-checks" and i + 1 < len(args):
            ai_checks = json.load(open(args[i + 1], encoding="utf-8"))
            if isinstance(ai_checks, dict):
                ai_checks = ai_checks.get("checks") or ai_checks.get("ai_checks") or []
            i += 2
        elif args[i] == "--offsite" and i + 1 < len(args):
            offsite = json.load(open(args[i + 1], encoding="utf-8"))
            if isinstance(offsite, dict):
                offsite = offsite.get("items") or offsite.get("offsite_evidence") or []
            i += 2
        else:
            i += 1
    eng = analyze(run_dir, ai_checks=ai_checks, offsite=offsite)
    print(f"Content engine → score {eng['overall_score']} ({eng['grade']}) confidence={eng['confidence']}")


if __name__ == "__main__":
    main()
