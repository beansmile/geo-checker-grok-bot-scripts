#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GEO Checker scoring v1.3 shared heuristics (stdlib only).

GEO = Generative Engine Optimization (AI understand / trust / cite readiness).
Never geography, local-pack, NAP-as-GEO, or LocalBusiness-as-core framing.

New signals (weights unchanged from v1.2; richer sub-heuristics + findings):
1. Image-locked / non-extractable main content
2. Entry & URL hygiene (soft splash, canonical, home variants)
3. Unverified marketing claims (C-AUTH)
4. Organization contact/address completeness as entity/trust/KG verifiability
5. Intent page-type coverage incl. optional market/region/project pages
6. Multi-UA smoke helpers (Access evidence only)
7. Advisory CWV / heavy-asset / old-stack notes (not scored)
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urlunparse


# ── Remediation templates (industry-agnostic) ──────────────────────────

PRODUCT_FIELD_CHECKLIST = [
    "What the product/service is (1–2 sentence definition)",
    "Who it is for / primary use cases",
    "Key specifications or capabilities as text (not only in images)",
    "Standards, certifications, or constraints when applicable",
    "How to inquire or next step (contact / form / download)",
]

CASE_FIELD_CHECKLIST = [
    "Project or engagement name and context",
    "Client / industry / location as publishable facts (text)",
    "Scope of work and deliverables",
    "Measurable outcomes or constraints solved",
    "Link to related product/solution pages",
]

ARTICLE_FIELD_CHECKLIST = [
    "Direct answer in the opening paragraph",
    "Named entities and dates in prose",
    "Evidence links to primary sources when claims cite numbers",
    "Clear heading hierarchy for extractable sections",
    "Author or editorial attribution when expertise matters",
]


# ── Image-locked / non-extractable ─────────────────────────────────────

EMPTY_DESC_RE = re.compile(
    r"<(?:dd|td|p|div|span)[^>]*>\s*(?:&nbsp;|\s)*</(?:dd|td|p|div|span)>",
    re.I,
)
BG_IMAGE_RE = re.compile(
    r"background(?:-image)?\s*:\s*url\(|data-bg=|data-background|style=[\"'][^\"']*url\([^)]+\.(?:jpg|jpeg|png|webp|gif)",
    re.I,
)
SOFT_REDIRECT_RE = re.compile(
    r"""(?ix)
    <meta[^>]+http-equiv=["']?refresh["']?[^>]+content=["']?\s*\d+\s*;\s*url=
    |location\s*(?:\.href|\[['"]href['"]\])\s*=
    |window\.location\s*=
    |setTimeout\s*\(\s*(?:function\s*\(|\(\)\s*=>)[^)]{0,120}location
    """
)

CLAIM_NUM_RE = re.compile(
    r"(?ix)"
    r"(?:"
    r"(?:(?<!\d)(?!(?:19|20)\d{2}\b)\d{1,3}\+?\s*(?:年|years?|patents?|projects?|cities?|countries|clients?|customers?|"
    r"employees?|awards?|patents|专利|项目|城市|客户|员工|奖))"
    r"|(?:300\+|100\+|50\+|30\+|10\+|首家|第一|最大|领先|唯一|No\.?\s*1|number\s*one|"
    r"world[- ]class|industry[- ]leading|best[- ]in[- ]class)"
    r")"
)

ADDRESS_TEXT_RE = re.compile(
    r"(?ix)"
    r"(?:"
    r"(?:地址|总部|注册地址|办公地址|Address|Headquarters|HQ)\s*[:：]?\s*[^\n<]{6,80}"
    r"|(?:Street|Rd\.|Road|Ave\.|Avenue|Blvd|Suite|Unit)\s+\d+"
    r"|\d{1,4}\s+[\w\u4e00-\u9fff]+(?:路|街|道|巷|号)"
    r"|(?:Province|State|City|邮编|Postal|ZIP)\b"
    r")"
)

PHONE_TEXT_RE = re.compile(
    r"(?ix)(?:电话|Tel|Phone|手机|Hotline)\s*[:：]?\s*[\d\-\+\(\)\s]{7,}|tel:\+?[\d\-]+"
)

MULTI_MARKET_RE = re.compile(
    r"(?ix)(?:全国|多城|多地|海外|全球|international|worldwide|multi[- ](?:city|market|region)|"
    r"across\s+(?:\d+|multiple)\s+(?:cities|countries|markets)|落地城市|业务覆盖)"
)

