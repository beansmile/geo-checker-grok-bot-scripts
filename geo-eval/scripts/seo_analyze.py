#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SEO content discoverability scoring (technical report add-on).

Separate from the nine-dimension 100-point formula in scoring.md.
Shared by analyze.py (technical) and optionally content pipelines for reuse.
Rubric: seo_scoring.md
"""

from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from typing import Any


def clamp(n, lo, hi):
    return max(lo, min(hi, n))


def grade_for_pct(pct: float) -> str:
    if pct >= 90:
        return "A+"
    if pct >= 80:
        return "A"
    if pct >= 70:
        return "B"
    if pct >= 60:
        return "C"
    return "D"


class _LiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.meta_desc = ""
        self.h1 = []
        self._h1 = False
        self._h1_buf = []
        self.links = []
        self.images_total = 0
        self.images_with_alt = 0
        self._skip = 0
        self._text = []

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (ad.get("name") or ad.get("property") or "").lower()
            if name in ("description", "og:description") and not self.meta_desc:
                self.meta_desc = (ad.get("content") or "").strip()
        elif tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "h1":
            self._h1 = True
            self._h1_buf = []
        elif tag == "a" and "href" in ad:
            self.links.append(ad.get("href") or "")
        elif tag == "img":
            self.images_total += 1
            if (ad.get("alt") or "").strip():
                self.images_with_alt += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        elif tag == "h1" and self._h1:
            text = re.sub(r"\s+", " ", "".join(self._h1_buf)).strip()
            if text:
                self.h1.append(text)
            self._h1 = False

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        elif self._h1:
            self._h1_buf.append(data)
        else:
            self._text.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._text)).strip()


def page_from_html(url: str, html: str, role: str = "content") -> dict:
    p = _LiteParser()
    try:
        p.feed(html or "")
    except Exception:
        pass
    text = p.text()
    words = len(text.split()) if text else 0
    page_type = "home" if role == "home" else (
        "product" if re.search(r"product|sku|goods", url, re.I) else
        "case" if re.search(r"case|project|engineering", url, re.I) else
        "about" if re.search(r"about", url, re.I) else
        role or "content"
    )
    return {
        "url": url,
        "title": (p.title or "").strip(),
        "meta_description": p.meta_desc,
        "h1": p.h1,
        "word_count": words,
        "internal_link_count": len([l for l in p.links if l.startswith("/") or "://" not in l]),
        "images_total": p.images_total,
        "images_with_alt": p.images_with_alt,
        "page_type": page_type,
        "role": role,
    }


def pages_from_content_extract(extract: dict) -> list[dict]:
    return list(extract.get("pages") or [])


def pages_from_technical_run(run_dir: str) -> list[dict]:
    """Build lightweight page dicts from evidence HTML + site.json roles."""
    pages_dir = os.path.join(run_dir, "evidence", "pages")
    site = {}
    sp = os.path.join(run_dir, "site.json")
    if os.path.isfile(sp):
        site = json.load(open(sp, encoding="utf-8"))
    role_by_url = {}
    for p in site.get("pages_sampled") or []:
        if isinstance(p, dict):
            role_by_url[p.get("url") or ""] = p.get("role") or "content"
        elif isinstance(p, str):
            role_by_url[p] = "content"

    out = []
    if not os.path.isdir(pages_dir):
        return out
    for name in sorted(os.listdir(pages_dir)):
        if not name.endswith((".html", ".htm")):
            continue
        path = os.path.join(pages_dir, name)
        raw = open(path, encoding="utf-8", errors="replace").read()
        # Guess URL from filename or pages.list
        url = role_by_url and next((u for u in role_by_url if name.replace(".html", "") in u), "") or name
        # Prefer matching by basename patterns in site
        for u, role in role_by_url.items():
            base = os.path.basename(u.rstrip("/")) or "index"
            if base in name or name.startswith(base.replace(".", "_")):
                url = u
                break
        role = role_by_url.get(url, "content")
        if name in ("home.html", "index.html"):
            role = "home"
            url = url or site.get("url") or ""
        out.append(page_from_html(url or name, raw, role=role))
    return out


def probe_flags(run_dir: str) -> tuple[bool, bool, bool, dict]:
    """Return crawl_ok, robots_ok, sitemap_ok, crawl_probe."""
    crawl_probe = {}
    probe_path = os.path.join(run_dir, "evidence", "crawl_probe.json")
    if os.path.isfile(probe_path):
        crawl_probe = json.load(open(probe_path, encoding="utf-8"))

    robots_path = os.path.join(run_dir, "evidence", "robots.txt")
    sitemap_path = os.path.join(run_dir, "evidence", "sitemap.xml")
    # Also accept sitemap variants
    if not os.path.isfile(sitemap_path):
        for alt in ("sitemap_index.xml", "sitemap.txt"):
            p = os.path.join(run_dir, "evidence", alt)
            if os.path.isfile(p):
                sitemap_path = p
                break

    robots_ok = os.path.isfile(robots_path) and os.path.getsize(robots_path) > 20
    sitemap_ok = os.path.isfile(sitemap_path) and os.path.getsize(sitemap_path) > 50

    crawl_ok = False
    if crawl_probe.get("box_curl_results"):
        crawl_ok = any(r.get("status") == 200 for r in crawl_probe["box_curl_results"])
    else:
        site = {}
        sp = os.path.join(run_dir, "site.json")
        if os.path.isfile(sp):
            site = json.load(open(sp, encoding="utf-8"))
        sampled = site.get("pages_sampled") or []
        if sampled and isinstance(sampled[0], dict):
            crawl_ok = any((p.get("status") == 200) for p in sampled)
        elif os.path.isdir(os.path.join(run_dir, "evidence", "pages")):
            htmls = [
                f for f in os.listdir(os.path.join(run_dir, "evidence", "pages"))
                if f.endswith(".html")
            ]
            crawl_ok = len(htmls) > 0 and not crawl_probe.get("box_curl_results")

    return crawl_ok, robots_ok, sitemap_ok, crawl_probe


def score_seo(
    pages: list[dict],
    crawl_ok: bool,
    robots_ok: bool,
    sitemap_ok: bool,
) -> tuple[float, list[str]]:
    """Return (score /25, notes). Same heuristic as former content C-SEO."""
    notes: list[str] = []
    if not pages:
        return 0.0, ["No page bodies available for SEO content checks."]

    score = 0.0
    titles = [p.get("title") or "" for p in pages]
    h1s = [" | ".join(p.get("h1") or []) if isinstance(p.get("h1"), list) else str(p.get("h1") or "") for p in pages]
    with_title = sum(1 for t in titles if len(t) >= 8)
    with_h1 = sum(1 for h in h1s if h)
    nonempty_titles = [t for t in titles if t]
    uniq_titles = len(set(t.lower() for t in nonempty_titles))
    score += 6 * (with_title / max(1, len(pages)))
    score += 4 * (with_h1 / max(1, len(pages)))
    if nonempty_titles and uniq_titles >= max(1, int(0.7 * len(nonempty_titles))):
        score += 3
    else:
        notes.append("Many pages share similar or missing titles — weak intent matching.")

    with_meta = sum(1 for p in pages if (p.get("meta_description") or "").strip())
    score += 3 * (with_meta / max(1, len(pages)))
    if with_meta == 0:
        notes.append("No meta descriptions observed in sampled pages.")

    thin = sum(
        1
        for p in pages
        if p.get("word_count", 0) < 80
        and p.get("page_type") in ("product", "case", "solution", "home")
    )
    if thin:
        score -= min(5, thin * 1.5)
        notes.append(f"{thin} product/case/home-like pages look thin (<80 tokens).")

    avg_links = sum(p.get("internal_link_count", 0) for p in pages) / max(1, len(pages))
    score += clamp(avg_links / 10.0, 0, 3)
    if avg_links < 3:
        notes.append("Weak internal linking among sampled pages — important URLs may lack crawl paths.")

    if crawl_ok:
        score += 2
    else:
        notes.append(
            "Direct crawler access failed or unverified — SEO/AI discovery risk "
            "(check Search Console & server logs; see Access findings if present)."
        )
    if sitemap_ok:
        score += 2
    else:
        notes.append("Sitemap not verified in this run.")
    if robots_ok:
        score += 2
    else:
        notes.append("robots.txt not verified in this run.")

    html_pages = [p for p in pages if p.get("images_total", 0) > 0]
    if html_pages:
        alt_rate = sum(p["images_with_alt"] for p in html_pages) / max(
            1, sum(p["images_total"] for p in html_pages)
        )
        score += 2 * alt_rate
        if alt_rate < 0.5:
            notes.append("Many images lack alt text in HTML sample.")

    return clamp(round(score, 1), 0, 25), notes


def build_seo_block(
    run_dir: str,
    pages: list[dict] | None = None,
    narr: str = "",
    callout: str = "",
    findings: list | None = None,
) -> dict[str, Any]:
    crawl_ok, robots_ok, sitemap_ok, crawl_probe = probe_flags(run_dir)
    if pages is None:
        # Prefer content_extract if present (richer page_type), else technical HTML
        extract_path = os.path.join(run_dir, "content_extract.json")
        if os.path.isfile(extract_path):
            pages = pages_from_content_extract(json.load(open(extract_path, encoding="utf-8")))
        else:
            pages = pages_from_technical_run(run_dir)

    score, notes = score_seo(pages or [], crawl_ok, robots_ok, sitemap_ok)
    confidence = "high" if crawl_ok and pages else ("provisional" if pages else "none")
    pct = (100.0 * score / 25.0) if score is not None else 0
    return {
        "score": score,
        "max": 25,
        "grade": grade_for_pct(pct) if pages else "F",
        "confidence": confidence,
        "crawl_ok": crawl_ok,
        "robots_verified": robots_ok,
        "sitemap_verified": sitemap_ok,
        "pages_analyzed": len(pages or []),
        "notes": notes,
        "narr": narr,
        "callout": callout,
        "findings": findings or [],
        "rubric": "seo_scoring.md v1.0",
        "separate_from_nine_dim": True,
        "crawl_probe_present": bool(crawl_probe),
    }


def attach_to_report(report: dict, run_dir: str) -> dict:
    """Mutate/return report with seo_discoverability attached (does not change overall_score)."""
    report["seo_discoverability"] = build_seo_block(run_dir)
    return report


if __name__ == "__main__":
    import sys

    rd = sys.argv[1] if len(sys.argv) > 1 else "."
    block = build_seo_block(rd)
    print(json.dumps(block, ensure_ascii=False, indent=2))
