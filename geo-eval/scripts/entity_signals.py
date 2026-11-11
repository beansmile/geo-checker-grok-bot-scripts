#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Body-first entity / KG signals, schema-body consistency, numeric conflicts,
and cross-page duplicate-content similarity.

Entity/KG use on-page body, profiles, contact facts and consistency — not
merely JSON-LD presence. Missing schema must not mean "the business cannot
be identified." Schema scores correctness/consistency with visible text;
the same sameAs / organization signal is not double-counted in schema and KG.

Numeric conflicts (ENT-09 group by entity; ENT-10 / ENT-11 split) verify
year, scope and version first. A news figure with a clear time range is
not auto-flagged as a current-fact error.

CLN-08 tiers: score only similarity >= 0.9; 0.75–0.9 advisory; 0.5–0.75
no longer scored.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

SOCIAL_HOSTS = re.compile(
    r"(?:^|\.)(?:facebook\.com|fb\.com|instagram\.com|twitter\.com|x\.com|"
    r"linkedin\.com|youtube\.com|youtu\.be|weibo\.com|weixin\.qq\.com|"
    r"tiktok\.com|pinterest\.com|wikipedia\.org|crunchbase\.com|"
    r"github\.com|xiaohongshu\.com|zhihu\.com)\b",
    re.I,
)

ADDRESS_RE = re.compile(
    r"(地址[:：]\s*\S+|邮政编码|邮编[:：]|大道|路\d+号|街道|"
    r"\b(?:address|postal\s*code|zip\s*code)\b[:：]?\s*\S+|"
    r"\b(?:road|street|avenue|blvd)\b)",
    re.I,
)
PHONE_RE = re.compile(
    r"(?:电话|热线|tel|phone|fax)[:：]?\s*\+?\d[\d\s\-()]{6,}\d"
    r"|href=[\"']tel:",
    re.I,
)
FOUNDING_RE = re.compile(
    r"(?:成立于|始创于|创办于|创建于|创立于|founded\s+in|established\s+in|"
    r"since)\s*(?:公元)?\s*(19|20)\d{2}",
    re.I,
)
YEAR_ONLY_RE = re.compile(r"\b((?:19|20)\d{2})\b")

TOPIC_HINT_RE = re.compile(
    r"(主营|业务范围|产品中心|解决方案|knowsAbout|我们的业务|core\s+business|"
    r"product\s+lines?|solutions?)",
    re.I,
)

# Metrics we are willing to compare. Keep conservative.
METRIC_PATTERNS = [
    # (metric_key, regex with named groups value, unit, optional year)
    ("area_mu", re.compile(
        r"(?:占地|规划|建筑|厂区|园区)?面积[^。；;\n]{0,20}?"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>亩|公顷|平方公里|km²|m²|平米|平方米)",
        re.I,
    )),
    ("staff", re.compile(
        r"(?:员工|职工|从业人员|雇员|staff|employees)\D{0,12}"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>万?人|people|employees|staff)?",
        re.I,
    )),
    ("founding_year", re.compile(
        r"(?:成立于|始创于|创办于|创建于|创立于|founded\s+in|established\s+in|since)"
        r"\s*(?:公元)?\s*(?P<value>((?:19|20)\d{2}))(?P<unit>年)?",
        re.I,
    )),
    ("revenue", re.compile(
        r"(?:营收|营业收入|销售额|revenue|sales)\D{0,16}"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>亿元|万元|百万|亿|万|USD|美元|亿元人民币)",
        re.I,
    )),
]

SCOPE_RE = re.compile(
    r"(?P<scope>截至|截止|当年|同年|同年年底|年底|全年|上半年|下半年|"
    r"第[一二三四]季度|Q[1-4]|as\s+of|in\s+(?:19|20)\d{2}|"
    r"(?:19|20)\d{2}\s*年(?:[度底末])?|(?:19|20)\d{2}\s*[-–]\s*(?:19|20)\d{2})",
    re.I,
)
VERSION_RE = re.compile(r"(第[一二三四五六七八九十\d]+代|版本\s*[:：]?\s*\w+|v(?:ersion)?\s*\d+)", re.I)
NEWS_PATH_RE = re.compile(r"/news|/media|/press|/资讯|/动态|/新闻|/announcement", re.I)