MARKET_PAGE_RE = re.compile(
    r"(?ix)/(?:markets?|regions?|cities|locations|coverage|服务区域|城市|区域)/|"
    r"(?:market|region|city)[-_](?:page|hub)"
)

OLD_STACK_RE = re.compile(
    r"(?ix)(?:X-Powered-By:\s*ASP\.NET|IIS/\d|jquery[-.]1\.[0-7]|document\.all\b|"
    r"<!--\[if\s+IE|ActiveXObject)"
)

HEAVY_ASSET_RE = re.compile(
    r"(?ix)<(?:img|video|source)[^>]*(?:src|data-src)=[\"'][^\"']+\.(?:mp4|webm|mov)|"
    r"<img[^>]*(?:width|height)=[\"']?(?:1[5-9]\d{2}|[2-9]\d{3})"
)


def _words(text: str) -> int:
    return len(re.findall(r"[\w\u4e00-\u9fff]+", text or ""))


def detect_image_locked(page: dict) -> dict[str, Any]:
    """Flag pages whose citeable facts appear unavailable as extractable text.

    Works on HTML samples (img / bg / empty fields) and text snapshots
    (extremely thin product/case/article bodies).
    """
    html = page.get("html") or ""
    text = page.get("text_excerpt") or page.get("content") or ""
    wc = int(page.get("word_count") or _words(text))
    images = int(page.get("images_total") or 0)
    page_type = (page.get("page_type") or page.get("role") or "content").lower()
    intentish = page_type in (
        "product", "case", "solution", "news", "article", "home", "content", "rd"
    )

    reasons = []
    severity = 0.0

    if intentish and images >= 3 and wc < 120:
        reasons.append(f"high image count ({images}) with low extractable text ({wc} tokens)")
        severity = max(severity, 0.8)
    if intentish and images >= 1 and wc < 40:
        reasons.append(f"near-empty body text ({wc} tokens) beside media")
        severity = max(severity, 0.9)
    if html and BG_IMAGE_RE.search(html) and wc < 100:
        reasons.append("background/hero imagery likely carries primary messages")
        severity = max(severity, 0.7)
    if html and len(EMPTY_DESC_RE.findall(html)) >= 3 and wc < 150:
        reasons.append("multiple empty description/list fields in HTML")
        severity = max(severity, 0.6)
    # Thin intent pages with little/no media text — covers alternate-fetch snapshots
    # (sometimes wrapped as HTML), CSR shells, and image-primary templates.
    if intentish and page_type in ("product", "case", "news", "article", "solution", "home"):
        if wc < 80 and images <= 1:
            reasons.append(
                f"intent page type '{page_type}' has very little extractable prose ({wc} tokens); "
                "facts may live only in images, background art, or client-side rendering"
            )
            severity = max(severity, 0.85 if wc < 40 else 0.65)

    locked = severity >= 0.6
    return {
        "locked": locked,
        "severity": round(severity, 2),
        "reasons": reasons,
        "word_count": wc,
        "images_total": images,
        "page_type": page_type,
        "remediation_template": (
            PRODUCT_FIELD_CHECKLIST if page_type == "product"
            else CASE_FIELD_CHECKLIST if page_type == "case"
            else ARTICLE_FIELD_CHECKLIST
        ),
    }


def summarize_image_locked(pages: list[dict]) -> dict[str, Any]:
    details = []
    for p in pages:
        hit = detect_image_locked(p)
        if hit["locked"]:
            details.append({
                "url": p.get("url") or p.get("path") or "",
                **hit,
            })
    n = len(pages) or 1
    rate = round(100.0 * len(details) / n, 1)
    return {
        "locked_pages": len(details),
        "pages_checked": len(pages),
        "locked_rate_pct": rate,
        "details": details[:12],
        "finding_title_en": "Main content appears image-locked or non-extractable",
        "finding_title_zh": "主内容疑似图片化/不可抽取",
        "generic_remediation_en": (
            "Put every fact you want AI systems to cite into visible HTML text: "
            "definitions, specs, scenarios, outcomes, and evidence links. "
            "Treat images as illustration, not as the only carrier of facts. "
            "Use the product / case / article field checklists in the GEO Checker scoring guide."
        ),
    }


# ── Entry & URL hygiene ────────────────────────────────────────────────

