#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3~4：通用 GEO 深度检测 + 9 维评分 → report.json

用法:
    python3 analyze.py <run_dir>

输入:  run_dir（run.py 产物：evidence/pages/*.html、pages.list、site.json、scope.json、robots.txt、llms.txt）
输出:  <run_dir>/report.json（9 维得分、总分、等级、findings、penalty/bonus）
       seo 为技术百分制维度（启发式 /25 → 维度 /15；见 seo_scoring.md）；加减分仍在 score_adjustments

口径:  10 维 100 分制 v1.3（权重同 v1.2：schema 12 · entity 12 · ogp 5 · richness 12 · kg 10 · absorption 12 · trust 12 · on_page 5 · quality 5 · seo 15；v1.3 加强可抽取性/URL 卫生/主张证据等子启发式）
       SEO content discoverability contributes to overall_score as the seo dimension
       Trust Ceiling：S1 实体冲突 → trust≤6/12、entity≤3.6/12、总分≤70；S1 lorem → 总分≤75
       纯规则 R（不含 LLM）；LLM 类判定（ENT-07、QLT 等）留待 merge_llm.py 扩展。
"""

import html as html_lib
import json
import os
import re
import sys
from urllib.parse import urlparse

import citability
import crawler_roles
import entity_signals
import llms_detect
import page_coverage

# ── 指纹/正则 ──────────────────────────────────────────────
LOREM_PATTERNS = [
    re.compile(r"lorem\s+ipsum", re.I),
    re.compile(r"ut\s+elit\s+tellus", re.I),
    re.compile(r"primis\s+non\s+dignissim", re.I),
    re.compile(r"massa\s+volutpat\s+ridiculus", re.I),
    re.compile(r"nisi\s+arcu\s+auctor\s+himenaeos", re.I),
    re.compile(r"ipsum\s+pede\s+habitant", re.I),
    re.compile(r"ut\s+fames\s+nibh\s+euismod", re.I),
    re.compile(r"dedicated\s+for\s+best\s+quality\s+innovations", re.I),
    re.compile(r"under\s+construction", re.I),
    re.compile(r"example\.com", re.I),
]
ZERO_COUNTER_PATTERN = re.compile(
    r"\b(0|￥\s*0|\$\s*0|zero)\s*\+?\s*(years?|staff|projects?|showrooms?|countries?|patents?|employees?|revenue|billion|million)",
    re.I,
)
DEFAULT_LEGAL_PATTERNS = [
    re.compile(r"when\s+visitors\s+leave\s+comments", re.I),
    re.compile(r"gravatar\s+service", re.I),
    re.compile(r"an\s+anonymized\s+string\s+created\s+from\s+your\s+email", re.I),
]
PLACEHOLDER_CTA = re.compile(r"\b(discover\s+more|read\s+more|click\s+here|learn\s+more)\b", re.I)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# 备案 / 登记类链接（ICP 备案号、工信部等）常被站点写进 Organization.sameAs，
# 但它们是登记记录、不是实体主页：既不该计入 sameAs 条数，也不该进生成的修复片段。
# 与 geo_ready 的 SiteFacts::FILING_HOST_PATTERN 保持同一口径。
FILING_HOST_PATTERN = re.compile(r"(?:\A|\.)(?:gov\.cn|miit\.gov\.cn|beian\.gov\.cn)\Z", re.I)

NAME_PLACEHOLDER_RE = re.compile(r"homepage|site\s*name|untitled|lorem", re.I)
TEL_PLACEHOLDER_RE = re.compile(r"xxx|000-?000|1234567|your-phone|example\.com", re.I)
DEFAULT_AUTHOR_NAMES = [
    "ehaitech", "admin", "administrator", "theme", "template", "author", "root",
    "wordpress", "webmaster", "editor", "siteadmin", "demo", "test", "user",
]
# 公司法定名（ENT-04）：必须是「大写开头的名称 + 空格 + 独立的法律后缀词」。
#
# 原正则 `[A-Z][A-Za-z&.'-]*(?:\s+(?:Co\.,?\s*)?Ltd\.?|Group|Corporation|Corp\.?|Inc\.?|Limited)` 用 re.I：
#   1) `[A-Z]` 在 re.I 下能匹配小写，任何小写词都能当公司名前缀；
#   2) 只有第一个分支带了 `\s+`，`Inc|Corp|Group|Limited` 前没有空格要求，
#      于是 "since"→"sinc"、"principals"→"princ"、"distinction"→"distinc" 被当成公司名（ENT-04 误报）。
# 现在：不加 re.I（公司名以大写开头），所有后缀分支都要求前置空白与词边界。
COMPANY_NAME_RE = re.compile(
    r"\b[A-Z][A-Za-z&.'-]*(?:[\s\u00a0]+[A-Z][A-Za-z&.'-]*){0,4}"
    r"[\s\u00a0]+(?:Co\.,?[\s\u00a0]*)?"
    r"(?:Ltd|Limited|Inc|Corp|Corporation|Company|Holdings|Group)\b\.?"
)
LEGAL_SUFFIXES = ["co", "ltd", "limited", "inc", "corp", "corporation", "group", "company", "holdings", "international", "home", "collection", "industry", "industries", "technology"]

# All known robots tokens (training + search + user fetchers).
# Core score only uses search-index and user-fetcher tokens — see crawler_roles.py.
# Google-Extended is a training token with no independent UA; listed for robots parsing only.
AI_CRAWLERS = sorted(
    crawler_roles.TRAINING_TOKENS
    | crawler_roles.SEARCH_INDEX_TOKENS
    | crawler_roles.USER_FETCHER_TOKENS
)

# 页面角色优先级（与 run.py 一致）
ROLE_RULES = [
    ("demo", re.compile(r"(pabriz-|elementor-|/page/|\?page_id=|/template|/demo)", re.I)),
    ("system", re.compile(r"(/cart|/checkout|/my-account|/account|/login|/signin|/register|/search|/tag/|/archive|/feed|/404|/thanks)", re.I)),
    ("legal", re.compile(r"(privacy|terms|tos|cookie|legal)", re.I)),
    ("trust", re.compile(r"(/about|/contact|/team|/our-story|/mission|/company|/partnership|/history)", re.I)),
]


def classify_role(url):
    path = urlparse(url).path
    # 首页角色：OGP 只评首页（OGP-01/02 scope=home），必须能把根路径识别出来
    if path in ("", "/"):
        return "home"
    # AI 发现类文件（agents.md / llms.txt / *.json）本身不是人类内容页，
    # 不应参与 title/meta/H1 等「页面元数据」计分
    if re.search(r"\.(md|txt|json|xml)$", path, re.I):
        return "meta"
    for name, pat in ROLE_RULES:
        if pat.search(path):
            return name
    return "content"


def strip_tags(html):
    # 去掉 script/style，再剥掉所有标签，得到正文纯文本
    without_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", without_scripts)


def interpolate_score(value, points):
    """分段线性插值：把阶梯阈值改成连续函数。

    阶梯阈值有断崖——可引用率 39.2% 与 40.1% 相差 0.9 个百分点却跳 2 分，
    评分不可复现。points 为 [[阈值, 得分], ...] 升序；区间内线性插值，两端取端点。
    """
    v = float(value or 0)
    if v <= points[0][0]:
        return float(points[0][1])
    if v >= points[-1][0]:
        return float(points[-1][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= v <= x1:
            return y0 + (y1 - y0) * (v - x0) / float(x1 - x0)
    return float(points[-1][1])


def flatten_jsonld(node, out):
    """展开 JSON-LD 中的 @graph 容器与数组，输出扁平节点列表。

    主流 SEO 插件（Yoast / RankMath / Shopify 主题）常把 Organization、WebSite、
    Product 等节点放在顶层 @graph 数组里；只看顶层 @type 会全部漏检。
    """
    if isinstance(node, list):
        for item in node:
            flatten_jsonld(item, out)
        return
    if not isinstance(node, dict):
        return
    graph = node.get("@graph")
    if isinstance(graph, (list, dict)):
        # 容器自身若带 @type（少见）也保留
        if node.get("@type"):
            out.append({k: v for k, v in node.items() if k != "@graph"})
        flatten_jsonld(graph, out)
        return
    out.append(node)


def load_pages(run_dir):

    """从 evidence/pages 解析页面信号。"""
    ev = os.path.join(run_dir, "evidence")
    pages_dir = os.path.join(ev, "pages")
    pages = []
    if not os.path.isdir(pages_dir):
        return pages

    # pages.list 提供 slug|url；否则扫描 html 文件
    url_map = {}
    list_file = os.path.join(pages_dir, "pages.list")
    if os.path.isfile(list_file):
        for line in open(list_file, encoding="utf-8"):
            line = line.strip()
            if "|" in line:
                slug, url = line.split("|", 1)
                url_map[slug] = url

    for fname in sorted(os.listdir(pages_dir)):
        # scoring v1.3: accept .md/.txt alternate-fetch snapshots as provisional pages
        # when direct HTML crawl failed (disclose via role/content; no invented HTML chrome).
        if not (fname.endswith(".html") or fname.endswith(".htm") or fname.endswith(".md") or fname.endswith(".txt")):
            continue
        if fname == "pages.list":
            continue
        slug = os.path.splitext(fname)[0]
        url = url_map.get(slug, slug)
        if url and not page_coverage.is_sampleable_url(url):
            continue
        raw = open(os.path.join(pages_dir, fname), encoding="utf-8", errors="ignore").read()
        if fname.endswith((".md", ".txt")) and "<html" not in raw[:500].lower():
            # Wrap snapshot text so downstream tag strippers still yield citeable body text.
            esc = html_lib.escape(raw)
            html = f"<html><head><title>{esc.splitlines()[0][:120] if esc.splitlines() else slug}</title></head><body><pre>{esc}</pre></body></html>"
        else:
            html = raw

        title = (re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I) or [None, ""])[1] if re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I) else ""
        title = html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title))).strip()

        meta = ""
        m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.S | re.I) or \
            re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', html, re.S | re.I)
        if m:
            meta = html_lib.unescape(re.sub(r"\s+", " ", m.group(1))).strip()

        h1s = [html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h))).strip() for h in re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)]

        schemas = []
        for blk in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I):
            try:
                data = json.loads(blk.strip())
            except (ValueError, TypeError):
                continue
            flatten_jsonld(data, schemas)

        ogp = {}
        for key in ("og:title", "og:description", "og:image", "og:url", "og:site_name", "og:locale"):
            m = re.search(r'property=["\']%s["\'][^>]+content=["\'](.*?)["\']' % re.escape(key), html, re.I)
            if m:
                ogp[key] = m.group(1)

        content = strip_tags(html)

        # 链接（内链/外链，去重）
        base_host = (urlparse(url).hostname or "").lower()
        links_internal = set()
        links_external = set()
        for a in re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.I):
            a = a.strip()
            if a.startswith(("http://", "https://")):
                host = urlparse(a).hostname or ""
                (links_internal if host.lower() == base_host else links_external).add(a)
            elif a.startswith("/") and not a.startswith("//"):
                links_internal.add(a)

        # 作者/日期（schema）
        author_names = set()
        dates = {}
        for s in schemas:
            if not isinstance(s, dict):
                continue
            t = str(s.get("@type", ""))
            if "Person" in t or (s.get("author")):
                n = s.get("name")
                if n:
                    author_names.add(str(n))
            a = s.get("author")
            if isinstance(a, dict) and a.get("name"):
                author_names.add(str(a["name"]))
            elif isinstance(a, str):
                author_names.add(a)
            for k in ("datePublished", "dateModified"):
                if s.get(k):
                    dates[k] = str(s[k])

        # canonical / twitter card
        canonical = ""
        m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
        if m:
            canonical = m.group(1)
        twitter_card = "twitter:card" in html.lower()

        # 标题层级（H1→H2→H3 是否跳级）
        h2s = [html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h))).strip()
               for h in re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.S | re.I)]
        h3s = [html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h))).strip()
               for h in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.S | re.I)]
        hierarchy_ok = not (h3s and not h2s)  # 有 H3 无 H2 = 跳级

        role = ("home" if slug in ("home", "index") or fname.startswith("home.") else classify_role(url))
        if role == "home" or slug in ("home", "index"):
            page_type = "home"
        else:
            page_type = page_coverage.classify_url(url, title)
            if page_type == "other":
                page_type = role or "content"
        wc = len(re.findall(r"[\w\u4e00-\u9fff]+", content or ""))
        pages.append({
            "url": url, "slug": slug, "role": role, "page_type": page_type,
            "title": title, "meta": meta, "h1": h1s, "h2": h2s, "h3": h3s,
            "hierarchy_ok": hierarchy_ok,
            "schemas": schemas, "ogp": ogp, "content": content, "html": html,
            "word_count": wc, "images_total": len(re.findall(r"<img\b", html, re.I)),
            "links_internal": links_internal, "links_external": links_external,
            "author_names": author_names, "dates": dates, "canonical": canonical,
            "twitter_card": twitter_card,
        })
    return pages


def load_site(run_dir):
    p = os.path.join(run_dir, "site.json")
    if os.path.isfile(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except (ValueError, TypeError):
            pass
    return {}


def registrable_domain(url):
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def normalize_brand(raw):
    first = re.findall(r"[a-z0-9\u4e00-\u9fff]+", raw.lower())
    return first[0] if first and first[0] not in LEGAL_SUFFIXES else ""


# ── 检测块 ────────────────────────────────────────────────
def detect_cln(pages):
    lorem, zero, legal, cta, soft404 = [], [], [], [], []
    for p in pages:
        c = p["content"]
        for pat in LOREM_PATTERNS:
            if pat.search(c):
                lorem.append({"url": p["url"], "pattern": pat.pattern})
                break
        m = ZERO_COUNTER_PATTERN.search(c)
        if m:
            zero.append({"url": p["url"], "snippet": m.group(0)})
        if p["role"] == "legal":
            for pat in DEFAULT_LEGAL_PATTERNS:
                if pat.search(c):
                    legal.append({"url": p["url"]})
                    break
        if PLACEHOLDER_CTA.search(c) and re.search(r'href=["\'](?:#|javascript:void\(0\))["\']', p["html"], re.I):
            cta.append({"url": p["url"]})
        if re.search(r"404|not\s+found|页面不存在", c, re.I) or (len(c) < 200 and not p["h1"]):
            soft404.append({"url": p["url"]})
    demo = [p["url"] for p in pages if p["role"] == "demo"]
    system = [p["url"] for p in pages if p["role"] == "system"]
    total = len(pages)
    non_content = sum(1 for p in pages if p["role"] in ("system", "demo", "legal"))
    bloat_ratio = round(non_content / total * 100, 1) if total else 0.0
    residue = min(sum([
        min(len(lorem) * 15, 45), min(len(zero) * 10, 20), min(len(legal) * 10, 10),
        min(len(cta) * 5, 10), min(len(demo) * 5, 15),
    ]), 100)
    similarity = entity_signals.pairwise_similarity(pages)
    return {"lorem": lorem, "zero": zero, "legal": legal, "cta": cta, "soft404": soft404,
            "demo": demo, "system": system, "bloat_ratio": bloat_ratio, "residue": residue,
            "similarity": similarity}


def page_locale(p):
    """页面 locale：og:locale 优先，退回 schema inLanguage。用于区分「多语言本地化」与「同一实体多写法」。"""
    loc = (p.get("ogp") or {}).get("og:locale")
    if loc:
        return str(loc).lower().replace("_", "-")
    for s in p["schemas"]:
        if isinstance(s, dict) and s.get("inLanguage"):
            return str(s["inLanguage"]).lower()
    return "default"


def declared_brand_aliases(pages):
    """站点用 alternateName 显式声明过的别名（同属一个实体）。"""
    terms = []
    for p in pages:
        for s in p["schemas"]:
            if isinstance(s, dict) and re.search(r"Organization|WebSite", str(s.get("@type", ""))):
                alt = s.get("alternateName")
                if isinstance(alt, list):
                    terms += [str(x) for x in alt]
                elif isinstance(alt, str):
                    terms.append(alt)
    return [t for t in terms if t.strip()]


BRAND_NOISE_PUNCT = re.compile(r"[，。！？；：、,;!?]")


def brand_noise(raw):
    """口号 / 句子 / 完整短语不是品牌名。"""
    t = str(raw).strip()
    if len(t) > 30:
        return True
    if BRAND_NOISE_PUNCT.search(t):
        return True
    return len(t.split()) > 4


def collect_brand_records(pages):
    """返回 [{raw, count, locales}]：每条品牌写法记录其出现次数与所在 locale。"""
    records = {}
    for p in pages:
        locale = page_locale(p)
        candidates = []
        for s in p["schemas"]:
            if isinstance(s, dict) and re.search(r"Organization|WebSite", str(s.get("@type", ""))):
                if s.get("name"):
                    candidates.append(s["name"])
        if p["ogp"].get("og:site_name"):
            candidates.append(p["ogp"]["og:site_name"])
        suffix = re.split(r"[-|—]", p["title"])[-1].strip() if p["title"] else ""
        if suffix and len(suffix) <= 30 and " " not in suffix:
            candidates.append(suffix)
        if "about" in p["url"].lower() and p["h1"]:
            brand = re.sub(r"^about\s*", "", p["h1"][0], flags=re.I).strip()
            if brand and len(brand) <= 40:
                candidates.append(brand)

        for raw in candidates:
            raw = str(raw).strip()
            key = normalize_brand(raw)
            if not key or len(key) < 3:
                continue
            rec = records.setdefault(key, {"raw": raw, "count": 0, "locales": []})
            rec["count"] += 1
            if locale not in rec["locales"]:
                rec["locales"].append(locale)
    return sorted(records.values(), key=lambda r: -r["count"])


def collect_brand_names(pages):
    """兼容旧接口：返回 raw 字符串计数字典（供展示用）。"""
    return {r["raw"]: r["count"] for r in collect_brand_records(pages)}


def brand_conflict_among(records, aliases):
    """ENT-01 判定（对齐 rules.md §2.4）：命中条件收严，避免把多语言站点判成实体混乱。

    1) alternateName 声明过的写法属同一实体，不计入冲突；
    2) 与声明名互相包含的标题/页脚噪声（「品牌名+隐私政策」）剔除；
    3) 口号、句子、完整短语不是品牌名；
    4) 每种写法需出现 ≥3 次；
    5) 冲突必须在同一 locale 内成立——同一实体在不同语言页使用不同名称属正常本地化。
    """
    alias_keys = {normalize_brand(a) for a in aliases} - {""}
    canonical = {normalize_brand(r["raw"]) for r in records} - {""}
    by_locale = {}
    for r in records:
        key = normalize_brand(r["raw"])
        if not key or len(key) < 3:
            continue
        if r["count"] < 3:
            continue
        if key in alias_keys:
            continue
        if brand_noise(r["raw"]):
            continue
        if any(c != key and (key in c or c in key) for c in canonical):
            continue
        for loc in (r["locales"] or ["default"]):
            by_locale.setdefault(loc, []).append(key)
    return any(len(set(keys)) >= 2 for keys in by_locale.values())


def collect_company_names(pages):
    """Collect legal-form company names that look like site-identity strings.

    Mentions of other companies in acquisition / subsidiary history must not
    be treated as conflicting legal names of the site owner.
    """
    skip_ctx = re.compile(
        r"acquired|acquisition|subsidiary|subsidiaries|wholly-?owned|"
        r"shares of|shareholding|控股|子公司|收购|并购|参股|成为.{0,8}附属",
        re.I,
    )

    def is_copyright_identity(text, start, end):
        left = text[max(0, start - 40):start]
        right = text[end:min(len(text), end + 40)]
        if re.search(r"(copyright|\u00a9|&copy;)\s*$", left, re.I):
            return True
        if re.search(r"^\s*\.?\s*All Rights Reserved", right, re.I):
            return True
        return False

    names = {}
    for p in pages:
        chunks = [p.get("title") or "", " ".join(p.get("h1") or []), p.get("content") or ""]
        for text in chunks:
            if not text:
                continue
            for m in COMPANY_NAME_RE.finditer(text):
                n = re.sub(r"\s+", " ", m.group(0)).strip()
                n = re.sub(r"^(Copyright|\u00a9|&copy;)\s+", "", n, flags=re.I).strip()
                if not n or len(n) > 60:
                    continue
                if re.search(r"all rights reserved", n, re.I):
                    continue
                if re.match(r"^(the|our|this|your|a|an|rights|reserved)\s+(company|group|corporation|inc|ltd|limited)\.?$", n, re.I):
                    continue
                window = text[max(0, m.start() - 180): m.end() + 180]
                if skip_ctx.search(window) and not is_copyright_identity(text, m.start(), m.end()):
                    continue
                # Body mentions of partners, nav labels or machine brands are not
                # official legal-name variants. Only title / H1 / copyright identity counts.
                is_identity_chunk = text in (p.get("title") or "", " ".join(p.get("h1") or []))
                if not is_identity_chunk and not is_copyright_identity(text, m.start(), m.end()):
                    continue
                names[n] = names.get(n, 0) + 1
    return list(names)


def default_author(name):
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    return any(n == d or n.startswith(d) for d in DEFAULT_AUTHOR_NAMES)


def detect_ent(pages, domain):
    brand_records = collect_brand_records(pages)
    brand_names = collect_brand_names(pages)
    # ENT-01：按 locale 分组 + 排除 alternateName 声明值与标题/口号噪声后再判冲突
    brand_conflict = brand_conflict_among(brand_records, declared_brand_aliases(pages))

    emails = {}
    for p in pages:
        for addr in EMAIL_RE.findall(p["content"]):
            emails[addr.lower()] = emails.get(addr.lower(), 0) + 1
    email_domains = {a.split("@")[-1] for a in emails}
    email_conflict = len(email_domains) >= 2
    # ENT-02（W）：单一邮箱域 ≠ 站点注册域 → 列出但不计分（不扣分、不触发 Trust Ceiling）。
    # email_conflict 为真（≥2 个域名）时留空，避免与 S1 条目重复上报。
    email_off_domain = [] if email_conflict else sorted(
        a for a in emails if not _email_domain_matches(a.split("@")[-1], domain)
    )

    company_names = collect_company_names(pages)
    generic_company = re.compile(
        r"^(the|our|this|your|a|an)\s+(company|group|corporation|inc|ltd|limited)\.?$",
        re.I,
    )
    company_names = [n for n in company_names if not generic_company.match(n or "")]

    def _company_core(n):
        s = normalize_brand(n)
        for suf in sorted(LEGAL_SUFFIXES, key=len, reverse=True):
            s = re.sub(re.escape(suf) + r"$", "", s)
        return s

    cores = [_company_core(n) for n in company_names if _company_core(n)]
    distinct = []
    for c in cores:
        if any(c != d and (c in d or d in c) for d in cores):
            continue
        if c not in distinct:
            distinct.append(c)
    # If every remaining core is related by containment, it is one entity, not a conflict.
    company_conflict = len({c for c in cores}) >= 2 and len(distinct) >= 2

    return {"brand_names": list(brand_names), "brand_conflict": brand_conflict,
            "emails": list(emails), "email_conflict": email_conflict,
            "email_off_domain": email_off_domain, "domain": domain,
            "company_names": company_names, "company_conflict": company_conflict,
            "trust_ceiling": brand_conflict or email_conflict}


def _email_domain_matches(email_domain, site_domain):
    """邮箱域与站点注册域一致（含子域）。站点域未知时视为不匹配，交由调用方决定是否提示。"""
    e = (email_domain or "").lower().strip()
    s = (site_domain or "").lower().strip()
    if not e or not s:
        return False
    return e == s or e.endswith("." + s)


def clean_same_as(values, site_domain):
    """过滤 sameAs：非 http 链接、站点自引用、ICP 备案/登记类链接都不算实体主页。

    未过滤时 `beian.miit.gov.cn` 会被当成一条「社交主页」直接给 kg 加分（≤4 分/条），
    同一条链接还会被写进修复片段与 LLM prompt 的「社交主页」字段。
    """
    out = []
    host_site = (site_domain or "").lower().strip()
    for value in values if isinstance(values, (list, tuple)) else ([values] if values else []):
        text = str(value or "").strip()
        if not re.match(r"^https?://", text, re.I):
            continue
        host = (urlparse(text).hostname or "").lower()
        if not host:
            continue
        if host_site and (host == host_site or host.endswith("." + host_site)):
            continue
        if FILING_HOST_PATTERN.search(host):
            continue
        if text not in out:
            out.append(text)
    return out


def detect_schema(pages):
    org = None
    website = None
    for p in pages:
        for s in p["schemas"]:
            if not isinstance(s, dict):
                continue
            t = str(s.get("@type", ""))
            if re.search(r"Organization", t) and org is None:
                org = s
            if re.search(r"WebSite", t) and website is None:
                website = s
    return {"org": org, "website": website}


def _parse_robots_groups(robots):
    """Split robots.txt into (agents, rule_lines) groups.

    Consecutive User-agent lines share the following directives. Agent names
    are matched exactly, so Applebot-Extended is not Applebot, and
    Google-Extended is not Googlebot.
    """
    groups = []
    agents, rules, in_rules = [], [], False
    for line in (robots or "").splitlines():
        raw = line.split("#", 1)[0].strip()
        if not raw:
            continue
        m = re.match(r"(?i)^user-agent:\s*(.*)$", raw)
        if m:
            if in_rules and agents:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            name = m.group(1).strip()
            if name:
                agents.append(name)
            continue
        if agents:
            rules.append(raw)
            in_rules = True
    if agents:
        groups.append((agents, rules))
    return groups


def _robots_section_blocks_all(robots, ua):
    """判断某 User-agent 段是否有「Disallow: /」（整站屏蔽，路径恰好是 /）。

    Agent tokens are matched exactly. Applebot-Extended must not satisfy a
    lookup for Applebot; Google-Extended must not satisfy Googlebot.
    """
    target = ua or ""
    if target in ("*", r"\*"):
        target = "*"
    found = False
    for agents, rules in _parse_robots_groups(robots):
        if any(a.lower() == target.lower() for a in agents):
            found = True
            if any(re.match(r"(?i)^disallow:\s*/\s*$", r) for r in rules):
                return True
    return False if found else None