ENTITY_NEAR_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9&.'\-]{1,30}"
    r"(?:公司|集团|有限公司|Co\.,?\s*Ltd\.?|Group|Inc\.?|Corporation)?)",
)


def extract_social_profiles(pages, extra_urls=None) -> list:
    """Union of visible footer/about social links and caller-supplied URLs (e.g. schema sameAs)."""
    found = []
    seen = set()

    def add(url):
        text = str(url or "").strip()
        if not re.match(r"^https?://", text, re.I):
            return
        host = (urlparse(text).hostname or "").lower()
        if not host or not SOCIAL_HOSTS.search(host):
            return
        key = text.rstrip("/").lower()
        if key in seen:
            return
        seen.add(key)
        found.append(text)

    for u in extra_urls or []:
        add(u)
    for p in pages or []:
        html = p.get("html") or ""
        for href in re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.I):
            add(href)
        for link in p.get("links_external") or []:
            add(link)
    return found


def visible_contact_facts(pages) -> dict:
    """Address / phone / founding year observed in visible body text."""
    address, phone, founding = False, False, None
    founding_snippets = []
    address_snippets = []
    phone_snippets = []
    aboutish = []
    for p in pages or []:
        content = p.get("content") or ""
        url = (p.get("url") or "").lower()
        role = p.get("role") or ""
        ptype = p.get("page_type") or ""
        if role in ("trust", "home") or ptype in ("about", "contact", "home") or re.search(
            r"about|contact|company|关于|联系", url
        ):
            aboutish.append(content)
        if ADDRESS_RE.search(content):
            address = True
            address_snippets.append({"url": p.get("url"), "quote": _snip(ADDRESS_RE, content)})
        if PHONE_RE.search(content) or PHONE_RE.search(p.get("html") or ""):
            phone = True
            phone_snippets.append({"url": p.get("url"), "quote": "tel/phone"})
        m = FOUNDING_RE.search(content)
        if m and founding is None:
            year = re.search(r"((?:19|20)\d{2})", m.group(0))
            founding = year.group(1) if year else m.group(0)
            founding_snippets.append({"url": p.get("url"), "quote": m.group(0)})
    topics = bool(any(TOPIC_HINT_RE.search(c) for c in aboutish or [p.get("content") or "" for p in (pages or [])[:3]]))
    return {
        "address": address,
        "phone": phone,
        "founding_year": founding,
        "topics": topics,
        "address_snippets": address_snippets[:3],
        "phone_snippets": phone_snippets[:3],
        "founding_snippets": founding_snippets[:3],
        "identifiable": bool(address or phone or founding or topics),
    }


def _snip(pat, text, radius=20):
    m = pat.search(text or "")
    if not m:
        return ""
    a = max(0, m.start() - radius)
    b = min(len(text), m.end() + radius)
    return re.sub(r"\s+", " ", text[a:b]).strip()


def _schema_name(org) -> str:
    if not org:
        return ""
    return str(org.get("name") or org.get("legalName") or "").strip()


def _schema_founding(org) -> str:
    if not org:
        return ""
    raw = str(org.get("foundingDate") or "").strip()
    m = re.search(r"((?:19|20)\d{2})", raw)
    return m.group(1) if m else raw