def detect_soft_redirect(html: str) -> dict[str, Any]:
    """True for splash/meta-refresh home redirects, not search-box location.href."""
    if not html:
        return {"detected": False}
    meta = re.search(
        r"<meta[^>]+http-equiv=[\"\']?refresh[\"\']?[^>]+content=[\"\']?\s*\d+\s*;\s*url=",
        html, re.I,
    )
    delayed = re.search(
        r"setTimeout\s*\(\s*(?:function\s*\(|\(\)\s*=>)[^)]{0,120}location",
        html, re.I,
    )
    if meta:
        return {"detected": True, "snippet": meta.group(0)[:160]}
    if delayed:
        return {"detected": True, "snippet": delayed.group(0)[:160]}
    skip_ctx = re.compile(
        r"search|keyword|input_|footSearch|getElementById|onsubmit|addEventListener|onclick",
        re.I,
    )
    for m in re.finditer(
        r"location\s*(?:\.href|\[[\'\"]href[\'\"]\])\s*=|window\.location\s*=",
        html, re.I,
    ):
        ctx = html[max(0, m.start() - 180): m.end() + 180]
        if skip_ctx.search(ctx):
            continue
        return {"detected": True, "snippet": m.group(0)[:160]}
    return {"detected": False, "snippet": ""}


def normalize_home_key(url: str) -> tuple[str, str]:
    """Return (host_without_www, path_normalized) for home-variant clustering."""
    try:
        p = urlparse(url)
    except Exception:  # noqa: BLE001
        return ("", url)
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path or "/"
    if path in ("", "/index.html", "/index.htm", "/default.html", "/default.htm", "/home", "/home/"):
        path = "/"
    return host, path


def detect_home_variants(urls: list[str]) -> dict[str, Any]:
    homes = []
    for u in urls:
        if not u:
            continue
        host, path = normalize_home_key(u)
        if path == "/" or re.search(r"/index\.html?$", u, re.I):
            homes.append(u)
    unique = sorted(set(homes))
    hosts = {normalize_home_key(u)[0] for u in unique}
    paths = {urlparse(u).path or "/" for u in unique}
    multi = len(unique) >= 2 and (len(hosts) > 1 or len(paths) > 1)
    return {
        "variants": unique[:8],
        "multi_host_or_path": multi,
        "note": (
            "Multiple home URLs observed in sample (www vs apex and/or / vs /index.html) "
            "without verified 301 consolidation."
            if multi else ""
        ),
    }


def canonical_mismatch(page: dict, site_host: str = "") -> bool:
    canon = (page.get("canonical") or "").strip()
    url = (page.get("url") or "").strip()
    if not canon or not url:
        return False
    try:
        cu, uu = urlparse(canon), urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    c_host = (cu.netloc or "").lower().lstrip("www.")
    u_host = (uu.netloc or "").lower().lstrip("www.")
    if site_host:
        site_host = site_host.lower().lstrip("www.")
    if c_host and u_host and c_host != u_host:
        return True
    c_path = cu.path or "/"
    u_path = uu.path or "/"
    if c_path.rstrip("/") != u_path.rstrip("/") and not (
        {c_path, u_path} <= {"/", "/index.html", "/index.htm"}
    ):
        # soft mismatch when one is index.html and other is /
        if normalize_home_key(canon) == normalize_home_key(url):
            return False
        return True
    return False