def _load_crawler_payload(run_dir):
    """Read crawler_access.json from either evidence/ or evidence/pages/."""
    candidates = [
        os.path.join(run_dir, "evidence", "crawler_access.json"),
        os.path.join(run_dir, "evidence", "pages", "crawler_access.json"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return json.load(open(path, encoding="utf-8")), path
            except (ValueError, OSError):
                continue
    return {}, None


def load_sitemap_urls(run_dir):
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


def detect_acc(run_dir, base_url):
    robots_path = os.path.join(run_dir, "evidence", "robots.txt")
    blocked = []
    if os.path.isfile(robots_path):
        robots = open(robots_path, encoding="utf-8", errors="ignore").read()
        wildcard_all = _robots_section_blocks_all(robots, r"\*")
        for ua in AI_CRAWLERS:
            section_all = _robots_section_blocks_all(robots, ua)
            # 有专属段 → 只看专属段；无专属段 → 看通配段（命中 Disallow: / 才算屏蔽）
            if section_all is True or (section_all is None and wildcard_all is True):
                blocked.append(ua)
    robots_split = crawler_roles.classify_robots(blocked)
    llms = llms_detect.load_from_run(run_dir)
    has_llms = bool(llms.get("present"))
    crawler, crawler_path = _load_crawler_payload(run_dir)
    ua_results = list(crawler.get("ua_results") or [])
    decision = crawler_roles.core_penalty_decision(
        blocked, ua_results, waf_challenge=bool(crawler.get("waf_challenge")),
    )
    engines = decision.get("engines") or crawler_roles.engine_access_status(ua_results, blocked)
    # Core live blocks only (training bots excluded). Keep ai_blocked as core list
    # so older report code that reads it does not treat GPTBot as search failure.
    core_live = list(decision.get("core_live_blocked") or [])
    return {
        "blocked": blocked,
        "blocked_core": list(robots_split.get("core_blocked") or []),
        "blocked_training": list(robots_split.get("training_blocked") or []),
        "has_llms": has_llms,
        "llms": llms,
        "crawler": crawler,
        "crawler_path": crawler_path,
        "ai_blocked": core_live,
        "training_blocked_live": list(decision.get("training_live_blocked") or []),
        "waf_challenge": bool(crawler.get("waf_challenge") or decision.get("browser_waf")),
        "reachable": (not decision.get("apply")),
        "crawler_decision": decision,
        "engines": engines,
        "observation_mode": "raw_http_html",
    }


# ── 10 维评分（SEO 在 analyze() 中并入）──────────────────
def score_dimensions(pages, site, cln, ent, schema_info, acc):
    domain = site.get("registrable_domain") or registrable_domain(pages[0]["url"] if pages else "")
    content_pages = [p for p in pages if p["role"] == "content" or p["role"] == "home"]

    # schema (15 internal, then ×12/15). Correctness + consistency with visible
    # text. sameAs is NOT scored here (counted once in KG from body ∪ schema).
    # Missing schema must not zero the entity/KG dimensions.
    org = schema_info["org"] or {}
    consistency = entity_signals.schema_body_consistency(org, pages, ent.get("brand_names"))
    acc["schema_consistency"] = consistency
    schema_score = 0
    if org:
        schema_score += 5  # Organization 存在
        name = str(org.get("name", ""))
        name_conflict = any(c.get("field") == "name" for c in consistency.get("conflicts") or [])
        if name and not NAME_PLACEHOLDER_RE.search(name) and not name_conflict:
            schema_score += 2
        if org.get("contactPoint") or org.get("logo"):
            schema_score += 2
        founding_conflict = any(c.get("field") == "foundingDate" for c in consistency.get("conflicts") or [])
        if org.get("foundingDate") and not founding_conflict:
            schema_score += 1
        if org.get("url"):
            schema_score += 1
        if not consistency.get("has_conflict"):
            schema_score += 2  # consistent with visible text
        elif consistency.get("has_conflict"):
            # Present-but-conflicting is not a high completeness score.
            schema_score = max(0, schema_score - 3)
    schema_score += 2 if schema_info["website"] else 0
    schema_score = min(schema_score, 15)

    # entity (15)：15 - 实体扣分. Body-and-profile identity is enough;
    # missing schema does not force this to 0.
    entity_deduction = 0
    if ent["brand_conflict"]:
        entity_deduction += 10
    if ent["email_conflict"]:
        entity_deduction += 8
    entity_score = max(0, min(15, 15 - entity_deduction))

    # ogp (5)：keep the 5-point slot so the 10-dim table still sums to 100,
    # but lower the contribution of Twitter and treat OG as share hygiene.
    # twitter:card is 0.5 (was 2.0).
    home = next((p for p in pages if p["role"] == "home"), None)
    ogp_score = 0
    if home and home["ogp"]:
        ogp_score = sum([
            1.25 if home["ogp"].get("og:title") else 0,
            1.25 if home["ogp"].get("og:description") else 0,
            1.25 if home["ogp"].get("og:image") else 0,
            0.75 if home["ogp"].get("og:url") else 0,
            0.5 if "twitter:card" in (home["html"].lower()) else 0,
        ])
    ogp_score = round(min(ogp_score, 5), 2)

    # richness (15)：FAQ 5 + 文章 5 + 内容量 5。
    # llms.txt is experimental and is not scored here or in adjustments.
    # Unsampled FAQ (discovered but not fetched) is 未评估 — mid credit, not 0.
    coverage = acc.get("coverage") or page_coverage.coverage_report(pages, site)
    acc["coverage"] = coverage
    faq_pages = [p for p in pages if "faq" in (p["url"] or "").lower() or p.get("page_type") == "faq"]
    article_like = sum(1 for p in pages if any(re.search(r"Article|BlogPosting", str(s.get("@type", ""))) for s in p["schemas"] if isinstance(s, dict)))
    content_len = sum(len(p["content"]) for p in content_pages)
    richness = 0
    if faq_pages:
        richness += 5
    elif page_coverage.type_is_unevaluated(coverage, "faq"):
        richness += 2.5
        acc.setdefault("unevaluated_notes", []).append("FAQ 页已在发现范围但未抽样，标为未评估，不按缺失计 0")
    richness += 5 if article_like >= 2 else (2.5 if article_like >= 1 else 0)
    richness += 5 if content_len > 20000 else (2.5 if content_len > 8000 else 0)
    richness = min(richness, 15)

    # kg (10)：body ∪ schema, each signal counted once. Missing schema does
    # not zero the dimension when on-page profiles/contact facts exist.
    kg_info = entity_signals.kg_score_from_signals(pages, org, org.get("sameAs"))
    acc["kg_detail"] = kg_info
    kg_score = min(kg_info["score"], 10)

    # absorption (15)：口径 B —— Citability 五子项 20 分制 × 0.75。
    # 与 geo_ready 的 CitabilityAnalyzer 同一模型（可引用率 7 + 证据块 7 + 直接回答 3
    # + 结构化资产 2 + 对题度 1）。块级切分、词数窗口、自包含判定都在 citability.py。
    cit = citability.analyze(pages)
    acc["absorption_rate"] = cit["content_blocks"]["citability_rate"]
    acc["citability"] = cit
    absorption = citability.absorption_score(cit)

    # trust (15)：信任页 + 作者；页面存在之外还要有实质内容。
    # 只判 URL 命中会让空壳页、软 404、WordPress 默认合规模板拿满分。
    soft404_urls = {x["url"] for x in cln.get("soft404", [])}
    legal_template_urls = {x["url"] for x in cln.get("legal", [])}

    def substantial(p):
        return p["url"] not in soft404_urls and len(p["content"].strip()) > 200

    about_pages = [p for p in pages if re.search(r"(about|our-story|/story|mission|/company|history)", p["url"], re.I)]
    contact_pages = [p for p in pages if re.search(r"(contact|support|help|service|faq)", p["url"], re.I)]
    legal_pages = [p for p in pages if p["role"] == "legal"]
    has_about = bool(about_pages)
    has_contact = bool(contact_pages)
    has_legal = bool(legal_pages)
    # Privacy missing is not escalated to "AI will not trust this company";
    # empty/default legal templates still don't earn the legal points.
    author_present = any(re.search(r"Person|Author", str(s.get("@type", ""))) for p in pages for s in p["schemas"] if isinstance(s, dict))
    trust = 0
    trust += 4 if has_about and any(substantial(p) for p in about_pages) else 0
    trust += 3 if has_contact and any(substantial(p) for p in contact_pages) else 0
    trust += 3 if has_legal and legal_pages and not legal_template_urls else 0
    trust += 3 if author_present else 0
    trust += 2 if content_len > 10000 else 0
    trust = min(trust, 15)

    # on_page (5): mechanical thresholds (title exactly ≤60, exactly one H1)
    # are hints, not equal to a missing title or missing main text.
    title_present = sum(1 for p in content_pages if (p.get("title") or "").strip())
    meta_ok = sum(1 for p in content_pages if p["meta"])
    h1_any = sum(1 for p in content_pages if p.get("h1"))
    n = len(content_pages) or 1
    on_page = 0
    on_page += 2 if title_present >= n * 0.8 else (1 if title_present >= n * 0.5 else 0)
    on_page += 1 if meta_ok >= n * 0.8 else 0
    on_page += 1 if h1_any >= n * 0.5 else 0
    on_page += 1 if title_present >= n * 0.8 and meta_ok >= n * 0.5 else 0
    acc["on_page_hints"] = {
        "title_over_60": sum(1 for p in content_pages if len((p.get("title") or "")) > 60),
        "not_exactly_one_h1": sum(1 for p in content_pages if len(p.get("h1") or []) != 1),
        "missing_title": sum(1 for p in content_pages if not (p.get("title") or "").strip()),
        "missing_h1": sum(1 for p in content_pages if not p.get("h1")),
    }

    # quality (5)：5 - 清洁度扣分. CLN-08 only scores similarity >= 0.9.
    q_deduction = 0
    if cln["lorem"]:
        q_deduction += min(len(cln["lorem"]) * 2, 5)
    if cln["zero"]:
        q_deduction += min(len(cln["zero"]), 2)
    if cln["legal"]:
        q_deduction += min(len(cln["legal"]), 2)
    if cln["demo"]:
        q_deduction += 1
    sim = cln.get("similarity") or {}
    if sim.get("scored") and sim.get("verdict") == "fail":
        q_deduction += 2
    quality = max(0, min(5, 5 - q_deduction))

    # v1.2/v1.3: dimensions formerly max 15 scale to max 12 (ogp/kg/on_page/quality unchanged).
    # SEO is attached later in analyze() from seo_analyze. Weights unchanged in this iteration
    # except OG is still a 5-point slot (Twitter weight lowered inside the slot) and
    # llms.txt is no longer a +3 core bonus.
    scale_15_to_12 = 12 / 15
    return {
        "schema": round(min(schema_score, 15) * scale_15_to_12, 1),
        "entity": round(min(entity_score, 15) * scale_15_to_12, 1),
        "ogp": ogp_score,
        "richness": round(min(richness, 15) * scale_15_to_12, 1),
        "kg": kg_score,
        "absorption": round(min(absorption, 12), 1),  # already ×0.6 in citability
        "trust": round(min(trust, 15) * scale_15_to_12, 1),
        "on_page": on_page,
        "quality": quality,
    }



def grade_for(score):
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def _org_missing(org):
    missing = []
    if not org.get("sameAs"):
        missing.append("sameAs（社媒/权威档案链接）")
    if not org.get("foundingDate"):
        missing.append("foundingDate（成立时间）")
    if not (org.get("address") or org.get("location") or org.get("areaServed")):
        missing.append("address（所在地）")
    if not org.get("knowsAbout"):
        missing.append("knowsAbout（专业领域）")
    return missing


ORG_JSONLD_EXAMPLE = """<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "[品牌名]",
  "alternateName": "[别名]",
  "url": "[官网]",
  "logo": "[logo 图片 URL]",
  "foundingDate": "[成立年份，如 1994]",
  "sameAs": ["[官方社交主页 URL]"],
  "knowsAbout": ["[主营领域]"],
  "address": { "@type": "PostalAddress", "addressLocality": "[城市]", "addressCountry": "[国家]" },
  "contactPoint": { "@type": "ContactPoint", "email": "[主用邮箱]", "contactType": "customer service" }
}
</script>"""

OGP_EXAMPLE = """<meta property="og:title" content="[品牌名 | 页面主题]" />
<meta property="og:description" content="[一句话描述，含事实/数据]" />
<meta property="og:image" content="[1200x630 配图 URL]" />
<meta property="og:url" content="[页面 URL]" />"""

TWITTER_EXAMPLE = """<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="[品牌名 | 页面主题]" />
<meta name="twitter:description" content="[一句话描述]" />"""

COUNTER_EXAMPLE = """<!-- 静态兜底：真实数字直接写在初始 HTML，AI 读到的是真实值，不是 0 -->
<span class="stat" data-count="20">20+ Years</span>
<span class="stat" data-count="5000">5000+ Staff</span>"""

FAQ_EXAMPLE = """<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "[常见问题]",
    "acceptedAnswer": { "@type": "Answer", "text": "[一段可直接引用的答案]" }
  }]
}
</script>"""

H1_EXAMPLE = """<!-- 每页保留唯一 H1，与页面主题一致 -->
<h1>[本页主题，如：产品名 / 服务名]</h1>"""

ENTITY_MAPPING_EXAMPLE = """<!-- 实体映射：法定主体 → 集团 → 品牌 → 域名 → 邮箱 → 社交，声明各名称同属一家 -->
Organization:
  name: "[对外主品牌名]"
  legalName: "[法定主体全称]"
  alternateName: ["[别名1]", "[别名2]"]
  sameAs: ["[官方社交主页 URL]"]
  parentOrganization: { "@type": "Organization", "name": "[集团/母公司]" }"""

CONTACTPOINT_EXAMPLE = """<!-- contactPoint：统一主用邮箱，与官网域名一致 -->
"contactPoint": {
  "@type": "ContactPoint",
  "email": "[主用邮箱，如 sales@你的域名]",
  "contactType": "customer service"
}"""


def build_findings(cln, ent, schema_info, acc, pages):
    findings = []
    org = schema_info["org"] or {}
    content_pages = [p for p in pages if p["role"] in ("content", "home")]

    # ── ACC-02 / ACC-03：实测可达性（robots.txt 只管自愿遵守，不代表能取到）──
    _crawler = acc.get("crawler") or {}
    _ai_blocked = acc.get("ai_blocked") or []
    _ua_rows = _crawler.get("ua_results") or []
    _base = _crawler.get("url") or (pages[0]["url"] if pages else "")

    def _ua_evidence(names):
        out = []
        for r in _ua_rows:
            if r.get("ua") in names:
                out.append({
                    "url": _base,
                    "quote": f"UA {r['ua']} → HTTP {r.get('status')}"
                             + ("，命中验证/挑战页" if r.get("challenge") else "")
                             + (f"（响应体 {r.get('size')} 字节）" if r.get("size") is not None else ""),
                })
        return out[:4]

    engines = acc.get("engines") or {}
    decision = acc.get("crawler_decision") or {}
    core_live = list(decision.get("core_live_blocked") or _ai_blocked)
    training_live = list(decision.get("training_live_blocked") or acc.get("training_blocked_live") or [])
    engine_lines = crawler_roles.engine_status_lines_zh(engines)

    if core_live:
        findings.append({
            "severity": "严重" if len(core_live) >= 2 else "高",
            "id": "ACC-SEARCH-BLOCKED",
            "root_cause_id": "crawler_search_access",
            "evidence_kind": "observed",
            "title": "搜索或按需抓取爬虫实测被拦截",
            "problem": f"用搜索索引/按需抓取 UA 实测首页：{('、'.join(core_live))} 被拦截"
                       f"（返回验证页 / 403 / 429 或超时）。robots.txt 本身可能是放行的，拦截发生在 CDN/WAF 层。"
                       + (" " + "；".join(engine_lines) if engine_lines else ""),
            "impact": "搜索爬虫拿不到页面，AI 搜索就无法读取网站内容。"
                      "训练爬虫也建议开放，好让内容进入模型的学习材料。"
                      "挡住训练爬虫，不会让搜索引擎看不到网站。",
            "solution": "在 CDN/WAF 中放行 OAI-SearchBot、Claude-SearchBot、PerplexityBot、"
                        "ChatGPT-User、Googlebot 与 Bingbot 等搜索/按需抓取爬虫；放行后重跑本项复测。"
                        "训练爬虫（GPTBot、ClaudeBot 等）也建议一并放行，以便内容进入模型语料；"
                        "不要用它们的拦截来推断 ChatGPT/Claude 搜索被屏蔽。",
            "evidence": _ua_evidence(set(core_live)),
        })
    elif acc.get("waf_challenge") and not (decision.get("core_ok") or []):
        _b = next((r for r in _ua_rows if r.get("ua") == "browser"), {})
        findings.append({
            "severity": "高",
            "id": "ACC-WAF",
            "root_cause_id": "crawler_search_access",
            "evidence_kind": "observed",
            "title": "WAF/机器人挑战会拦截抓取（普通请求即返回验证页）",
            "problem": f"用普通浏览器 UA 请求首页即命中机器人验证（HTTP {_b.get('status')}，"
                       f"响应体仅 {_b.get('size')} 字节），且未见搜索索引爬虫成功取到页面。",
            "impact": "若搜索或按需抓取爬虫同样无法通过挑战，页面内容就无法被读取。"
                      "若个别搜索爬虫实测已通过，则以分角色结果为准，不把训练爬虫状态写成搜索失败。",
            "solution": "在 WAF 中为搜索/按需抓取爬虫（OAI-SearchBot、Claude-SearchBot、PerplexityBot、"
                        "ChatGPT-User、Googlebot、Bingbot）配置放行，或把挑战策略限定在登录/表单路径。",
            "evidence": [{"url": _base,
                          "quote": f"UA browser → HTTP {_b.get('status')}，命中验证页，响应体 {_b.get('size')} 字节"}],
        })
    if training_live:
        findings.append({
            "severity": "低",
            "scored": False,
            "id": "ACC-TRAINING-INFO",
            "root_cause_id": "crawler_training_info",
            "evidence_kind": "observed",
            "title": "训练爬虫被拦截：建议开放，好让内容进入模型的学习材料",
            "problem": f"训练爬虫 {('、'.join(training_live))} 实测被拦截。"
                       + (" " + "；".join(engine_lines) if engine_lines else ""),
            "impact": "训练爬虫用于采集模型的学习材料。建议一并开放。"
                      "挡住训练爬虫，不会让 ChatGPT 或 Claude 搜索看不到网站。本项不扣搜索访问分。",
            "solution": "建议在 robots.txt 和网站防护中放行 GPTBot、ClaudeBot 等训练爬虫，好让内容进入模型的学习材料。"
                        "搜索爬虫（如 OAI-SearchBot、Claude-SearchBot）请继续保持开放。",
            "evidence": _ua_evidence(set(training_live)),
        })


    def ev(items, quote):
        return [{"url": (i["url"] if isinstance(i, dict) else i), "quote": (i.get("quote") or quote if isinstance(i, dict) else quote)}
                for i in items[:3]] if items else []

    if cln["lorem"]:
        findings.append({"severity": "严重", "title": "模板占位文案残留（lorem/拉丁填充）",
                         "problem": f"{len(cln['lorem'])} 个页面残留 Lorem ipsum 等占位假字。",
                         "impact": "AI 判定内容未完成，不敢引用；客户观感掉分。",
                         "solution": "删除占位段落，替换为真实产品/公司介绍。",
                         "evidence": ev(cln["lorem"], "占位假字")})
    if cln["zero"]:
        findings.append({"severity": "高", "title": "0 值/占位计数器",
                         "problem": "计数器读到 0（Years/Staff/Projects），等于向 AI 暴露“0 年经验”。",
                         "impact": "最伤信任的一句话。",
                         "solution": "把真实数字直接写入初始 HTML，不要只靠 JS 动画。",
                         "code": COUNTER_EXAMPLE,
                         "evidence": ev(cln["zero"], "0 值计数器")})
    if cln["legal"]:
        findings.append({"severity": "高", "title": "合规页为默认模板",
                         "problem": "隐私/条款页仍是建站默认模板原文。",
                         "impact": "合规页是信任页，默认模板不专业。",
                         "solution": "法务确认后替换为符合目标市场法规的版本。",
                         "evidence": ev(cln["legal"], "默认合规模板")})
    if ent["brand_conflict"]:
        names = " / ".join(list(ent["brand_names"])[:3])
        findings.append({"severity": "严重", "title": "品牌写法不一致",
                         "problem": f"网站同时使用多种品牌写法：{names}。",
                         "impact": "AI 认不准你是谁，品牌认知被分流。",
                         "solution": "建立实体映射，用结构化数据声明各名称同属一个实体。",
                         "code": ENTITY_MAPPING_EXAMPLE,
                         "evidence": [{"url": "", "quote": n} for n in list(ent["brand_names"])[:3]]})
    if ent["email_conflict"]:
        domains = " / ".join(sorted({e.split('@')[-1] for e in ent["emails"]}))
        findings.append({"severity": "严重", "title": "同时公开多个邮箱域名",
                         "problem": f"公开邮箱使用多个域名：{domains}。",
                         "impact": "客户不知道该联系哪个。",
                         "solution": "统一为一个主用邮箱，并在 contactPoint 列明。",
                         "code": CONTACTPOINT_EXAMPLE,
                         "evidence": [{"url": "", "quote": e} for e in ent["emails"][:3]]})
    elif ent.get("email_off_domain"):
        # ENT-02（W 警告项）：单一邮箱域 ≠ 站点注册域，列出但不计分。
        # 免费邮箱（126/163/qq/gmail）与外部域名邮箱不区分——主体仍然唯一，
        # 不构成实体冲突，因此不扣 entity 维度分、不触发 Trust Ceiling。
        off = list(ent["email_off_domain"])
        addrs = " / ".join(off[:3])
        site_domain = ent.get("domain") or ""
        findings.append({"severity": "低", "scored": False, "title": "官方邮箱未使用站点域名（警告项，不计分）",
                         "problem": f"站点域名是 {site_domain}，但公开邮箱为 {addrs}，两者域名不一致。",
                         "impact": "不构成实体冲突，不影响本项得分；但免费/外部邮箱会削弱「这是不是官方渠道」的可信度观感，也影响直订意愿。",
                         "solution": f"申请品牌域名邮箱（如 reservations@{site_domain or 'your-domain'}），"
                                     "在 Organization/contactPoint、联系页、页脚与 llms.txt 中统一替换；原邮箱可保留作转发。",
                         "code": CONTACTPOINT_EXAMPLE,
                         "evidence": [{"url": "", "quote": e} for e in off[:3]]})
    name = str(org.get("name", ""))
    if name and NAME_PLACEHOLDER_RE.search(name):
        findings.append({"severity": "高", "title": "Schema 组织名称为占位值",
                         "problem": f"Organization name=\"{name}\" 是模板占位。",
                         "impact": "AI 无法把站点归到真实实体。",
                         "solution": "将 schema name 改为真实品牌名。",
                         "evidence": [{"url": "", "quote": f'Organization name="{name}"'}]})
    core_robots = list(acc.get("blocked_core") or [])
    training_robots = list(acc.get("blocked_training") or [])
    if core_robots:
        findings.append({
            "severity": "严重",
            "id": "ACC-ROBOTS-SEARCH",
            "root_cause_id": "crawler_search_access",
            "evidence_kind": "observed",
            "title": "搜索或按需抓取爬虫被 robots.txt 屏蔽",
            "problem": f"robots.txt 拦截了搜索/按需抓取爬虫：{', '.join(core_robots)}。",
            "impact": "自愿遵守 robots.txt 的搜索或按需抓取爬虫不会抓取本站，这是内容出现在 AI 搜索中的前提。"
                      "训练爬虫（如 GPTBot、ClaudeBot、Google-Extended）的屏蔽不在本条扣分范围内，但它们也应开放，以便内容进入模型训练语料。",
            "solution": "在 robots.txt 中放行 OAI-SearchBot、Claude-SearchBot、PerplexityBot、ChatGPT-User、Googlebot、Bingbot 等搜索/按需抓取爬虫。"
                        "训练爬虫也建议一并放行。",
            "evidence": [{"url": "/robots.txt", "quote": f"Disallow 命中 {', '.join(core_robots)}"}],
        })
    if training_robots and not core_robots:
        findings.append({
            "severity": "低",
            "scored": False,
            "id": "ACC-ROBOTS-TRAINING",
            "root_cause_id": "crawler_training_info",
            "evidence_kind": "observed",
            "title": "robots.txt 屏蔽了训练爬虫：建议开放，好让内容进入模型的学习材料",
            "problem": f"robots.txt 拦截了训练爬虫：{', '.join(training_robots)}。"
                       "这些是训练爬虫的设置，与搜索爬虫是分开的。",
            "impact": "建议放行这些训练爬虫，好让内容进入模型的学习材料。本项不扣搜索访问分。"
                      "挡住 Google-Extended 不影响 Google 搜索或 AI Overviews，但仍建议放行。",
            "solution": "建议在 robots.txt 中去掉对这些训练爬虫的屏蔽，放行 GPTBot、ClaudeBot、Google-Extended 等。"
                        "搜索爬虫请继续保持开放。",
            "evidence": [{"url": "/robots.txt", "quote": f"Disallow 命中 {', '.join(training_robots)}"}],
        })
    # OGP：只评首页（OGP-01/02 的 scope=home）。内页缺标签只作为建议项、
    # 不参与计分；反过来，内页有标签也不能掩盖首页的缺口。
    home = next((p for p in pages if p["role"] == "home"), None)

    def ogp_missing(p):
        ogp = p.get("ogp") or {}
        missing = [tag for tag in ("og:title", "og:description", "og:image", "og:url") if not ogp.get(tag)]
        if "twitter:card" not in (p.get("html") or "").lower():
            missing.append("twitter:card")
        return missing

    twitter_only = home and ogp_missing(home) == ["twitter:card"]
    if home and ogp_missing(home):
        missing = ogp_missing(home)
        findings.append({
            "severity": "低" if twitter_only else "中",
            "scored": False if twitter_only else True,
            "id": "OGP-HOME",
            "root_cause_id": "ogp_share_hygiene",
            "evidence_kind": "observed",
            "title": "首页社交分享标签不完整" if home["ogp"] else "首页缺少 Open Graph 分享标签",
            "problem": f"首页缺少 {', '.join(missing)}（本项只评首页分享标签完整度）。",
            "impact": "在社交平台或聊天工具里转发时，预览可能不完整。",
            "solution": "如需控制分享预览，为首页补 og:title / og:description / og:image / og:url；twitter:card 为次要辅助项。",
            "code": OGP_EXAMPLE,
            "evidence": [{"url": home["url"], "quote": "缺 " + " / ".join(missing)}],
        })
    elif not any(p["ogp"] for p in pages) and pages:
        findings.append({
            "severity": "中",
            "id": "OGP-NONE",
            "root_cause_id": "ogp_share_hygiene",
            "evidence_kind": "observed",
            "title": "开放图谱分享标签缺失",
            "problem": "抽样页面都没有 og:title/description/image。",
            "impact": "链接被转发时，可能没有稳定的标题和配图。",
            "solution": "为首页和重要落地页补 og:title/description/image。",
            "code": OGP_EXAMPLE,
            "evidence": [{"url": pages[0]["url"], "quote": "缺 og:title / og:description / og:image / og:url"}],
        })

    inner_missing_ogp = [p for p in pages if p is not home and p["role"] == "content" and ogp_missing(p)]
    if inner_missing_ogp:
        findings.append({"severity": "低", "scored": False,
                         "id": "OGP-INNER",
                         "root_cause_id": "ogp_share_hygiene",
                         "evidence_kind": "sample",
                         "title": "内页 Open Graph 标签不完整（建议项，不计分）",
                         "problem": f"{len(inner_missing_ogp)} 个内容页缺少 OGP 标签；OGP 维度只评首页，故不计分。",
                         "impact": "内页被转发时，预览可能不完整。本项不计入分数。",
                         "solution": "如需控制分享预览，为文章与重点落地页补 og:title/description/image。",
                         "code": OGP_EXAMPLE,
                         "evidence": [{"url": p["url"], "quote": "缺 " + " / ".join(ogp_missing(p))} for p in inner_missing_ogp[:3]]})

    # ── 维度驱动的发现项 ──
    missing = _org_missing(org) if org else None
    if missing:
        findings.append({
            "severity": "中",
            "id": "SCH-ORG-INCOMPLETE",
            "root_cause_id": "schema_org",
            "evidence_kind": "observed",
            "title": "Organization 结构化属性不完整",
            "problem": f"已有 Organization 节点，但缺少：{'、'.join(missing)}。",
            "impact": "已有组织信息标记，但字段还不完整。补全与页面文字一致的名称、标志和联系方式，这一项的分数还能提高。",
            "solution": "在 Organization 中按正文已有事实补全字段，并与可见文本保持一致；不要写与正文冲突的值。",
            "code": ORG_JSONLD_EXAMPLE,
            "evidence": [{"url": "", "quote": f"缺 {', '.join(missing)}"}],
        })

    missing_h1 = [p for p in content_pages if not p.get("h1")]
    not_one_h1 = [p for p in content_pages if len(p.get("h1") or []) != 1]
    missing_title = [p for p in content_pages if not (p.get("title") or "").strip()]
    long_title = [p for p in content_pages if len((p.get("title") or "")) > 60]
    if missing_title and len(missing_title) > len(content_pages) * 0.3:
        findings.append({
            "severity": "高",
            "id": "ONP-TITLE-MISSING",
            "root_cause_id": "onpage_title",
            "evidence_kind": "observed",
            "title": "页面缺少 title 标题",
            "problem": f"{len(missing_title)}/{len(content_pages)} 个内容页没有 title。",
            "impact": "缺少 title 比“略长于 60 个字符”严重得多，主题信号会弱很多。",
            "solution": "为每个可索引页写一个能概括本页主题的 title。",
            "evidence": [{"url": p["url"], "quote": "无 title"} for p in missing_title[:3]],
        })
    elif long_title and not missing_title:
        findings.append({
            "severity": "低",
            "scored": False,
            "id": "ONP-TITLE-LENGTH",
            "root_cause_id": "onpage_title_hint",
            "evidence_kind": "observed",
            "title": "部分 title 略长于常见展示长度（提示项）",
            "problem": f"{len(long_title)}/{len(content_pages)} 个内容页的标题超过 60 个字符。这是展示长度提示，不是缺少标题。",
            "impact": "过长的标题在部分搜索结果里可能被截断。",
            "solution": "可酌情缩短标题；不必为凑 60 字符阈值而牺牲含义。",
            "evidence": [{"url": p["url"], "quote": (p.get("title") or "")[:80]} for p in long_title[:3]],
        })
    if missing_h1 and len(missing_h1) > len(content_pages) * 0.5:
        findings.append({
            "severity": "中",
            "id": "ONP-H1-MISSING",
            "root_cause_id": "onpage_h1",
            "evidence_kind": "observed",
            "title": "部分页面在服务端 HTML 中未见 H1",
            "problem": f"{len(missing_h1)}/{len(content_pages)} 个内容页没有 H1。这与“不是恰好一个 H1”不是同一问题。",
            "impact": "完全没有主标题时，主题信号较弱。若正文仍充分，不把它等同于页面没有主内容。",
            "solution": "为内容页设置能概括主题的主标题（建议用 H1）；不必机械追求每页恰好一个。",
            "code": H1_EXAMPLE,
            "evidence": [{"url": p["url"], "quote": "无 H1"} for p in missing_h1[:3]],
        })
    elif not_one_h1 and not missing_h1 and len(not_one_h1) > len(content_pages) * 0.5:
        findings.append({
            "severity": "低",
            "scored": False,
            "id": "ONP-H1-COUNT",
            "root_cause_id": "onpage_h1_hint",
            "evidence_kind": "observed",
            "title": "部分页面不是恰好一个 H1（提示项）",
            "problem": f"{len(not_one_h1)}/{len(content_pages)} 个内容页的主标题（H1）数量不是 1，多数是有多个主标题。",
            "impact": "多个 H1 是结构提示，严重程度低于缺 title 或完全没有主标题。",
            "solution": "建议每个页面保留一个与可见主标题一致的 H1。",
            "code": H1_EXAMPLE,
            "evidence": [{"url": p["url"], "quote": f"H1×{len(p.get('h1') or [])}"} for p in not_one_h1[:3]],
        })

    cit_blocks = (acc.get("citability") or {}).get("content_blocks") or {}
    if cit_blocks and cit_blocks.get("citability_rate", 0) < 25 and content_pages:
        cit_evidence = (acc.get("citability") or {}).get("sample_non_citable") or []
        findings.append({"severity": "高", "title": "内容缺少可被直接引用的答案块",
                         "problem": (f"{cit_blocks.get('total', 0)} 个内容块里只有 {cit_blocks.get('citable', 0)} 个"
                                     f"（{cit_blocks.get('citability_rate', 0)}%）符合「可整段摘用」："
                                     "段落需 100–200 词（中文 60–220 字）、有完整句读、不靠上下文；"
                                     "列表/表格/FAQ 放宽到 30–220 词。"),
                         "impact": "生成式引擎倾向引用能独立成句、可直接摘录的段落；纯营销短句与超长段落都无法被摘录，答案里就不会出现你的表述。",
                         "solution": "把核心内容拆成自包含答案段（先一句结论、再支撑事实与数字），并补齐定义 / 数据 / 对比 / 步骤四类证据块；FAQ 用完整问答句写在 details 或问答区块里。",
                         "evidence": ([{"url": e["url"], "quote": (e.get("text") or "")[:80]} for e in cit_evidence[:3]]
                                      or [{"url": p["url"], "quote": p["content"][:80].strip()} for p in content_pages[:3]])})

    coverage = acc.get("coverage") or {}
    faq_in_sample = any("faq" in (p["url"] or "").lower() or p.get("page_type") == "faq" for p in pages)
    if page_coverage.type_is_unevaluated(coverage, "faq") and not faq_in_sample:
        findings.append({
            "severity": "低",
            "scored": False,
            "id": "RCH-FAQ-UNEVAL",
            "evidence_kind": "sample",
            "title": "FAQ 页未评估（已发现但未抽样）",
            "problem": "sitemap 或发现范围里有 FAQ 类 URL，但本轮抽样未抓取，不能断言站点缺少 FAQ。",
            "impact": "相关内容分项按抽样页计，FAQ 标为未评估，不按缺失计 0。",
            "solution": "如需完整评估 FAQ，请把该页纳入抽样后复测。FAQ 的价值在于真实问答，而不只是标题或某一种 schema 类型。",
        })
    elif not faq_in_sample and "faq" in (coverage.get("observed_absent_types") or []):
        findings.append({
            "severity": "中",
            "id": "RCH-FAQ-ABSENT",
            "evidence_kind": "sample",
            "title": "发现范围内未见 FAQ 问答页",
            "problem": "在 sitemap 与本轮抽样中都没有看到 FAQ 类页面。这是范围内的观察，不是对未发现 URL 的全站断言。",
            "impact": "少了可被直接摘用的问答素材。FAQ 的价值是真实问题与完整答案，而不是有一个 FAQ 标题或 FAQPage 标记。",
            "solution": "围绕用户真正会问的问题写问答（完整问句和可摘用的答案），需要时再辅以结构化标记。",
            "code": FAQ_EXAMPLE,
        })

    # ── 更多 R 规则 ──
    # SCH-05：logo 占位/非图片
    logo = org.get("logo") if org else None
    logo_url = logo.get("url") if isinstance(logo, dict) else logo
    if logo_url and isinstance(logo_url, str) and (re.search(r"example\.com|placeholder", logo_url, re.I) or not re.search(r"\.(png|jpe?g|webp|svg|gif)(\?|#|$)", logo_url, re.I)):
        findings.append({"severity": "中", "title": "Logo 图片为占位/非图片地址",
                         "problem": f"Organization logo=\"{logo_url}\" 是占位或非图片路径。",
                         "impact": "AI 无法解析品牌视觉标识。",
                         "solution": "补全真实 logo 的 http(s) 图片 URL。",
                         "evidence": [{"url": "", "quote": logo_url}]})

    # SCH-08：日期模板/未来
    bad_dates = []
    for p in pages:
        for k, v in p.get("dates", {}).items():
            if re.search(r"1970|2000-01-01|0000", v):
                bad_dates.append({"url": p["url"], "quote": f"{k}={v}"})
    if bad_dates:
        findings.append({"severity": "中", "title": "Schema 日期为模板/异常值",
                         "problem": "检测到 1970/2000-01-01 等模板日期。",
                         "impact": "AI 无法确认内容新鲜度。",
                         "solution": "以真实发布日期为准，修正 schema 日期。",
                         "evidence": bad_dates[:3]})

    # ONP-04：标题层级跳级（有 H3 无 H2）
    skip_pages = [p["url"] for p in content_pages if not p.get("hierarchy_ok", True)]
    if content_pages and len(skip_pages) > len(content_pages) * 0.3:
        findings.append({"severity": "中", "title": "标题层级跳级（H3 先于 H2）",
                         "problem": f"{len(skip_pages)}/{len(content_pages)} 个内容页出现 H3 先于 H2 的层级跳跃。",
                         "impact": "AI 难以重建页面信息结构。",
                         "solution": "按 H1→H2→H3 顺序整理标题层级。",
                         "evidence": [{"url": u, "quote": "有 H3 无 H2"} for u in skip_pages[:3]]})

    # TEC-01：canonical 缺失
    no_canonical = [p["url"] for p in content_pages if not p.get("canonical")]
    if content_pages and len(no_canonical) > len(content_pages) * 0.5:
        findings.append({
            "severity": "低",
            "scored": False,
            "id": "TEC-CANONICAL-MISSING",
            "root_cause_id": "canonical_hint",
            "evidence_kind": "observed",
            "title": "部分页面缺少指向自身的规范网址（canonical）",
            "problem": f"{len(no_canonical)}/{len(content_pages)} 个内容页缺少指向自身的规范网址。",
            "impact": "缺少这个标签，通常不如错误的规范网址或已确认的收录问题严重。如果同一内容有多个网址且没有跳转，应先处理冲突。",
            "solution": "为重点可索引页补自引用 canonical；若已有冲突的 canonical，应先修正错误配置。",
            "evidence": [{"url": u, "quote": "缺 canonical"} for u in no_canonical[:3]],
        })

    # KG-04 / CIT-01：正文缺权威外链。KG 维度只计 sameAs/knowsAbout/foundingDate/address，
    # 本项属于「只报不评」的观察项：列出供改进，但不扣分、不计入严重度色带。
    authority_domains = ("wikipedia.org", "gov", "edu", "ieee.org", "iso.org", "w3.org", "developer.mozilla.org")
    has_authority = any(
        any(dom in link for dom in authority_domains)
        for p in pages for link in p.get("links_external", set())
    )
    if not has_authority and pages:
        findings.append({"severity": "低", "scored": False, "title": "正文缺少权威外部引用（建议项，不计分）",
                         "problem": "正文没有指向权威来源（维基/政府/标准组织）的外链。",
                         "impact": "AI 较难判断内容的事实可信度与作者权威。",
                         "solution": "在内容中引用权威来源并附链接（交易所公告、认证机构、行业标准等）。"})

    # ENT-04：公司法定名多种写法
    if ent.get("company_conflict"):
        names = " / ".join(ent.get("company_names", [])[:3])
        findings.append({"severity": "高", "title": "公司法定名多种写法",
                         "problem": f"公司名（Co., Ltd / Group / Corporation）在不同位置写法不一致：{names}。",
                         "impact": "AI 难以把多个公司名归到同一实体。",
                         "solution": "用实体映射表固定各层级名称写法，与上市主体关联声明。",
                         "evidence": [{"url": "", "quote": n} for n in ent.get("company_names", [])[:3]]})

    # ENT-03：电话占位
    phone_placeholder = []
    for p in pages:
        m = re.search(r'href=["\']tel:([^"\']+)["\']', p["html"], re.I)
        tel = m.group(1) if m else ""
        if tel and TEL_PLACEHOLDER_RE.search(tel):
            phone_placeholder.append({"url": p["url"], "quote": tel})
    if phone_placeholder:
        findings.append({"severity": "中", "title": "联系方式电话为占位值",
                         "problem": "页面电话是占位符（xxx/000 等）。",
                         "impact": "AI 无法把站点归到可联系的真实实体。",
                         "solution": "补全真实联系电话或删除占位。",
                         "evidence": phone_placeholder[:3]})

    # TRU-02：默认/建站商作者名
    default_authors = sorted({n for p in pages for n in p.get("author_names", set()) if default_author(n)})
    if default_authors:
        findings.append({"severity": "高", "title": "文章作者为默认/建站方账号",
                         "problem": f"作者署名是默认账号：{', '.join(default_authors[:3])}。",
                         "impact": "AI 无法判断内容是否由真实专家撰写。",
                         "solution": "替换为真实作者署名，并补充作者简介与资质。",
                         "evidence": [{"url": "", "quote": n} for n in default_authors[:3]]})

    # SCH-09：WebSite.publisher 指向不存在的实体
    website = schema_info.get("website") or {}
    publisher = website.get("publisher") if isinstance(website, dict) else None
    publisher_id = publisher.get("@id") if isinstance(publisher, dict) else None
    if publisher_id and not any(s.get("@id") == publisher_id for s in [schema_info.get("org")] if s and s.get("@id")):
        findings.append({"severity": "中", "title": "Schema @id 引用无法解析",
                         "problem": f"WebSite.publisher 指向 {publisher_id}，但无对应实体定义。",
                         "impact": "AI 无法把站点与发布者实体关联。",
                         "solution": "补全被引用的 Organization 实体，或改用内联 publisher。"})

    # RCH-04：内容新鲜度（无任何日期信号）
    dated_pages = [p for p in pages if p.get("dates")]
    if content_pages and not dated_pages:
        findings.append({"severity": "中", "title": "内容缺少发布时间信号",
                         "problem": "抽样页面没有 datePublished / dateModified 信号。",
                         "impact": "AI 无法判断内容是否更新、是否新鲜。",
                         "solution": "在文章/内容 schema 中补 datePublished 与 dateModified。"})

    # ABS-05：结构化答案资产（列表/表格少）
    has_lists = any(re.search(r"<(ul|ol|table)[ >]", p["html"], re.I) for p in content_pages)
    if content_pages and not has_lists:
        findings.append({"severity": "低", "title": "缺少列表/表格等结构化答案资产",
                         "problem": "内容页几乎没有列表、表格等便于 AI 抽取的结构。",
                         "impact": "AI 更倾向抽取结构化的定义/数据/对比/步骤。",
                         "solution": "用列表/表格呈现关键事实、参数、步骤。"})

    # ── scoring v1.3 additions (generic websites) ──
    try:
        import geo_signals_v13 as v13
        lock = v13.summarize_image_locked(content_pages or pages)
        if lock.get("locked_pages"):
            findings.append({
                "severity": "高", "id": "ABS-IMG-01",
                "title": "主内容疑似图片化/不可抽取",
                "problem": (
                    f"{lock['locked_pages']}/{lock['pages_checked']} 个抽样页可抽取正文不足；"
                    "关键事实可能只存在于图片、背景图或空字段中。"
                ),
                "impact": "生成式引擎难以摘取可引用段落，品牌描述与参数无法被稳定引用。",
                "solution": (
                    lock.get("generic_remediation_en")
                    or "把定义、规格、场景、成果写进可见 HTML 文本；图片只作说明。"
                ),
                "remediation_templates": {
                    "product": v13.PRODUCT_FIELD_CHECKLIST,
                    "case": v13.CASE_FIELD_CHECKLIST,
                    "article": v13.ARTICLE_FIELD_CHECKLIST,
                },
                "evidence": [
                    {"url": d.get("url") or "", "quote": "; ".join((d.get("reasons") or [])[:2])}
                    for d in (lock.get("details") or [])[:4]
                ],
            })
        # Entity address completeness → trust/KG framing (never local-pack)
        corpus = " ".join((p.get("content") or "")[:2000] for p in pages[:8])
        ev = v13.entity_verifiability(corpus, org)
        if not ev.get("complete_enough"):
            findings.append({
                "severity": "中", "id": "ENT-ADDR-01",
                "title": "组织可核验地址/联系信息不完整",
                "problem": (
                    "抽样正文与 Organization schema 中缺少足够的地址（postal/街道/地区文本或 schema address）"
                    "与可核验联系方式。"
                ),
                "impact": "AI 引用时难以把站点落到可核验的 Organization 实体（实体/信任/知识图谱信号），不是本地地图包问题。",
                "solution": "在 About/Contact 与 Organization JSON-LD 中提供一致的地址与 contactPoint。",
                "evidence": [{
                    "url": "",
                    "quote": (
                        f"schema_address={ev.get('schema_address_or_area')} "
                        f"visible_address={ev.get('visible_address_text')} "
                        f"contact={ev.get('schema_contact_point') or ev.get('visible_phone_text')}"
                    ),
                }],
            })
        # URL hygiene findings (also scored lightly inside SEO dim)
        for f in v13.url_hygiene_findings(pages, [p.get("url") or "" for p in pages]):
            # Avoid duplicating TEC-01 canonical-missing if SEO-URL-02 already covers
            if f.get("id") == "SEO-URL-02" and any("canonical" in (x.get("title") or "") for x in findings):
                continue
            findings.append({
                "severity": f.get("severity") or "中",
                "id": f.get("id"),
                "title": f.get("title_zh") or f.get("title"),
                "problem": f.get("problem"),
                "impact": f.get("impact"),
                "solution": f.get("solution"),
                "evidence": f.get("evidence") or [],
                "note": f.get("note") or "",
            })
        # Advisory CWV / old stack (not scored)
        blob = "\n".join((p.get("html") or "")[:3000] for p in pages[:3])
        for adv in v13.advisory_performance_notes(blob):
            findings.append(adv)
        # Multi-UA smoke as Access evidence note
        crawler = acc.get("crawler") or {}
        if crawler.get("ua_results"):
            smoke = v13.multi_ua_smoke_record(crawler.get("ua_results") or [])
            findings.append({
                "severity": "低", "scored": False, "id": "ACC-UA-SMOKE",
                "title": "Multi-UA fetch smoke (Access evidence, advisory)",
                "problem": smoke.get("note"),
                "impact": "Records browser / searchbot / AI-bot status and latency when probed; not a scored dimension.",
                "solution": "Keep AI and search crawlers able to fetch the same primary HTML as browsers.",
                "evidence": [
                    {"url": "", "quote": f"{r.get('ua')}: HTTP {r.get('status')} {r.get('latency_ms')}ms"}
                    for r in (smoke.get("results") or [])[:6]
                ],
            })
    except Exception as exc:  # noqa: BLE001
        findings.append({
            "severity": "低", "scored": False,
            "title": "v1.3 signal pack partially skipped",
            "problem": str(exc)[:200],
            "impact": "",
            "solution": "Re-run analyze.py after fixing geo_signals_v13 import path.",
        })


    # Schema vs body identity: missing Organization is scored in the schema
    # dimension (presence alone is 5 raw / 4.0 of 12). It must not zero entity/KG
    # when the body already identifies the business — that is a wording constraint,
    # not a reason to mark the finding advisory.
    kg_detail = acc.get("kg_detail") or {}
    consistency = acc.get("schema_consistency") or {}
    if not (schema_info.get("org")):
        body_clear = bool(kg_detail.get("body_identifiable"))
        if body_clear:
            title = "缺少组织信息的结构化标记"
            problem = (
                "抽查页面没有组织信息的结构化标记。关于我们、联系页或页脚已经写明了公司和联系方式。"
            )
            fid = "SCH-ABSENT-BODY-CLEAR"
        else:
            title = "缺少组织信息的结构化标记"
            problem = (
                "抽查页面没有组织信息的结构化标记。组织标记是这一项的基础分。"
            )
            fid = "SCH-ABSENT"
        findings.append({
            "severity": "中",
            "scored": True,
            "id": fid,
            "root_cause_id": "schema_org",
            "evidence_kind": "observed",
            "title": title,
            "problem": problem,
            "impact": (
                "这项满分 12 分。补上与页面文字一致的组织信息标记，可以先提到 4 分；"
                "再补名称、标志和联系方式，分数还能提高。"
            ),
            "solution": (
                "在首页与关于我们增加与可见正文一致的 Organization JSON-LD"
                "（法定名称、官网、logo、联系方式），不要填写与正文冲突的字段。"
            ),
            "code": ORG_JSONLD_EXAMPLE,
        })
    for c in (consistency.get("conflicts") or []):
        findings.append({
            "severity": "中",
            "id": "SCH-BODY-CONFLICT",
            "root_cause_id": "schema_body_conflict",
            "evidence_kind": "observed",
            "title": "结构化数据与可见正文不一致",
            "problem": c.get("note") or f"字段 {c.get('field')} 在 schema 与正文中不一致。",
            "impact": "冲突的标记不能当作完整度加分；应以可见正文为准再改 schema。",
            "solution": "以页面上可见的公司信息为准，修改结构化标记，使两者一致。",
            "evidence": [{"url": "", "quote": f"schema={c.get('schema')} body={c.get('body')}"}],
        })

    # ENT-09/10/11 numeric conflicts — verification first
    numeric = acc.get("numeric") or {}
    for rec in numeric.get("ent10_conflicts") or []:
        findings.append({
            "severity": "中",
            "id": "ENT-10",
            "root_cause_id": f"numeric-{rec.get('entity')}-{rec.get('metric')}",
            "evidence_kind": "observed",
            "title": "同一主体的数值主张冲突（已核对年份/口径）",
            "problem": (
                f"实体「{rec.get('entity')}」的 {rec.get('metric')} 出现冲突数值 "
                f"{rec.get('values')}（单位 {rec.get('units')}）。已确认可比较为当前事实。"
            ),
            "impact": "生成式引擎可能摘到互相矛盾的数字。",
            "solution": "统一该主体在当前口径下的官方数字，并在正文标明统计时点与范围。",
            "evidence": [{"url": u, "quote": q} for u, q in zip(rec.get("urls") or [], rec.get("quotes") or [])],
        })
    for rec in numeric.get("ent11_conflicts") or []:
        findings.append({
            "severity": "中",
            "id": "ENT-11",
            "root_cause_id": f"numeric-{rec.get('entity')}-{rec.get('metric')}",
            "evidence_kind": "observed",
            "title": "结构化数据与正文的数值不一致（已核对）",
            "problem": f"schema {rec.get('metric')}={rec.get('schema')}，正文为 {rec.get('body')}。",
            "impact": "同一事实的机器可读值与可见值冲突，完整度不能给高分。",
            "solution": "以页面上可见的文字为准，统一结构化标记。",
            "evidence": [{"url": rec.get("url") or "", "quote": rec.get("quote") or ""}],
        })
    for rec in (numeric.get("needs_review") or [])[:5]:
        findings.append({
            "severity": "低",
            "scored": False,
            "id": rec.get("rule") or "ENT-09",
            "root_cause_id": f"numeric-review-{rec.get('entity')}-{rec.get('metric')}",
            "evidence_kind": "inference",
            "title": "数值差异需先核对年份、口径或版本（未自动判为事实错误）",
            "problem": (
                f"实体「{rec.get('entity')}」的 {rec.get('metric')} 出现不同数字 "
                f"{rec.get('values') or [rec.get('schema'), rec.get('body')]}，"
                f"但带有年份/范围/新闻时效（{rec.get('verification')}），不能直接当作当前事实错误。"
            ),
            "impact": "若把带时间范围的新闻亩数等自动标成当前错误，会造成误报。",
            "solution": "先核对统计时点、口径和版本，再决定是否需要统一当前页表述。",
            "evidence": [{"url": u, "quote": q} for u, q in zip(rec.get("urls") or [rec.get("url") or ""], rec.get("quotes") or [rec.get("quote") or ""])],
        })

    # CLN-08 tiers
    sim = cln.get("similarity") or {}
    if sim.get("verdict") == "fail":
        findings.append({
            "severity": "高",
            "id": "CLN-08",
            "root_cause_id": "duplicate_content",
            "evidence_kind": "observed",
            "title": "跨页正文高度重复（相似度 ≥ 0.9）",
            "problem": f"去模板后相似度 {sim.get('best')}：{sim.get('pair')}。",
            "impact": "近乎复制的页面会稀释可引用的独特内容。",
            "solution": "合并或差异化这两页，保留一个权威版本。",
            "evidence": [{"url": u, "quote": f"相似度 {sim.get('best')}"} for u in (sim.get("pair") or [])],
        })
    elif sim.get("verdict") == "advisory":
        findings.append({
            "severity": "低",
            "scored": False,
            "id": "CLN-08",
            "root_cause_id": "duplicate_content",
            "evidence_kind": "observed",
            "title": "跨页正文较相似（0.75–0.9，建议项，不计分）",
            "problem": f"去模板后相似度 {sim.get('best')}：{sim.get('pair')}。未达到 0.9 的计分门槛。",
            "impact": "可能存在模板化段落，但不按复制站扣核心分。0.5–0.75 的相似度不再计分。",
            "solution": "可酌情差异化重复段落，不是必须立即处理的核心项。",
            "evidence": [{"url": u, "quote": f"相似度 {sim.get('best')}"} for u in (sim.get("pair") or [])],
        })

    # llms.txt experimental
    llms = acc.get("llms") or {}
    findings.append({
        "severity": "低",
        "scored": False,
        "id": "ACC-07-LLMS",
        "root_cause_id": "llms_experimental",
        "evidence_kind": "observed",
        "title": "llms.txt（不计入总分）",
        "problem": (
            ("已找到 llms.txt，质量较好。" if (llms.get("quality") == "high") else
             "已找到 llms.txt，质量：" + str(llms.get("quality") or "一般") + "。")
            if llms.get("present") else
            ("未找到 llms.txt。" + (" " + "；".join(llms.get("reasons") or []) if llms.get("reasons") else ""))
        ),
        "impact": "这项不计入技术总分。这份文件可以帮助部分工具了解网站导航。Google 搜索并不使用它。",
        "solution": "可以按需维护 llms.txt，并与网站导航保持一致。这项不计入总分，不是必须项。",
        "evidence": [{"url": llms.get("url") or "/llms.txt", "quote": (llms.get("body_preview") or "；".join(llms.get("reasons") or []) or "n/a")[:180]}],
    })

    # Bare currency
    bare = ((acc.get("citability") or {}).get("bare_currency")) or []
    if bare:
        findings.append({
            "severity": "低",
            "id": "CIT-CURRENCY",
            "root_cause_id": "bare_currency",
            "evidence_kind": "observed",
            "title": "出现未标明单位的金额",
            "problem": f"抽样正文中有 {len(bare)} 处价格/金额未写明货币单位（例如只有数字）。",
            "impact": "无单位的金额难以被准确摘用或比较。",
            "solution": "在金额旁写明货币或单位（元、万元、USD 等）。",
            "evidence": [{"url": b.get("url") or "", "quote": b.get("quote") or b.get("amount")} for b in bare[:4]],
        })

    # Unsampled product detail must not yield "missing spec table"
    if page_coverage.type_is_unevaluated(coverage, "product_detail") or page_coverage.type_is_unevaluated(coverage, "product"):
        findings.append({
            "severity": "低",
            "scored": False,
            "id": "SCOPE-PRODUCT-UNEVAL",
            "evidence_kind": "sample",
            "title": "产品详情页未评估",
            "problem": "范围内有产品类网址，但本轮抽查没有打开产品详情页，因此没有评估规格表或参数。",
            "impact": "相关分数按已抽查的页面计算，未抽到的类型标为未评估，不按缺失计 0 分。",
            "solution": "如需评估规格与参数，请把代表性产品详情页纳入抽样后复测。",
        })

    # Privacy: never escalate to "AI will not trust this company"
    if "privacy" in (coverage.get("observed_absent_types") or []) or any(
        "privacy" in (w.get("required") or "") for w in (acc.get("coverage") and []) or []
    ):
        pass  # wording is handled if a legal finding already exists; see below

    # Observation mode disclosure
    findings.append({
        "severity": "低",
        "scored": False,
        "id": "OBS-RAW-HTML",
        "evidence_kind": "sample",
        "title": "本轮证据来自原始 HTML（非渲染 DOM）",
        "problem": (acc.get("fetch_observation") or {}).get("note_zh")
                   or "观察基于 HTTP 原始 HTML，不是浏览器渲染后的 DOM。",
        "impact": "仅存在于客户端渲染后的内容可能未被计入。这是样本与采集方式说明，不是额外扣分。",
        "solution": "若关键事实只在渲染后出现，需要补充渲染抓取后再评估那些字段。",
    })

    # Drop or rewrite any finding that would claim unsampled pages are missing specs
    kept = []
    for f in findings:
        blob = " ".join(str(f.get(k) or "") for k in ("title", "problem", "impact", "solution"))
        if page_coverage.should_suppress_missing_finding(coverage, blob):
            f = dict(f)
            f["scored"] = False
            f["severity"] = "低"
            f["evidence_kind"] = "sample"
            f["title"] = (f.get("title") or "") + "（改为未评估，因相关页未抽样）"
            f["problem"] = "该判断所依赖的页面类型本轮未抓取，已改为未评估，不按缺失计 0。"
            f["impact"] = "不对未抓取页面做缺失断言。"
        kept.append(f)
    findings = kept

    return findings


def build_strengths(cln, ent, acc, schema_info):
    strengths = []
    if not ent["brand_conflict"] and not ent["email_conflict"]:
        strengths.append("品牌与实体高度一致，邮箱域名统一。")
    org = schema_info["org"] or {}
    if org.get("sameAs") and org.get("foundingDate"):
        strengths.append("Organization 结构化数据完整（sameAs 社交链接 + 成立日期）。")
    if acc.get("has_llms"):
        strengths.append("网站提供了 llms.txt，这项不计入总分。")
    engines = acc.get("engines") or {}
    chatgpt = (engines.get("chatgpt_search") or {}).get("search_status")
    claude = (engines.get("claude_search") or {}).get("search_status")
    decision = acc.get("crawler_decision") or {}
    training_ok = list(decision.get("training_ok") or [])
    training_blocked = list(decision.get("training_live_blocked") or []) + list(
        decision.get("training_robots_blocked") or acc.get("blocked_training") or []
    )
    if not (acc.get("blocked_core") or decision.get("core_live_blocked") or decision.get("core_robots_blocked")):
        if decision.get("core_ok"):
            core_list = "、".join(decision.get("core_ok") or [])
            if training_ok and not training_blocked:
                train_list = "、".join(training_ok)
                strengths.append(
                    f"搜索爬虫可以访问（{core_list}），训练爬虫也可以访问（{train_list}）。"
                )
            else:
                strengths.append(
                    f"搜索爬虫可以访问（{core_list}）。"
                    "训练爬虫（如 GPTBot、ClaudeBot）建议一并开放，好让内容进入模型的学习材料。"
                )
        elif not acc.get("blocked_core"):
            strengths.append("robots.txt 未屏蔽搜索/按需抓取爬虫。建议同时放行训练爬虫，以便内容进入模型训练语料。")
    if chatgpt == "allowed":
        gpt_live = (engines.get("chatgpt_search") or {}).get("training_live")
        if gpt_live == "allowed":
            strengths.append(
                "ChatGPT 的搜索爬虫（OAI-SearchBot）和训练爬虫（GPTBot）都可以访问。"
            )
        else:
            strengths.append("ChatGPT 搜索爬虫（OAI-SearchBot）可访问。")
    if claude == "unverified":
        pass  # do not list as a strength
    return strengths or ["本次未发现明显亮点。"]


def _absorption_detail(acc):
    cit = acc.get("citability") or {}
    blocks = cit.get("content_blocks") or {}
    evidence = cit.get("evidence_blocks") or {}
    direct = cit.get("direct_answer") or {}
    align = cit.get("query_alignment") or {}
    if not blocks:
        return "未取到可判定的正文内容块。"
    return ("可引用内容块 {citable}/{total}（{rate}%）；"
            "证据块覆盖：定义 {d}、数据 {data}、对比 {c}、步骤 {s}（密度达标的 {dense}/4 类）；"
            "直接回答页 {da}/{dc}；标题与首段对齐 {al}/{ac}。").format(
        citable=blocks.get("citable", 0), total=blocks.get("total", 0),
        rate=blocks.get("citability_rate", 0),
        d=evidence.get("definition_blocks", 0), data=evidence.get("data_blocks", 0),
        c=evidence.get("comparison_blocks", 0), s=evidence.get("step_blocks", 0),
        dense=evidence.get("dense_covered_types", 0),
        da=direct.get("pages_with_direct_answer", 0), dc=direct.get("pages_checked", 0),
        al=align.get("aligned_pages", 0), ac=align.get("pages_checked", 0))


ABSORPTION_TOLERANCE = 0.6
DIMENSION_MAX = {"schema": 12, "entity": 12, "ogp": 5, "richness": 12, "kg": 10,
                 "absorption": 12, "trust": 12, "on_page": 5, "quality": 5, "seo": 15}


def integrity_flags(dims, acc, ent):
    """评分自检：维度分必须与原始分析数据自洽，矛盾时打 flag 而不是静默出报告。

    历史事故：absorption 的计分路径与 CitabilityAnalyzer 用了两套口径，分数长期塌在
    2/15，而同一份数据里可引用率是 39%——两者不可能同时成立，却照常出了报告。
    """
    flags = []
    cit = acc.get("citability") or {}
    blocks = cit.get("content_blocks") or {}

    expected = citability.absorption_score(cit) if cit else 0
    if abs(dims.get("absorption", 0) - expected) > ABSORPTION_TOLERANCE:
        flags.append({"dimension": "absorption", "kind": "score_mismatch",
                      "detail": f"维度分 {dims.get('absorption')} 与 citability 复算值 {expected} 不一致"})

    if blocks.get("citability_rate", 0) >= 20 and dims.get("absorption", 0) <= 1:
        flags.append({"dimension": "absorption", "kind": "floor_collapse",
                      "detail": f"可引用率 {blocks.get('citability_rate')}% 但吸收性仅 {dims.get('absorption')} 分"})

    for key, max_score in DIMENSION_MAX.items():
        if dims.get(key, 0) > max_score + 0.001:
            flags.append({"dimension": key, "kind": "over_max",
                          "detail": f"{dims.get(key)} 超过维度满分 {max_score}"})

    if ent.get("trust_ceiling"):
        if dims.get("trust", 0) > 6.0 + 0.001 or dims.get("entity", 0) > 3.6 + 0.001:
            flags.append({"dimension": "trust", "kind": "ceiling_not_applied",
                          "detail": "命中 Trust Ceiling，但 trust/entity 仍高于 6 / 3.6 的封顶值"})
    return flags


def build_dimension_details(dims, pages, cln, ent, schema_info, acc):
    """每个维度给一段「本维度主要发现」，供报告分维度评估章节使用。"""
    org = schema_info["org"] or {}
    content_pages = [p for p in pages if p["role"] in ("content", "home")]
    n = len(content_pages) or 1
    title_ok = sum(1 for p in content_pages if (p.get("title") or "").strip())
    h1_ok = sum(1 for p in content_pages if p.get("h1"))
    meta_ok = sum(1 for p in content_pages if p["meta"])
    missing_org = _org_missing(org)
    home = next((p for p in pages if p["role"] == "home"), None)
    home_ogp = (home or {}).get("ogp") or {}
    home_ogp_missing = [tag for tag in ("og:title", "og:description", "og:image", "og:url") if not home_ogp.get(tag)]
    if home and "twitter:card" not in (home.get("html") or "").lower():
        home_ogp_missing.append("twitter:card")
    faq_count = sum(1 for p in pages if "faq" in p["url"].lower())
    article_count = sum(1 for p in pages if any(re.search(r"Article|BlogPosting", str(s.get("@type", ""))) for s in p["schemas"] if isinstance(s, dict)))
    total_content_len = sum(len(p["content"]) for p in content_pages)

    details = {
        "schema": ("Organization 节点" + ("存在" if org else "缺失") +
                   ("；缺 " + "、".join(missing_org) if missing_org else "，属性基本完整") + "。"),
        "entity": ("品牌写法" + ("不一致（" + " / ".join(list(ent["brand_names"])[:3]) + "）" if ent["brand_conflict"] else "一致") +
                   "；邮箱域名" + ("多个不一致（S1）" if ent["email_conflict"]
                                 else ("为外部域名/免费邮箱（W 警告项，不计分）" if ent.get("email_off_domain") else "与站点一致")) +
                   "。"),
        "ogp": ("首页分享标签 " + ("缺失 " + "、".join(home_ogp_missing) if home_ogp_missing else "完整") +
                "（只评首页分享预览卫生，内页不计分；不是 AI 理解或信任门槛）。"),
        "richness": (f"FAQ 页 {faq_count} 个；文章/博客页 {article_count} 个；"
                     f"内容页正文合计 {total_content_len} 字符。"
                     + ((" 未评估类型：" + "、".join((acc.get("coverage") or {}).get("unevaluated_types") or []))
                        if (acc.get("coverage") or {}).get("unevaluated_types") else "")),
        "kg": (
            "站内实体信号（正文与 schema 去重合计）：社交/档案 "
            + (f"{len((acc.get('kg_detail') or {}).get('profiles') or [])} 条"
               if (acc.get("kg_detail") or {}).get("profiles") else "未见")
            + "、成立信息 "
            + ("有" if (acc.get("kg_detail") or {}).get("founding") else "缺")
            + "、地址/联系 "
            + ("有" if (acc.get("kg_detail") or {}).get("address") else "缺")
            + "。缺 schema 不表示主体无法确认。"
        ),
        "absorption": _absorption_detail(acc),
        "trust": ("信任页：About " + ("有" if any('about' in p['url'].lower() for p in pages) else "缺") +
                  "、Contact " + ("有" if any('contact' in p['url'].lower() for p in pages) else "缺") +
                  "、合规页 " + ("有" if any(p['role'] == 'legal' for p in pages) else "缺") +
                  "（About/Contact 需实质内容，默认合规模板不计分）。"),
        "on_page": (f"有 title {title_ok}/{n}、有 Meta {meta_ok}/{n}、有 H1 {h1_ok}/{n}（长度略超 60 或并非恰好一个 H1 只作提示）。"),
        "quality": ("占位文案 " + (f"{len(cln['lorem'])} 处" if cln['lorem'] else "无") +
                    "、0 值计数器 " + (f"{len(cln['zero'])} 处" if cln['zero'] else "无") +
                    "、默认合规模板 " + (f"{len(cln['legal'])} 处" if cln['legal'] else "无") + "。"),
        "seo": "见 seo_discoverability 分章（标题/H1/meta、薄内容、站内链接、sitemap/robots）。",
    }
    out = []
    for d in dims:
        out.append({**d, "detail": details.get(d["key"], "")})
    return out


def build_scope(pages, site, acc):
    role_counts = {}
    for p in pages:
        role_counts[p["role"]] = role_counts.get(p["role"], 0) + 1
    return {
        "sitemap_count": site.get("sitemap", {}).get("url_count", len(pages)),
        "sampled_count": len(pages),
        "role_counts": role_counts,
        "blocked": acc.get("blocked_core") or [],
        "blocked_all": acc.get("blocked") or [],
        "blocked_training": acc.get("blocked_training") or [],
        "has_llms": acc.get("has_llms"),
        "llms": acc.get("llms") or {"present": acc.get("has_llms"), "experimental": True, "in_core_score": False},
        # run.py 的必检页后置补入结果：找不到 FAQ/About/Contact/Privacy 时在此告警，
        # 报告「检测范围」页据此提示「相关维度可能因缺页被低估」。未抽样 ≠ 缺失。
        "scope_warnings": list(site.get("scope_warnings") or []),
        "coverage": acc.get("coverage") or {},
        "unevaluated_types": (acc.get("coverage") or {}).get("unevaluated_types") or [],
        "score_scope": "sampled_pages",
        "crawler_access": {
            "reachable": acc.get("reachable"),
            "ai_blocked": acc.get("ai_blocked") or [],
            "training_blocked_live": acc.get("training_blocked_live") or [],
            "waf_challenge": bool(acc.get("waf_challenge")),
            "engines": acc.get("engines") or {},
            "roles": {
                "search_index": (acc.get("crawler_decision") or {}).get("core_ok"),
                "core_blocked": (acc.get("crawler_decision") or {}).get("core_live_blocked"),
                "training_blocked": (acc.get("crawler_decision") or {}).get("training_live_blocked"),
            },
        },
        "observation_mode": acc.get("observation_mode") or "raw_http_html",
        # 站点快照说明（例如线上被验证码拦截、改用归档证据时，明确写清快照日期与来源）
        "note": site.get("snapshot_note") or "",
    }


def llm_review(pages, site):
    """LLM 语义判定（R+LLM/LLM 规则：ENT-06/07、ONP-06、TRU-06、QLT、CIT-02/03、ABS-03）。

    可插拔：设置环境变量 GEO_EVAL_LLM_API_KEY（可选 GEO_EVAL_LLM_BASE_URL / GEO_EVAL_LLM_MODEL）
    走 OpenAI 兼容 chat/completions；未配置或调用失败返回 None（规则降级，报告注明）。
    返回 list[finding]，或 None 表示未启用/失败。
    """
    api_key = os.environ.get("GEO_EVAL_LLM_API_KEY")
    if not api_key:
        return None
    base_url = os.environ.get("GEO_EVAL_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("GEO_EVAL_LLM_MODEL", "gpt-4o-mini")

    brand_names = set()
    emails = set()
    org_name = ""
    for p in pages:
        for s in p["schemas"]:
            if isinstance(s, dict) and re.search(r"Organization|WebSite", str(s.get("@type", ""))):
                if s.get("name"):
                    org_name = str(s["name"])
                break
        brand_names.add(p["ogp"].get("og:site_name", "") if p["ogp"].get("og:site_name") else "")
        emails.update(EMAIL_RE.findall(p["content"]))
        if "about" in p["url"].lower() and p["h1"]:
            brand_names.add(p["h1"][0])
    brand_names.discard("")
    site_type = site.get("site_type", {}).get("type", "corporate")

    # 只取少量页面文本，控制 prompt 体积
    excerpts = []
    for p in pages[:6]:
        excerpts.append({"url": p["url"], "title": p["title"], "text": p["content"][:800]})

    prompt = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": (
                "你是 GEO（生成式引擎优化）评审。基于给定网页证据，找出与「声明/历史矛盾、"
                "子品牌/代理关系不清、缺少一手经验、营销空话、关键数据无出处、对题度低」相关的具体问题。"
                "只输出 JSON：{\"findings\":[{\"severity\":\"高|中|低\",\"title\":\"…\",\"problem\":\"…\","
                "\"impact\":\"…\",\"solution\":\"…\",\"evidence\":\"原文片段\"}]}。"
                "没有把握就不要编造；最多 5 条。")},
            {"role": "user", "content": (
                f"站点类型：{site_type}\n品牌名：{', '.join(brand_names) or '未知'}\n"
                f"Organization.name：{org_name or '无'}\n邮箱：{', '.join(list(emails)[:5])}\n\n"
                f"页面摘录：{json.dumps(excerpts, ensure_ascii=False)}")},
        ],
    }

    try:
        import urllib.request
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(prompt).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.loads(r.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed.get("findings") or []
    except Exception:
        return None


def analyze(run_dir):
    pages = load_pages(run_dir)
    if not pages:
        return {"error": "no pages found", "overall_score": 0, "grade": "F", "findings": []}

    site = load_site(run_dir)
    domain = site.get("registrable_domain") or registrable_domain(pages[0]["url"])
    base_url = site.get("url") or pages[0]["url"]

    cln = detect_cln(pages)
    ent = detect_ent(pages, domain)
    schema_info = detect_schema(pages)
    if schema_info.get("org"):
        # 统一在这里清洗 sameAs：所有下游（schema/kg 计分、缺失项、优点、维度解读）共用一份。
        org = dict(schema_info["org"])
        org["sameAs"] = clean_same_as(org.get("sameAs"), domain)
        schema_info["org"] = org
    acc = detect_acc(run_dir, base_url)
    sitemap_urls = load_sitemap_urls(run_dir)
    acc["coverage"] = page_coverage.coverage_report(pages, site, sitemap_urls)
    acc["numeric"] = entity_signals.analyze_numeric_conflicts(
        pages, schema_info.get("org"), default_entity=domain,
    )
    acc["fetch_observation"] = {
        "kind": "raw_http_html",
        "note_zh": "本轮观察来自 HTTP 原始 HTML，不是渲染后的 DOM。",
        "note_en": "Observations are from raw HTTP HTML, not a rendered DOM.",
    }

    dims = score_dimensions(pages, site, cln, ent, schema_info, acc)

    # SEO dimension (/15) — heuristic raw /25 scaled in seo_analyze
    seo_block = None
    try:
        import seo_analyze
        seo_block = seo_analyze.build_seo_block(run_dir)
        dims["seo"] = float(seo_block.get("dim_score") if seo_block.get("dim_score") is not None
                            else seo_block.get("score") or 0)
    except Exception as exc:  # noqa: BLE001
        seo_block = {
            "score": 0.0, "max": 15, "dim_score": 0.0,
            "score_raw_25": None, "max_raw_25": 25,
            "grade": "F", "confidence": "none",
            "notes": [f"SEO block unavailable: {exc}"],
            "rubric": "seo_scoring.md v1.2", "part_of_technical_100": True,
        }
        dims["seo"] = 0.0

    # Trust Ceiling
    ceiling = None
    ceiling_note = ""
    if ent["trust_ceiling"]:
        ceiling = 70
        ceiling_note = "品牌写法/邮箱域名冲突 → 信任度≤6/12、品牌与实体≤3.6/12、总分≤70"
        dims["trust"] = min(dims["trust"], 6.0)
        dims["entity"] = min(dims["entity"], 3.6)
    if cln["lorem"]:
        ceiling = 75 if ceiling is None else min(ceiling, 75)
        ceiling_note = (ceiling_note + "；" if ceiling_note else "") + "残留 lorem 占位 → 总分≤75"

    base = round(sum(dims.values()), 1)
    if ceiling:
        base = min(base, ceiling)

    # penalty / bonus
    # Training-bot blocks do not enter the core −15. llms.txt is experimental
    # and no longer grants a general-purpose +3 in the core 100.
    # Documented ItemList +3 is applied here (bonus cap ≤ +10).
    penalty, bonus = 0, 0
    adjustments = []
    decision = acc.get("crawler_decision") or crawler_roles.core_penalty_decision(
        acc.get("blocked") or [], (acc.get("crawler") or {}).get("ua_results") or [],
        waf_challenge=bool(acc.get("waf_challenge")),
    )
    if decision.get("apply"):
        penalty += 15
        reason = crawler_roles.penalty_reason_zh(decision) or "搜索/按需抓取爬虫不可达"
        adjustments.append({"type": "penalty", "points": -15, "reason": reason})
    has_itemlist = any(
        re.search(r"ItemList", str(s.get("@type", "")))
        for p in pages for s in (p.get("schemas") or []) if isinstance(s, dict)
    )
    if has_itemlist:
        bonus += 3
        adjustments.append({"type": "bonus", "points": 3, "reason": "有 ItemList Schema"})

    bonus = min(bonus, 10)
    overall = int(max(0, min(100, base - penalty + bonus)))
    acc["score_formula"] = {
        "expression": "overall = clamp(0, 100, int(base_score - penalty + bonus))",
        "base_score": base,
        "penalty": penalty,
        "bonus": bonus,
        "overall": overall,
    }
    grade = grade_for(overall)

    dims_meta = [
        {"name": "结构化数据", "key": "schema", "max": 12},
        {"name": "品牌与实体一致性", "key": "entity", "max": 12},
        {"name": "开放图谱与分享", "key": "ogp", "max": 5},
        {"name": "内容覆盖与新鲜度", "key": "richness", "max": 12},
        {"name": "站内实体信号", "key": "kg", "max": 10},
        {"name": "答案可吸收性", "key": "absorption", "max": 12},
        {"name": "信任度", "key": "trust", "max": 12},
        {"name": "页面主题与元数据", "key": "on_page", "max": 5},
        {"name": "内容质量", "key": "quality", "max": 5},
        {"name": "SEO 内容可发现性", "key": "seo", "max": 15},
    ]
    for d in dims_meta:
        d["score"] = dims[d["key"]]
        d["pct"] = round(dims[d["key"]] / d["max"] * 100, 1)
        d["grade"] = grade_for(d["pct"])

    findings = build_findings(cln, ent, schema_info, acc, pages)
    strengths = build_strengths(cln, ent, acc, schema_info)
    dimension_details = build_dimension_details(dims_meta, pages, cln, ent, schema_info, acc)
    scope = build_scope(pages, site, acc)

    # LLM 语义判定（可插拔；未配置 API key 则降级为规则结果）
    llm_findings = llm_review(pages, site)
    llm_enabled = llm_findings is not None
    if llm_findings:
        findings.extend(llm_findings)

    top = [f["title"] for f in findings[:3]]
    if grade in ("A+", "A"):
        summary = "技术基础扎实、实体信息完整，整体已达优秀/良好门槛，主要是细节优化。"
    elif grade == "B":
        summary = f"整体良好，主要短板：{'、'.join(top) or '个别细节项'}。"
    elif grade == "C":
        summary = f"存在明显短板（{'、'.join(top) or '内容/结构'}），建议优先处理高优先级问题。"
    else:
        summary = f"基础较弱，需先修复核心问题（{'、'.join(top) or '抓取/理解/信任'}）。"

    report_out = {
        "url": base_url,
        "domain": domain,
        "sitemap_count": site.get("sitemap", {}).get("url_count", len(pages)),
        "sampled_count": len(pages),
        "overall_score": overall,
        "grade": grade,
        "base_score": base,
        "penalty": penalty,
        "bonus": bonus,
        "adjustments": adjustments,
        "ceiling": ceiling,
        "ceiling_note": ceiling_note,
        "versions": {"methodology_version": "v2026.10", "rules_version": "v1.1",
                     "scoring_version": "v1.3", "seo_scoring_version": "v1.2"},
        "data_integrity_flags": integrity_flags(dims, acc, ent),
        "dimensions": dims_meta,
        "dimension_details": dimension_details,
        "scope": scope,
        "findings": findings,
        "strengths": strengths,
        "llm_enabled": llm_enabled,
        "overall_summary": summary,
        "closing": "优先处理上述高优先级问题，再持续补充真实内容与实体声明。" if findings else "技术基础与内容结构良好，保持并持续补充真实内容即可。",
        "score_formula": acc.get("score_formula") or {
            "expression": "overall = clamp(0, 100, int(base_score - penalty + bonus))",
            "base_score": base, "penalty": penalty, "bonus": bonus, "overall": overall,
        },
        "coverage": acc.get("coverage") or {},
        "llms": acc.get("llms") or {"present": bool(acc.get("has_llms")), "experimental": True, "in_core_score": False},
        "crawler_engines": acc.get("engines") or {},
        "observation_mode": acc.get("observation_mode") or "raw_http_html",
        "counters": {
            "sampled_count": len(pages),
            "sitemap_count": site.get("sitemap", {}).get("url_count", len(pages)),
            "finding_count": len(findings),
            "bare_currency": len(((acc.get("citability") or {}).get("bare_currency")) or []),
            "citability_rate": (acc.get("absorption_rate")),
        },
    }
    # SEO narrative block (score already folded into dims / overall_score)
    report_out["seo_discoverability"] = seo_block
    report_out["category_scores"] = {
        d["key"]: {"score": d["score"], "max": d["max"], "percentage": d["pct"], "grade": d["grade"]}
        for d in dims_meta
    }
    report_out["score_adjustments"] = {
        "base_score": base,
        "penalty": penalty,
        "bonus": min(bonus, 10),
        "adjustments": adjustments,
    }
    return report_out


def main():
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    report = analyze(run_dir)
    out = os.path.join(run_dir, "report.json")

    # 保护已富化的报告：enrich.py（或人工）写过的 report.json 不能在此被引擎原判覆盖。
    # 重跑 analyze.py 常见于「只补一条规则」的场景，直接覆盖会丢掉 findings 改写、
    # 维度解读、总评与站点专属建议（本 run 曾因此丢失过一次）。
    enriched = False
    if os.path.isfile(out):
        try:
            with open(out, encoding="utf-8") as f:
                prev = json.load(f)
            enriched = bool(prev.get("llm_enabled")) or bool((prev.get("llm_review") or {}).get("reviewed"))
        except (ValueError, OSError):
            enriched = False
    if enriched:
        print(f"[analyze] 检测到已富化的 {os.path.basename(out)}，仅更新 report.engine.json，不覆盖富化稿")
        out = os.path.join(run_dir, "report.engine.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    # 引擎快照：LLM 富化（enrich.py）以此为输入；report.json 被富化覆盖后仍可回看引擎原判
    with open(os.path.join(run_dir, "report.engine.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"wrote {out}  →  总分 {report.get('overall_score')}/{report.get('grade')}  findings={len(report.get('findings', []))}")


if __name__ == "__main__":
    main()
