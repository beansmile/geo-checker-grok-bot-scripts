#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Heuristic Content GEO scoring from content_extract.json (+ optional AI checks).

Writes content.engine.json. Agent enrichment fills narratives into content_report.json.
Does NOT touch technical scoring.md / report.engine.json.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

DIMS = [
    ("seo_discoverability", "C-SEO", "SEO content discoverability", 25),
    ("information_architecture", "C-IA", "Information architecture", 15),
    ("taxonomy_gaps", "C-TAX", "Content taxonomy & gaps", 10),
    ("writing_quality", "C-WRITE", "Writing quality", 15),
    ("authority_evidence", "C-AUTH", "Authority & evidence publishing", 15),
    ("query_coverage", "C-QUERY", "Target query coverage", 20),
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


def score_seo(pages, crawl_ok: bool, robots_ok: bool, sitemap_ok: bool) -> tuple[float, list]:
    notes = []
    if not pages:
        return 0.0, ["No page bodies available for SEO content checks."]
    score = 0.0
    # titles / H1 uniqueness
    titles = [p.get("title") or "" for p in pages]
    h1s = [" | ".join(p.get("h1") or []) for p in pages]
    with_title = sum(1 for t in titles if len(t) >= 8)
    with_h1 = sum(1 for h in h1s if h)
    uniq_titles = len(set(t.lower() for t in titles if t))
    score += 6 * (with_title / max(1, len(pages)))
    score += 4 * (with_h1 / max(1, len(pages)))
    if uniq_titles >= max(1, int(0.7 * len([t for t in titles if t]))):
        score += 3
    else:
        notes.append("Many pages share similar or missing titles — weak intent matching.")
    # meta
    with_meta = sum(1 for p in pages if (p.get("meta_description") or "").strip())
    score += 3 * (with_meta / max(1, len(pages)))
    if with_meta == 0:
        notes.append("No meta descriptions observed in sampled pages (HTML may be snapshot text).")
    # thin content
    thin = sum(1 for p in pages if p.get("word_count", 0) < 80 and p.get("page_type") in ("product", "case", "solution", "home"))
    if thin:
        score -= min(5, thin * 1.5)
        notes.append(f"{thin} product/case/home-like pages look thin (<80 tokens).")
    # internal links
    avg_links = sum(p.get("internal_link_count", 0) for p in pages) / max(1, len(pages))
    score += clamp(avg_links / 10.0, 0, 3)
    # discovery infrastructure
    if crawl_ok:
        score += 2
    else:
        notes.append("Direct crawler access failed — SEO/AI discovery risk (verify Search Console & server logs).")
        score += 0
    if sitemap_ok:
        score += 2
    else:
        notes.append("Sitemap not verified in this run.")
    if robots_ok:
        score += 2
    else:
        notes.append("robots.txt not verified in this run.")
    # image alts when HTML present
    html_pages = [p for p in pages if p.get("images_total", 0) > 0]
    if html_pages:
        alt_rate = sum(p["images_with_alt"] for p in html_pages) / max(1, sum(p["images_total"] for p in html_pages))
        score += 2 * alt_rate
    return clamp(round(score, 1), 0, 25), notes


def score_ia(types: dict) -> tuple[float, list]:
    notes = []
    needed = ["product", "case", "about", "solution", "rd", "news"]
    present = [n for n in needed if types.get(n, 0) > 0]
    # home counted separately
    score = 2  # base for having any site
    score += 2 * len(present)  # up to 12
    if types.get("faq") or types.get("download"):
        score += 1
    missing = [n for n in needed if not types.get(n)]
    if missing:
        notes.append("Missing or not sampled page types: " + ", ".join(missing))
    if types.get("product", 0) and types.get("case", 0) == 0:
        notes.append("Products exist without deep project-case pages in sample.")
    if types.get("about") and not types.get("rd"):
        notes.append("R&D / patent / specs likely folded into About rather than dedicated URLs.")
    return clamp(score, 0, 15), notes


def score_taxonomy(types: dict, pages: list) -> tuple[float, list]:
    notes = []
    score = 5
    # reward diversity
    score += min(4, len([k for k, v in types.items() if v > 0 and k != "other"]))
    # thin product pages
    products = [p for p in pages if p.get("page_type") == "product"]
    thin_prod = [p for p in products if p.get("word_count", 0) < 120]
    if thin_prod:
        score -= min(3, len(thin_prod))
        notes.append(f"{len(thin_prod)} product page(s) are thin — taxonomy exists but depth is weak.")
    cases = [p for p in pages if p.get("page_type") == "case"]
    empty_cases = [p for p in cases if p.get("word_count", 0) < 60]
    if empty_cases:
        score -= 2
        notes.append("Case pages in sample lack extractable project narrative.")
    if types.get("news", 0) >= 2 and types.get("case", 0) <= 1:
        notes.append("Evidence is skewed to news posts rather than structured case/product knowledge pages.")
        score -= 1
    return clamp(score, 0, 10), notes


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
    # normalize to 15
    avg = score / max(1, len(pages))
    final = clamp(round(avg * 5, 1), 0, 15)  # avg~3 → 15
    slogan_pages = sum(1 for p in pages if p.get("slogan_hits", 0) >= 3 and p.get("spec_hits", 0) < 2)
    if slogan_pages:
        notes.append(f"{slogan_pages} page(s) lean on slogans without enough specs/standards.")
    if not any(p.get("spec_hits", 0) >= 3 for p in pages):
        notes.append("Few extractable specification blocks across the sample.")
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
        notes.append("No deep on-site case write-up observed in sample.")
        if thin_cases:
            score += 0.5
            notes.append("Case URLs exist but are too thin to cite.")
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
    return clamp(round(score, 1), 0, 15), notes


def score_query(pages: list, ai_checks: list | None = None) -> tuple[float, list]:
    """Baseline heuristic from page types; AI checks refine in enrichment."""
    notes = []
    types = {p.get("page_type") for p in pages}
    # rough answerability proxies
    score = 4  # brand home exists
    if "product" in types:
        score += 3
    if "case" in types:
        score += 3
    if "about" in types:
        score += 2
    if "solution" in types:
        score += 2
    if "faq" in types or "rd" in types:
        score += 2
    # AI checks: if present, adjust
    if ai_checks:
        cited = sum(1 for c in ai_checks if c.get("cited_official_domain"))
        mentioned = sum(1 for c in ai_checks if c.get("mentioned_brand"))
        n = max(1, len(ai_checks))
        # category questions usually fail → keep modest
        score = score * 0.5 + 10 * (0.4 * mentioned / n + 0.6 * cited / n)
        notes.append(
            f"AI/search checks: brand mentioned in {mentioned}/{n}; official domain cited in {cited}/{n}."
        )
        if cited == 0:
            notes.append("No checked question cited ltzm.com / official domain in retrieval proxies.")
    else:
        notes.append("AI mention checks not attached yet — Agent should fill query × engine table.")
    return clamp(round(score, 1), 0, 20), notes


def analyze(run_dir: str, ai_checks: list | None = None, offsite: list | None = None) -> dict:
    extract_path = os.path.join(run_dir, "content_extract.json")
    if not os.path.isfile(extract_path):
        raise SystemExit(f"Missing {extract_path}; run content_extract.py first")
    extract = json.load(open(extract_path, encoding="utf-8"))
    pages = extract.get("pages") or []
    types = extract.get("page_type_counts") or {}

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
    seo_s, seo_n = score_seo(pages, crawl_ok, robots_ok, sitemap_ok)
    ia_s, ia_n = score_ia(types)
    tax_s, tax_n = score_taxonomy(types, pages)
    wr_s, wr_n = score_writing(pages)
    au_s, au_n = score_authority(pages, offsite)
    qu_s, qu_n = score_query(pages, ai_checks)

    dimensions = []
    for key, cid, name, mx in DIMS:
        val = {
            "seo_discoverability": seo_s,
            "information_architecture": ia_s,
            "taxonomy_gaps": tax_s,
            "writing_quality": wr_s,
            "authority_evidence": au_s,
            "query_coverage": qu_s,
        }[key]
        notes = {
            "seo_discoverability": seo_n,
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

    total = round(sum(d["score"] for d in dimensions), 1)
    confidence = "high" if crawl_ok and pages else ("provisional" if pages else "none")
    grade = "F" if unevaluable else grade_for(total, 100)

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
        "rubric": "content_scoring.md v1.0",
        "note": "Heuristic engine scores. Agent must enrich narratives and AI-check table per content_prompts.md.",
    }
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