def url_hygiene_findings(
    pages: list[dict],
    sample_urls: list[str] | None = None,
) -> list[dict]:
    findings = []
    home = next((p for p in pages if (p.get("role") == "home" or p.get("page_type") == "home")), None)
    if home:
        soft = detect_soft_redirect(home.get("html") or "")
        if soft["detected"]:
            findings.append({
                "id": "SEO-URL-01",
                "severity": "中",
                "title": "Homepage uses soft/JS splash redirect",
                "title_zh": "首页存在软跳转/脚本跳转",
                "problem": (
                    "Root or home HTML appears to redirect via meta refresh or JavaScript "
                    "instead of a server 301 to the canonical home URL."
                ),
                "impact": (
                    "Crawlers and AI fetchers may index the splash URL, miss the real home body, "
                    "or treat two homes as duplicates — weakening discoverability and citability."
                ),
                "solution": (
                    "Use a single canonical home URL; 301 all variants; avoid timed JS splash "
                    "redirects for the primary entry."
                ),
                "evidence": [{"url": home.get("url") or "", "quote": soft.get("snippet") or "soft redirect"}],
                "scored_in": "seo",
            })

    contentish = [p for p in pages if (p.get("role") in (None, "content", "home", "trust") or p.get("page_type"))]
    if contentish:
        missing = [p for p in contentish if not (p.get("canonical") or "").strip()]
        mismatched = [p for p in contentish if canonical_mismatch(p)]
        if len(missing) > len(contentish) * 0.5:
            findings.append({
                "id": "SEO-URL-02",
                "severity": "中",
                "title": "Canonical tags missing on most sampled pages",
                "title_zh": "多数抽样页缺少 canonical",
                "problem": f"{len(missing)}/{len(contentish)} sampled pages lack rel=canonical.",
                "impact": "Engines may treat parameter/duplicate URLs as separate documents.",
                "solution": "Add self-referencing canonical on every indexable URL; 301 true duplicates.",
                "evidence": [{"url": p.get("url") or "", "quote": "missing canonical"} for p in missing[:3]],
                "scored_in": "seo",
            })
        if mismatched:
            findings.append({
                "id": "SEO-URL-03",
                "severity": "中",
                "title": "Canonical URL mismatches page URL",
                "title_zh": "canonical 与页面 URL 不一致",
                "problem": f"{len(mismatched)} page(s) declare a canonical that does not match the fetched URL.",
                "impact": "Authority and citations may consolidate to the wrong URL or drop.",
                "solution": "Align canonical, internal links, and sitemap to one authoritative URL per document.",
                "evidence": [{"url": p.get("url") or "", "quote": p.get("canonical") or ""} for p in mismatched[:3]],
                "scored_in": "seo",
            })

    variants = detect_home_variants([p.get("url") or "" for p in pages] + list(sample_urls or []))
    if variants["multi_host_or_path"]:
        findings.append({
            "id": "SEO-URL-04",
            "severity": "中",
            "title": "Multiple home host/path variants without 301 evidence",
            "title_zh": "多个首页主机/路径变体且未见 301",
            "problem": variants["note"] + " Observed: " + ", ".join(variants["variants"][:4]),
            "impact": "Home equity and entity home signals split across URLs.",
            "solution": "Pick one home (https + preferred host + /); 301 www/apex and /index.html variants.",
            "evidence": [{"url": u, "quote": "home variant"} for u in variants["variants"][:4]],
            "scored_in": "seo",
            "note": "Do not double-count into ACC HTTPS penalty; this is discoverability hygiene.",
        })
    return findings


# ── Unverified marketing claims ───────────────────────────────────────