def schema_body_consistency(org, pages, brand_names=None) -> dict:
    """Compare Organization schema with visible text. Conflicts lower schema quality."""
    conflicts = []
    agreements = []
    facts = visible_contact_facts(pages)
    name = _schema_name(org)
    if name and brand_names:
        norms = {re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(b).lower()) for b in brand_names if b}
        nkey = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", name.lower())
        if nkey and norms and nkey not in norms and not any(nkey in k or k in nkey for k in norms if k):
            conflicts.append({
                "field": "name",
                "schema": name,
                "body": list(brand_names)[:3],
                "note": "Organization.name 与页面可见品牌写法不一致",
            })
        elif nkey:
            agreements.append("name")
    elif name:
        agreements.append("name")

    sy = _schema_founding(org)
    by = facts.get("founding_year")
    if sy and by and sy != by:
        conflicts.append({
            "field": "foundingDate",
            "schema": sy,
            "body": by,
            "note": "schema foundingDate 与正文成立年份不一致",
        })
    elif sy and by and sy == by:
        agreements.append("foundingDate")

    return {
        "conflicts": conflicts,
        "agreements": agreements,
        "has_conflict": bool(conflicts),
        "body_facts": facts,
    }


def kg_score_from_signals(pages, org=None, same_as_cleaned=None, max_score=10) -> dict:
    """Score on-site entity signals from body ∪ schema, counting each signal once.

    sameAs / social profiles: min(4, unique profiles)
    topics / knowsAbout: 3 if body topics or schema knowsAbout
    founding: 1 if body or schema
    address/location: 2 if body address or schema address/location/areaServed
    """
    org = org or {}
    schema_same = list(same_as_cleaned or org.get("sameAs") or [])
    profiles = extract_social_profiles(pages, extra_urls=schema_same)
    facts = visible_contact_facts(pages)

    profile_pts = min(4, len(profiles))
    topics = bool(org.get("knowsAbout") or facts.get("topics"))
    topic_pts = 3 if topics else 0
    founding = bool(org.get("foundingDate") or facts.get("founding_year"))
    founding_pts = 1 if founding else 0
    address = bool(
        org.get("address") or org.get("location") or org.get("areaServed") or facts.get("address")
    )
    address_pts = 2 if address else 0
    score = min(max_score, profile_pts + topic_pts + founding_pts + address_pts)
    return {
        "score": score,
        "profiles": profiles,
        "profile_points": profile_pts,
        "topics": topics,
        "founding": founding,
        "address": address,
        "body_identifiable": facts.get("identifiable"),
        "body_facts": facts,
        "source": "body_and_schema_union",
    }


