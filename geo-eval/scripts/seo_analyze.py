#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SEO content discoverability scoring (technical dimension, scoring v1.3).

Heuristic raw score is /25; scaled into the technical 100 as a 15-point dim:
  dim_score = snap_half(min(15, max(0, raw_25 * 15 / 25)))  # published /15, 0 / 0.5 increments
Weights unchanged from v1.2; v1.3 adds richer sub-heuristics (image-locked thin,
URL hygiene notes/findings). Shared by analyze.py and content pipelines.
Rubric: seo_scoring.md
"""

from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from typing import Any

try:
    from content_analyze import snap_half
except ImportError:  # pragma: no cover
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from content_analyze import snap_half


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
        self.canonical = ""
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
        elif tag == "link":
            rel = (ad.get("rel") or "").lower()
            if "canonical" in rel and not self.canonical:
                self.canonical = (ad.get("href") or "").strip()
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
    page = {
        "url": url,
        "title": (p.title or "").strip(),
        "meta_description": p.meta_desc,
        "h1": p.h1,
        "word_count": words,
        "internal_link_count": len([l for l in p.links if l.startswith("/") or "://" not in l]),
        "images_total": p.images_total,
        "images_with_alt": p.images_with_alt,
        "canonical": p.canonical,
        "html": html or "",
        "page_type": page_type,
        "role": role,
    }
    try:
        import geo_signals_v13 as v13
        lock = v13.detect_image_locked(page)
        page["image_locked"] = bool(lock.get("locked"))
        page["image_locked_reasons"] = lock.get("reasons") or []
    except Exception:
        page["image_locked"] = False
        page["image_locked_reasons"] = []
    return page


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
) -> tuple[float, list[str], list[dict]]:
    """Return (raw_score /25, notes, findings). Weights same as v1.2; v1.3 richer signals."""
    notes: list[str] = []
    findings: list[dict] = []
    if not pages:
        return 0.0, ["No page bodies available for SEO content checks."], []

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
        and p.get("page_type") in ("product", "case", "solution", "home", "news", "article")
    )
    locked = sum(1 for p in pages if p.get("image_locked"))
    if thin or locked:
        penalty = min(5, thin * 1.5 + locked * 0.5)
        score -= penalty
        if locked:
            notes.append(
                f"{locked} page(s) look image-locked / non-extractable (facts may live only in media). "
                "Put specs and proof into HTML text — see product/case/article field checklists."
            )
        if thin:
            notes.append(f"{thin} product/case/home/news-like pages look thin (<80 tokens).")

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

    # v1.3 URL hygiene — small raw deductions; never replay ACC HTTPS penalty here
    try:
        import geo_signals_v13 as v13
        hy = v13.url_hygiene_findings(pages, [p.get("url") or "" for p in pages])
        for f in hy:
            if f.get("id") == "SEO-URL-02":
                f["scored"] = False
                f["severity"] = f.get("severity") or "低"
        findings.extend(hy)
        if any(f.get("id") == "SEO-URL-01" for f in hy):
            score -= 1.5
            notes.append("Homepage soft/JS splash redirect detected (discoverability hygiene).")
        if any(f.get("id") == "SEO-URL-02" for f in hy):
            # Missing canonical is an auxiliary hint, not a core deduction.
            notes.append("Canonical tags missing on most sampled pages (advisory; missing tag is less serious than a conflicting canonical).")
        if any(f.get("id") == "SEO-URL-03" for f in hy):
            score -= 1.0
            notes.append("Canonical mismatches page URL on one or more samples (wrong configuration, scored).")
        if any(f.get("id") == "SEO-URL-04" for f in hy):
            score -= 1.0
            notes.append("Multiple home host/path variants without 301 evidence in sample.")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"URL hygiene checks skipped: {exc}")

    # hreflang incomplete coverage and html lang issues are advisory only.
    # A lang attribute issue is not a Google language-identification failure.
    adv = advisory_i18n_and_links(pages)
    notes.extend(adv["notes"])
    findings.extend(adv["findings"])

    return clamp(round(score, 1), 0, 25), notes, findings


def advisory_i18n_and_links(pages: list[dict]) -> dict:
    """hreflang / html lang / sampled broken internals — advisory, not core weight."""
    import re
    notes, findings = [], []
    hreflang_pages = 0
    langs = set()
    missing_lang = 0
    href_re = re.compile(r"""hreflang\s*=\s*['"][^'"]+['"]""", re.I)
    lang_re = re.compile(r"""<html[^>]*\slang=['"]([^'"]+)""", re.I)
    a_re = re.compile(r"""href=['"]([^'"]+)['"]""", re.I)
    for p in pages or []:
        html = p.get("html") or ""
        if href_re.search(html):
            hreflang_pages += 1
        m = lang_re.search(html)
        if m:
            langs.add(m.group(1).lower())
        elif html:
            missing_lang += 1
    n = len(pages or [])
    multilingual = (hreflang_pages > 0) or (len(langs) >= 2)
    if multilingual and hreflang_pages and hreflang_pages < max(2, int(0.5 * n)):
        notes.append("Multilingual site appears to have incomplete hreflang coverage in the sample (advisory only).")
        findings.append({
            "id": "SEO-HREFLANG",
            "scored": False,
            "severity": "低",
            "title": "hreflang 覆盖不完整（建议项）",
            "problem": f"抽样中仅 {hreflang_pages}/{n} 页见到 hreflang。这是建议项，不计入核心重权。",
            "impact": "多语言站点的 hreflang 不完整可能影响语言版本选择，但不把它当作 Google 语言识别失败。",
            "solution": "按实际语言版本补双向 hreflang；不要把 html lang 属性问题夸大为索引失败。",
        })
    if missing_lang and n and missing_lang > n * 0.5:
        notes.append("Many sampled pages lack an html lang attribute (advisory; not treated as a Google language-identification failure).")
        findings.append({
            "id": "SEO-HTML-LANG",
            "scored": False,
            "severity": "低",
            "title": "部分页面缺少 html lang（建议项）",
            "problem": f"{missing_lang}/{n} 个抽样页未见 html lang 属性。",
            "impact": "这是辅助标记问题，不能写成“Google 无法识别页面语言”或语言识别失败。",
            "solution": "可在 html 根元素声明正确语言代码；优先级低于抓取、正文与错误的语言配置。",
        })
    status_by_url = {}
    for p in pages or []:
        status_by_url[(p.get("url") or "").rstrip("/")] = p.get("status")
    broken = []
    for p in pages or []:
        html = p.get("html") or ""
        for href in a_re.findall(html)[:80]:
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            for u, st in status_by_url.items():
                if st in (404, 410) and u and u in href.rstrip("/"):
                    broken.append({"from": p.get("url"), "to": u, "status": st})
                    break
    if broken:
        notes.append(
            f"{len(broken)} sampled-page internal link(s) point at a sampled 404/410 URL "
            "(advisory; not a core heavy weight)."
        )
        findings.append({
            "id": "SEO-BROKEN-INTERNAL",
            "scored": False,
            "severity": "低",
            "title": "抽样页上存在失效内链（建议项）",
            "problem": f"在已抓取页面之间发现 {len(broken)} 条指向 404/410 的内链。未对全站做额外死链爬取。",
            "impact": "失效内链是建议项，不按核心重权扣分。",
            "solution": "修复或移除这些已观察到的失效链接。",
            "evidence": [{"url": b["from"], "quote": f"→ {b['to']} HTTP {b['status']}"} for b in broken[:4]],
        })
    return {"notes": notes, "findings": findings}



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

    raw_25, notes, hy_findings = score_seo(pages or [], crawl_ok, robots_ok, sitemap_ok)
    merged_findings = list(findings or []) + list(hy_findings or [])
    dim_score = min(15.0, max(0.0, float(raw_25) * 15 / 25))
    dim_score = snap_half(dim_score)
    confidence = "high" if crawl_ok and pages else ("provisional" if pages else "none")
    pct = (100.0 * dim_score / 15.0) if pages else 0
    return {
        "score": dim_score,
        "max": 15,
        "dim_score": dim_score,
        "score_raw_25": raw_25,
        "max_raw_25": 25,
        "grade": grade_for_pct(pct) if pages else "F",
        "confidence": confidence,
        "crawl_ok": crawl_ok,
        "robots_verified": robots_ok,
        "sitemap_verified": sitemap_ok,
        "pages_analyzed": len(pages or []),
        "notes": notes,
        "narr": narr,
        "callout": callout,
        "findings": merged_findings,
        "rubric": "seo_scoring.md v1.2",
        "scoring_version": "v1.3",
        "part_of_technical_100": True,
        "crawl_probe_present": bool(crawl_probe),
    }


def attach_to_report(report: dict, run_dir: str) -> dict:
    """Mutate/return report with seo_discoverability attached (caller folds dim into overall_score)."""
    report["seo_discoverability"] = build_seo_block(run_dir)
    return report


if __name__ == "__main__":
    import sys

    rd = sys.argv[1] if len(sys.argv) > 1 else "."
    block = build_seo_block(rd)
    print(json.dumps(block, ensure_ascii=False, indent=2))