def detect_unverified_claims(text: str, outbound_links: list[str] | None = None) -> list[dict]:
    """Large round numbers / superlatives without nearby evidence link or proof URL."""
    if not text:
        return []
    links = outbound_links or []
    has_proof_link = any(
        re.search(r"(patent|cert|award|iso|case|report|证|专利|奖|资质)", L, re.I)
        for L in links
    )
    hits = []
    ordinal = re.compile(
        r"第[一二三四五六七八九十百千万0-9]+(?:季度|季报|次|届|轮|批|期|条|款|项|名|周)|"
        r"first\s+(?:quarter|meeting|half|session|round|interim)|"
        r"\bQ[1-4]\b",
        re.I,
    )
    for m in CLAIM_NUM_RE.finditer(text):
        span = text[max(0, m.start() - 80): m.end() + 120]
        # 第一季度 / 第一次股东会 / first quarter are administrative ordinals, not boasts.
        local = text[max(0, m.start() - 8): m.end() + 12]
        if ordinal.search(local) or ordinal.search(span):
            continue
        nearby_link = bool(re.search(r"https?://|href=", span, re.I)) or has_proof_link
        if not nearby_link:
            hits.append({
                "claim": m.group(0).strip(),
                "context": re.sub(r"\s+", " ", span).strip()[:180],
            })
    # de-dupe by claim string
    seen = set()
    out = []
    for h in hits:
        key = h["claim"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out[:8]


# ── Entity address / contact completeness (trust/KG framing) ───────────

def entity_verifiability(text: str, org: dict | None = None) -> dict[str, Any]:
    """Postal/street/region text OR schema address — for AI citation entity checks.

    Framed as Organization verifiability, not local map-pack SEO.
    """
    org = org or {}
    schema_addr = bool(org.get("address") or org.get("location") or org.get("areaServed"))
    text_addr = bool(ADDRESS_TEXT_RE.search(text or ""))
    text_phone = bool(PHONE_TEXT_RE.search(text or ""))
    contact_point = bool(org.get("contactPoint") or org.get("email") or org.get("telephone"))
    return {
        "schema_address_or_area": schema_addr,
        "visible_address_text": text_addr,
        "visible_phone_text": text_phone,
        "schema_contact_point": contact_point,
        "complete_enough": bool((schema_addr or text_addr) and (contact_point or text_phone)),
        "framing": "entity_trust_kg",  # never local-pack
    }


# ── Intent page-type coverage ──────────────────────────────────────────

RECOMMENDED_INTENT_TYPES = (
    "product",
    "solution",  # solutions / use-cases
    "case",      # cases / proof
    "rd",        # specs / docs
    "about",     # company proof
    "news",      # knowledge / updates (proxy for knowledge hub when faq absent)
    "faq",
    "market",    # optional market/region/project pages
)


def intent_coverage(types: dict, pages: list[dict] | None = None, corpus_text: str = "") -> dict[str, Any]:
    pages = pages or []
    # Detect market-like URLs even if classified as other
    market_hits = sum(
        1 for p in pages
        if MARKET_PAGE_RE.search(p.get("url") or "") or (p.get("page_type") == "market")
    )
    counts = dict(types or {})
    if market_hits and not counts.get("market"):
        counts["market"] = market_hits

    multi_market_claim = bool(MULTI_MARKET_RE.search(corpus_text or ""))
    present = [t for t in RECOMMENDED_INTENT_TYPES if counts.get(t)]
    missing = [t for t in RECOMMENDED_INTENT_TYPES if not counts.get(t)]
    # market is optional unless the site claims multi-market coverage
    if not multi_market_claim and "market" in missing:
        missing = [t for t in missing if t != "market"]
    return {
        "recommended": list(RECOMMENDED_INTENT_TYPES),
        "present": present,
        "missing": missing,
        "multi_market_claim": multi_market_claim,
        "market_pages_in_sample": market_hits,
        "note": (
            "Recommend independent URLs for products, solutions/use-cases, cases/proof, "
            "specs/docs, company proof, and knowledge. Optional market/region/project pages "
            "improve answerability when the site claims multi-market coverage — this is "
            "answerability for generative engines, not city-keyword SEO."
        ),
    }


# ── Advisory (not scored) ──────────────────────────────────────────────

def advisory_performance_notes(html_or_headers: str) -> list[dict]:
    notes = []
    blob = html_or_headers or ""
    if OLD_STACK_RE.search(blob):
        notes.append({
            "scored": False,
            "severity": "低",
            "title": "Legacy stack fingerprints observed (advisory)",
            "problem": "Response or HTML shows older server/JS fingerprints.",
            "impact": "Not part of the GEO /100 score; may correlate with weaker maintainability.",
            "solution": "Modernize when practical; keep Core Web Vitals and asset weight as engineering backlog.",
        })
    if HEAVY_ASSET_RE.search(blob):
        notes.append({
            "scored": False,
            "severity": "低",
            "title": "Heavy media assets observed (advisory)",
            "problem": "Large images or video tags appear in the sample.",
            "impact": "CWV/lab performance is advisory only in GEO Checker — not a scored dimension.",
            "solution": "Compress, lazy-load, and keep citeable facts in text alongside media.",
        })
    return notes


def multi_ua_smoke_record(ua_results: list[dict]) -> dict[str, Any]:
    """Normalize crawler_access ua_results into Access evidence (no invented differentiation scores)."""
    slim = []
    for r in ua_results or []:
        slim.append({
            "ua": r.get("ua"),
            "status": r.get("status"),
            "latency_ms": r.get("latency_ms"),
            "challenge": r.get("challenge"),
            "error": r.get("error") or "",
            "size": r.get("size"),
        })
    return {
        "kind": "multi_ua_smoke",
        "scored": False,
        "results": slim,
        "note": (
            "Browser + searchbot + AI-search bot UA smoke is Access evidence only. "
            "Do not invent differentiation scores from a single sample."
        ),
    }


__all__ = [
    "PRODUCT_FIELD_CHECKLIST",
    "CASE_FIELD_CHECKLIST",
    "ARTICLE_FIELD_CHECKLIST",
    "detect_image_locked",
    "summarize_image_locked",
    "detect_soft_redirect",
    "detect_home_variants",
    "url_hygiene_findings",
    "detect_unverified_claims",
    "entity_verifiability",
    "intent_coverage",
    "advisory_performance_notes",
    "multi_ua_smoke_record",
    "MULTI_MARKET_RE",
    "MARKET_PAGE_RE",
]
