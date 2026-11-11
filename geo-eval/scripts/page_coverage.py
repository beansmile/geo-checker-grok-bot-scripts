#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unsampled ≠ missing.

If a key page type (e.g. product detail) was discovered in the sitemap or
internal links but was not in the crawl sample, mark it 未评估 / not
evaluated. Do not auto-score 0 and do not emit confident findings such as
"missing spec table" for pages never fetched.

If key types were not evaluated, label the content total as a sampled-pages
score (and optionally defer a complete content total).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Order matters: first match wins (mirrors content_extract.PAGE_TYPE_RULES,
# plus event / legal, and product-detail vs product-list).
TYPE_RULES = [
    ("home", re.compile(r"^(index\.html?)?$", re.I)),
    ("about", re.compile(r"about|company|概况|关于我们|关于", re.I)),
    ("contact", re.compile(r"contact|联系", re.I)),
    ("privacy", re.compile(r"privacy|隐私", re.I)),
    ("legal", re.compile(r"terms|cookie|legal|条款", re.I)),
    ("faq", re.compile(r"faq|问答|常见问题", re.I)),
    ("event", re.compile(
        r"summit|峰会|经销商大会|经销商年会|dealer[- ]?(meet|summit|conference)|"
        r"open[- ]day|展会|博览|开业典礼",
        re.I,
    )),
    ("product_detail", re.compile(
        r"/product[s]?/[^/]+|/cp/[^/]+|/products?/\d|/item/|/p/\d|"
        r"/产品/[^/]+",
        re.I,
    )),
    ("product", re.compile(r"product|产品|chanpin|/cp/|hot-products", re.I)),
    ("case", re.compile(r"case|project|工程案例|cases|客户案例", re.I)),
    # News before solution so 行业新闻 / 媒体视角 are not swallowed by a bare 「行业」.
    ("news", re.compile(r"news|资讯|动态|媒体|新闻|公告|arcnews|media", re.I)),
    ("solution", re.compile(r"solution|解决方案|(?<!行)方案", re.I)),
    ("rd", re.compile(r"patent|研发|技术|rd|research|spec", re.I)),
    ("download", re.compile(r"download|资料", re.I)),
    ("market", re.compile(r"market|region|cities|locations|coverage|服务区域|/city/|区域业务", re.I)),
]

KEY_TYPES = (
    "product", "product_detail", "case", "about", "contact", "faq",
    "privacy", "news", "solution", "rd",
)

# Findings that must not be emitted as confident "missing X" when the type
# was never fetched.
TYPE_BOUND_FINDING_HINTS = {
    "product": ("spec table", "规格表", "产品参数", "product spec", "missing spec"),
    "product_detail": ("spec table", "规格表", "产品参数", "product spec", "missing spec"),
    "case": ("case study", "案例叙事", "项目案例缺失"),
    "faq": ("缺少 FAQ", "missing faq"),
    "privacy": ("隐私政策", "privacy policy"),
}


def is_escaped_external_url(url: str) -> bool:
    """True for sitemap accidents like /https/irm-cninfo-com-cn/... or /http/www-szse-cn/..."""
    path = urlparse(url or "").path or ""
    return bool(re.search(r"^/(https?)[-/]", path, re.I))


def is_non_html_asset(url: str) -> bool:
    path = urlparse(url or "").path or ""
    return bool(re.search(
        r"\.(pdf|zip|rar|7z|docx?|xlsx?|pptx?|mp4|mp3|avi|wmv|png|jpe?g|gif|webp|svg)(\?|$)",
        path, re.I,
    ))


def is_sampleable_url(url: str) -> bool:
    return bool(url) and not is_escaped_external_url(url) and not is_non_html_asset(url)


def classify_url(url: str, title: str = "") -> str:
    path = urlparse(url or "").path or ""
    blob = f"{url or ''} {path} {title or ''}"
    for name, pat in TYPE_RULES:
        if name == "home":
            if path in ("", "/"):
                return "home"
            continue
        if pat.search(blob):
            return name
    return "other"


def collect_discovered_urls(site=None, sitemap_urls=None, pages=None) -> list:
    urls = []
    seen = set()

    def add(u):
        u = (u or "").strip()
        if not u or u in seen:
            return
        seen.add(u)
        urls.append(u)

    for u in sitemap_urls or []:
        add(u)
    site = site or {}
    sm = site.get("sitemap") or {}
    for u in sm.get("urls") or sm.get("all_urls") or []:
        add(u)
    for p in site.get("pages_sampled") or []:
        add(p.get("url") if isinstance(p, dict) else None)
    for p in pages or []:
        add(p.get("url"))
        for link in p.get("links_internal") or []:
            add(link)
    return urls


def coverage_report(pages, site=None, sitemap_urls=None) -> dict:
    discovered = collect_discovered_urls(site, sitemap_urls, pages)
    discovered_types = {}
    for u in discovered:
        t = classify_url(u)
        discovered_types.setdefault(t, []).append(u)

    sampled = {}
    for p in pages or []:
        t = p.get("page_type") or classify_url(p.get("url") or "", p.get("title") or "")
        # Normalize product_detail into its own bucket; product list stays product.
        sampled.setdefault(t, []).append(p.get("url"))
        if t == "product_detail":
            sampled.setdefault("product", []).append(p.get("url"))

    unevaluated = []
    observed_absent = []  # discovered set has no URLs of this type
    for key in KEY_TYPES:
        sampled_hit = bool(sampled.get(key) or (key == "product" and sampled.get("product_detail")))
        discovered_hit = bool(
            discovered_types.get(key)
            or (key == "product" and discovered_types.get("product_detail"))
        )
        if sampled_hit:
            continue
        if discovered_hit:
            unevaluated.append(key)
        else:
            observed_absent.append(key)

    complete_deferred = bool(unevaluated)
    return {
        "discovered_count": len(discovered),
        "sampled_count": len(pages or []),
        "discovered_types": {k: len(v) for k, v in discovered_types.items()},
        "sampled_types": {k: len(v) for k, v in sampled.items()},
        "unevaluated_types": unevaluated,
        "observed_absent_types": observed_absent,
        "score_scope": "sampled_pages",
        "complete_total_deferred": complete_deferred,
        "note_zh": (
            "本分为抽样页得分。"
            + ("未抽到但站点已发现的关键页类型标为「未评估」，不按缺失计 0。" if unevaluated else "")
            + ("未在 sitemap/抽样发现的类型记为观察范围内未见，不是对未抓页面的断言。" if observed_absent else "")
        ),
        "note_en": (
            "This is a sampled-pages score. "
            + ("Key page types discovered but not fetched are marked not evaluated, not scored 0. " if unevaluated else "")
            + ("Types not seen in the sitemap or sample are 'not observed in scope', not claims about unfetched pages." if observed_absent else "")
        ),
    }


def type_is_unevaluated(coverage: dict, page_type: str) -> bool:
    return page_type in (coverage or {}).get("unevaluated_types", [])


def label_zh(page_type: str, coverage: dict) -> str:
    if type_is_unevaluated(coverage, page_type):
        return "未评估"
    if page_type in (coverage or {}).get("observed_absent_types", []):
        return "抽样与发现范围内未见"
    return "已抽样"


def should_suppress_missing_finding(coverage: dict, text: str) -> bool:
    """True if a finding looks like a confident 'missing X' for an unsampled type."""
    blob = (text or "").lower()
    for ptype in (coverage or {}).get("unevaluated_types") or []:
        for hint in TYPE_BOUND_FINDING_HINTS.get(ptype, ()):
            if hint.lower() in blob:
                return True
    return False


def load_sitemap_urls(run_dir: str) -> list:
    """Collect <loc> URLs from evidence sitemap XML files."""
    import os
    urls, seen = [], set()
    ev = os.path.join(run_dir, "evidence")
    if not os.path.isdir(ev):
        return urls
    for root, _dirs, files in os.walk(ev):
        for fname in files:
            if not fname.endswith(".xml"):
                continue
            try:
                body = open(os.path.join(root, fname), encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, re.I):
                loc = loc.strip()
                if loc and loc not in seen and not re.search(r"\.xml(\.gz)?$", loc, re.I):
                    seen.add(loc)
                    urls.append(loc)
    return urls