# ── CLN-08 similarity ─────────────────────────────────────────────
def _tokens(text: str):
    text = text or ""
    words = re.findall(r"[a-z0-9]+", text.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    return words + cjk


def _shingles(tokens, k=8):
    if len(tokens) < k:
        return set()
    return {tuple(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def pairwise_similarity(pages, k=8) -> dict:
    """Best Jaccard similarity of de-boilerplated shingles among content pages."""
    content = [p for p in (pages or []) if (p.get("role") in (None, "content", "home", "trust"))]
    if len(content) < 2:
        return {"best": 0.0, "pair": [], "verdict": "pass", "scored": False}

    shingles = []
    for p in content:
        toks = _tokens(p.get("content") or "")
        shingles.append(_shingles(toks, k=k))

    # boilerplate: shingles appearing on >70% of pages
    from collections import Counter
    cnt = Counter()
    for s in shingles:
        for g in s:
            cnt[g] += 1
    # With only two pages, shared body is the signal, not boilerplate.
    # Require at least 3 pages before stripping frequent shingles.
    n_pages = max(len(shingles), 1)
    thresh = 0.7 * n_pages
    if n_pages < 3:
        common = set()
    else:
        common = {g for g, c in cnt.items() if c > thresh}
    cleaned = [{g for g in s if g not in common} for s in shingles]

    best_i, best_j, best = 0, 1, 0.0
    for i, a in enumerate(cleaned):
        for j in range(i + 1, len(cleaned)):
            b = cleaned[j]
            if not a and not b:
                continue
            jacc = len(a & b) / max(1, len(a | b))
            if jacc > best:
                best_i, best_j, best = i, j, jacc

    verdict, scored = cln08_tier(best)
    return {
        "best": round(best, 3),
        "pair": [content[best_i].get("url"), content[best_j].get("url")],
        "verdict": verdict,  # fail | advisory | pass
        "scored": scored,
    }


def cln08_tier(score: float) -> tuple[str, bool]:
    """Return (verdict, scored). score only >= 0.9; 0.75-0.9 advisory; else pass."""
    if score >= 0.9:
        return "fail", True
    if score >= 0.75:
        return "advisory", False
    return "pass", False


# ── ENT-09 / ENT-10 / ENT-11 numeric conflicts ────────────────────
def _window(text, start, end, radius=80):
    a = max(0, start - radius)
    b = min(len(text), end + radius)
    return text[a:b]


def _guess_entity(window: str, default="site"):
    # Prefer a nearby company/group name; otherwise the site default.
    # Strip trailing "成立于1994年" so the same company is not split by year.
    cands = ENTITY_NEAR_RE.findall(window or "")
    scored = []
    for c in cands:
        c = re.sub(
            r"(成立于|创办于|创建于|创立于|始创于|founded\s+in|established\s+in).*$",
            "",
            c.strip(),
            flags=re.I,
        ).strip(" ，,。")
        if len(c) < 2 or re.match(r"^\d", c):
            continue
        weight = 2 if re.search(r"(公司|集团|有限公司|Ltd\.?|Group|Inc\.?|Corporation)$", c, re.I) else 1
        scored.append((weight, len(c), c))
    if scored:
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[0][2]
    return default


def extract_numeric_claims(pages, default_entity="site") -> list:
    claims = []
    for p in pages or []:
        text = p.get("content") or ""
        url = p.get("url") or ""
        is_news = bool(NEWS_PATH_RE.search(url) or (p.get("page_type") == "news"))
        for metric, pat in METRIC_PATTERNS:
            for m in pat.finditer(text):
                window = _window(text, m.start(), m.end())
                scope_m = SCOPE_RE.search(window)
                year_m = re.search(r"((?:19|20)\d{2})", window)
                ver_m = VERSION_RE.search(window)
                try:
                    value = float(m.group("value"))
                except (ValueError, IndexError):
                    continue
                unit = ""
                try:
                    unit = (m.group("unit") or "").strip()
                except IndexError:
                    unit = ""
                claims.append({
                    "entity": _guess_entity(window, default_entity),
                    "metric": metric,
                    "value": value,
                    "unit": unit.lower(),
                    "year": year_m.group(1) if year_m else None,
                    "scope": scope_m.group("scope") if scope_m else None,
                    "version": ver_m.group(0) if ver_m else None,
                    "url": url,
                    "is_news": is_news,
                    "quote": re.sub(r"\s+", " ", m.group(0))[:160],
                    "window": re.sub(r"\s+", " ", window)[:240],
                })
    return claims


def _same_scope(a, b) -> bool:
    """True if two claims can fairly be compared as the same fact."""
    # For founding_year the year *is* the value, not a reporting period.
    if a.get("metric") == "founding_year" and b.get("metric") == "founding_year":
        return a.get("unit") == b.get("unit") or not (a.get("unit") and b.get("unit") and a.get("unit") != b.get("unit"))
    # Different years → not the same current fact.
    if a.get("year") and b.get("year") and a["year"] != b["year"]:
        return False
    if a.get("scope") and b.get("scope"):
        if a["scope"].lower() != b["scope"].lower() and a.get("year") != b.get("year"):
            return False
    if a.get("version") and b.get("version") and a["version"] != b["version"]:
        return False
    # News with a time range / year must not be auto-compared to an undated
    # current fact (or another year).
    if a.get("is_news") and (a.get("year") or a.get("scope")):
        return False
    if b.get("is_news") and (b.get("year") or b.get("scope")):
        return False
    if a.get("unit") and b.get("unit") and a["unit"] != b["unit"]:
        return False
    return True


def _values_conflict(a, b, rel=0.15) -> bool:
    if a["value"] == b["value"]:
        return False
    # founding years: any difference is a conflict (if same scope)
    if a["metric"] == "founding_year":
        return True
    denom = max(abs(a["value"]), abs(b["value"]), 1.0)
    return abs(a["value"] - b["value"]) / denom >= rel


def analyze_numeric_conflicts(pages, org=None, default_entity="site") -> dict:
    """ENT-09 grouping; ENT-10 same-entity body conflicts; ENT-11 schema vs body.

    Verification-first: do not emit a scored factual error unless year/scope/
    version were checked and the claims are comparable.
    """
    claims = extract_numeric_claims(pages, default_entity=default_entity)
    by_entity = {}
    for c in claims:
        by_entity.setdefault(c["entity"], []).append(c)

    ent10 = []  # same entity, comparable facts, conflicting values
    needs_review = []  # discrepancies that need year/scope verification
    for entity, items in by_entity.items():
        by_metric = {}
        for c in items:
            by_metric.setdefault(c["metric"], []).append(c)
        for metric, rows in by_metric.items():
            for i, a in enumerate(rows):
                for b in rows[i + 1:]:
                    if not _values_conflict(a, b):
                        continue
                    comparable = _same_scope(a, b)
                    rec = {
                        "rule": "ENT-10",
                        "entity": entity,
                        "metric": metric,
                        "values": [a["value"], b["value"]],
                        "units": [a.get("unit"), b.get("unit")],
                        "years": [a.get("year"), b.get("year")],
                        "scopes": [a.get("scope"), b.get("scope")],
                        "urls": [a.get("url"), b.get("url")],
                        "quotes": [a.get("quote"), b.get("quote")],
                    }
                    if comparable and not (a.get("is_news") or b.get("is_news")):
                        # Founding year *is* the value; period markers in the
                        # window should not downgrade a clear conflict.
                        if a.get("metric") == "founding_year":
                            rec["verification"] = "comparable_current_facts"
                            ent10.append(rec)
                        elif a.get("year") or b.get("year") or a.get("scope") or b.get("scope"):
                            # One has scope, the other doesn't — verify first.
                            rec["verification"] = "year_or_scope_differs_or_incomplete"
                            needs_review.append(rec)
                        else:
                            rec["verification"] = "comparable_current_facts"
                            ent10.append(rec)
                    else:
                        rec["rule"] = "ENT-10"
                        rec["verification"] = "not_comparable_or_news_timeboxed"
                        needs_review.append(rec)

    ent11 = []  # schema vs body (foundingDate is the reliable one)
    if org:
        sy = _schema_founding(org)
        body_years = [c for c in claims if c["metric"] == "founding_year"]
        # Prefer evergreen (non-news) body years
        evergreen = [c for c in body_years if not c.get("is_news")]
        for c in evergreen:
            if sy and str(int(c["value"])) != str(sy):
                rec = {
                    "rule": "ENT-11",
                    "entity": c.get("entity") or default_entity,
                    "metric": "founding_year",
                    "schema": sy,
                    "body": c["value"],
                    "url": c.get("url"),
                    "quote": c.get("quote"),
                    "verification": "schema_vs_body",
                }
                # If the body mention is clearly historical/scoped, review only
                if c.get("scope") and "截至" in (c.get("scope") or ""):
                    rec["verification"] = "body_has_scope_review"
                    needs_review.append(rec)
                else:
                    ent11.append(rec)

    return {
        "claims": claims,
        "by_entity": {k: len(v) for k, v in by_entity.items()},
        "ent09_entities": list(by_entity.keys()),
        "ent10_conflicts": ent10,          # scored only when verification passed
        "ent11_conflicts": ent11,
        "needs_review": needs_review,      # advisory, not auto factual errors
    }
