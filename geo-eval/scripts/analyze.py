#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 3~4：通用 GEO 深度检测 + 9 维评分 → report.json

用法:
    python3 analyze.py <run_dir>

输入:  run_dir（run.py 产物：evidence/pages/*.html、pages.list、site.json、scope.json、robots.txt、llms.txt）
输出:  <run_dir>/report.json（9 维得分、总分、等级、findings、penalty/bonus）

口径:  9 维 100 分制（schema 15 · entity 15 · ogp 5 · richness 15 · kg 10 · absorption 15 · trust 15 · on_page 5 · quality 5）
       Trust Ceiling：S1 实体冲突 → trust≤50%、entity≤30%、总分≤70；S1 lorem → 总分≤75
       纯规则 R（不含 LLM）；LLM 类判定（ENT-07、QLT 等）留待 merge_llm.py 扩展。
"""

import html as html_lib
import json
import os
import re
import sys
from urllib.parse import urlparse

import citability

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

# AI 检索爬虫（critical）
AI_CRAWLERS = ["GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "GoogleExtendedCrawler", "Bingbot", "ChatGPT-User", "anthropic-ai"]

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
        if not fname.endswith(".html"):
            continue
        slug = fname[:-5]
        url = url_map.get(slug, slug)
        html = open(os.path.join(pages_dir, fname), encoding="utf-8", errors="ignore").read()

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

        pages.append({
            "url": url, "slug": slug, "role": classify_role(url),
            "title": title, "meta": meta, "h1": h1s, "h2": h2s, "h3": h3s,
            "hierarchy_ok": hierarchy_ok,
            "schemas": schemas, "ogp": ogp, "content": content, "html": html,
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
    return {"lorem": lorem, "zero": zero, "legal": legal, "cta": cta, "soft404": soft404,
            "demo": demo, "system": system, "bloat_ratio": bloat_ratio, "residue": residue}


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
    names = {}
    for p in pages:
        text = p["content"]
        for name in COMPANY_NAME_RE.findall(text):
            n = re.sub(r"\s+", " ", name).strip()
            if len(n) <= 60:
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
    company_keys = {normalize_brand(n) for n in company_names} - {""}
    company_conflict = len(company_keys) >= 2

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


def _robots_section_blocks_all(robots, ua):
    """判断某 User-agent 段是否有「Disallow: /」（整站屏蔽，路径恰好是 /）。"""
    m = re.search(r"User-agent:\s*" + re.escape(ua) + r"(.*?)(?=User-agent:|\Z)", robots, re.S | re.I)
    if not m:
        return None  # 无该 UA 专属段
    return bool(re.search(r"^Disallow:\s*/\s*$", m.group(1), re.M))


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
    llms_path = os.path.join(run_dir, "evidence", "llms.txt")
    has_llms = False
    if os.path.isfile(llms_path):
        body = open(llms_path, encoding="utf-8", errors="ignore").read()
        has_llms = len(body) > 10 and not body.strip().startswith("<!doctype") and not body.strip().startswith("<html")
    # ACC-02 / ACC-03：读取 run.py 用真实 AI UA 实测的结果（离线可复现）
    crawler = {}
    crawler_path = os.path.join(run_dir, "evidence", "crawler_access.json")
    if os.path.isfile(crawler_path):
        try:
            crawler = json.load(open(crawler_path, encoding="utf-8"))
        except (ValueError, OSError):
            crawler = {}
    return {
        "blocked": blocked,
        "has_llms": has_llms,
        "crawler": crawler,
        "ai_blocked": list(crawler.get("ai_blocked") or []),
        "waf_challenge": bool(crawler.get("waf_challenge")),
        "reachable": crawler.get("reachable"),      # True / False / None(未实测)
    }


# ── 9 维评分 ──────────────────────────────────────────────
def score_dimensions(pages, site, cln, ent, schema_info, acc):
    domain = site.get("registrable_domain") or registrable_domain(pages[0]["url"] if pages else "")
    content_pages = [p for p in pages if p["role"] == "content" or p["role"] == "home"]

    # schema (15)
    org = schema_info["org"] or {}
    schema_score = 0
    if org:
        schema_score += 5  # Organization 存在
        name = str(org.get("name", ""))
        if name and not NAME_PLACEHOLDER_RE.search(name):
            schema_score += 2
        if org.get("sameAs"):
            schema_score += 2
        if org.get("contactPoint") or org.get("logo"):
            schema_score += 2
        if org.get("foundingDate"):
            schema_score += 1
        if org.get("url"):
            schema_score += 1
    schema_score += 2 if schema_info["website"] else 0
    schema_score = min(schema_score, 15)

    # entity (15)：15 - 实体扣分
    entity_deduction = 0
    if ent["brand_conflict"]:
        entity_deduction += 10
    if ent["email_conflict"]:
        entity_deduction += 8
    entity_score = max(0, min(15, 15 - entity_deduction))

    # ogp (5)：OGP-01/02 的 scope 是 home，只评首页。
    # 旧实现取「首个带 ogp 的页面」后 break，首页缺 og:image 时会被一篇完整的文章掩盖，
    # 导致首页的缺口永远看不到分。
    home = next((p for p in pages if p["role"] == "home"), None)
    ogp_score = 0
    if home and home["ogp"]:
        ogp_score = sum([
            0.75 if home["ogp"].get("og:title") else 0,
            0.75 if home["ogp"].get("og:description") else 0,
            0.75 if home["ogp"].get("og:image") else 0,
            0.75 if home["ogp"].get("og:url") else 0,
            2.0 if "twitter:card" in (home["html"].lower()) else 0,
        ])
    # 保留 2 位小数：0.75 × 3 + 2 = 4.25，round(x, 1) 会因银行家舍入变成 4.2
    ogp_score = round(min(ogp_score, 5), 2)

    # richness (15)：FAQ 5 + 文章 5 + 内容量 5。
    # llms.txt 只在 adjustments 里 +3，不在本维重复计分（旧实现同一文件共 6 分）。
    faq_pages = [p for p in pages if "faq" in p["url"].lower()]
    article_like = sum(1 for p in pages if any(re.search(r"Article|BlogPosting", str(s.get("@type", ""))) for s in p["schemas"] if isinstance(s, dict)))
    content_len = sum(len(p["content"]) for p in content_pages)
    richness = 0
    richness += 5 if faq_pages else 0
    richness += 5 if article_like >= 2 else (2.5 if article_like >= 1 else 0)
    richness += 5 if content_len > 20000 else (2.5 if content_len > 8000 else 0)
    richness = min(richness, 15)

    # kg (10)：sameAs ≤4 + knowsAbout 3 + foundingDate 1 + address 2 = 10
    # 旧实现 sameAs ≤3 + knowsAbout 2 → 检查项合计只有 8 分，维度满分不可达。
    kg_score = 0
    if org:
        sameas = org.get("sameAs") or []
        kg_score += min(4, len(sameas) if isinstance(sameas, list) else (1 if sameas else 0))
        if org.get("knowsAbout"):
            kg_score += 3
        if org.get("foundingDate"):
            kg_score += 1
        if org.get("address") or org.get("location") or org.get("areaServed"):
            kg_score += 2
    kg_score = min(kg_score, 10)

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

    about_pages = [p for p in pages if re.search(r"(about|our-story|/story|mission|/company|history|brand)", p["url"], re.I)]
    contact_pages = [p for p in pages if re.search(r"(contact|support|help|service|faq)", p["url"], re.I)]
    legal_pages = [p for p in pages if p["role"] == "legal"]
    has_about = bool(about_pages)
    has_contact = bool(contact_pages)
    has_legal = bool(legal_pages)
    author_present = any(re.search(r"Person|Author", str(s.get("@type", ""))) for p in pages for s in p["schemas"] if isinstance(s, dict))
    trust = 0
    trust += 4 if has_about and any(substantial(p) for p in about_pages) else 0
    trust += 3 if has_contact and any(substantial(p) for p in contact_pages) else 0
    trust += 3 if has_legal and legal_pages and not legal_template_urls else 0
    trust += 3 if author_present else 0
    trust += 2 if content_len > 10000 else 0
    trust = min(trust, 15)

    # on_page (5)
    title_ok = sum(1 for p in content_pages if 10 <= len(p["title"]) <= 60)
    meta_ok = sum(1 for p in content_pages if p["meta"])
    h1_ok = sum(1 for p in content_pages if len(p["h1"]) == 1)
    n = len(content_pages) or 1
    on_page = 0
    on_page += 1 if title_ok >= n * 0.8 else 0
    on_page += 1 if meta_ok >= n * 0.8 else 0
    on_page += 1 if h1_ok >= n * 0.8 else 0
    on_page += 2 if title_ok >= n * 0.8 and meta_ok >= n * 0.8 else 0

    # quality (5)：5 - 清洁度扣分
    q_deduction = 0
    if cln["lorem"]:
        q_deduction += min(len(cln["lorem"]) * 2, 5)
    if cln["zero"]:
        q_deduction += min(len(cln["zero"]), 2)
    if cln["legal"]:
        q_deduction += min(len(cln["legal"]), 2)
    if cln["demo"]:
        q_deduction += 1
    quality = max(0, min(5, 5 - q_deduction))

    return {
        "schema": schema_score, "entity": entity_score, "ogp": ogp_score,
        "richness": richness, "kg": kg_score, "absorption": absorption,
        "trust": trust, "on_page": on_page, "quality": quality,
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

    if _ai_blocked:
        findings.append({
            "severity": "严重" if len(_ai_blocked) >= 3 else "高",
            "title": "AI 检索爬虫实测被拦截（robots.txt 放行不等于能取到）",
            "problem": f"用真实 AI 爬虫 UA 实测首页：{('、'.join(_ai_blocked))} 共 {len(_ai_blocked)} 个 UA 被拦截"
                       f"（返回验证页 / 403 / 429 或超时）。而 robots.txt 本身是放行的，说明拦截发生在 CDN/WAF 层，"
                       f"robots.txt 无法反映。",
            "impact": "生成式引擎的检索爬虫拿不到页面内容，站内写得再好也不会进入 AI 的答案来源。"
                      "这类拦截通常对客户不可见——robots.txt 检查一切正常，只有实测才会暴露。",
            "solution": "在 CDN/WAF 的机器人防护里放行 OAI-SearchBot、GPTBot、ClaudeBot、PerplexityBot、"
                        "Google-Extended 与 Bingbot，或关闭对已知 AI 检索爬虫的挑战；放行后重跑本项复测。",
            "evidence": _ua_evidence(set(_ai_blocked)),
        })
    elif acc.get("waf_challenge"):
        _b = next((r for r in _ua_rows if r.get("ua") == "browser"), {})
        findings.append({
            "severity": "高",
            "title": "WAF/机器人挑战会拦截抓取（普通请求即返回验证页）",
            "problem": f"用普通浏览器 UA 请求首页即命中机器人验证（HTTP {_b.get('status')}，"
                       f"响应体仅 {_b.get('size')} 字节），说明站点前置了 WAF 挑战。"
                       f"AI 检索爬虫通常不会执行验证脚本，因此同样会被挡在这一层。",
            "impact": "抓取方需要在 robots.txt 之外再突破一层验证；AI 爬虫一般不具备这种能力，"
                      "结果是页面内容无法被读取，站内优化无法转化为被引用。",
            "solution": "在 WAF 中为已知 AI 检索爬虫（OAI-SearchBot、GPTBot、ClaudeBot、PerplexityBot、"
                        "Google-Extended、Bingbot）配置放行规则，或把挑战策略限定在登录/表单路径。",
            "evidence": [{"url": _base,
                          "quote": f"UA browser → HTTP {_b.get('status')}，命中验证页，响应体 {_b.get('size')} 字节"}],
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
    if acc["blocked"]:
        findings.append({"severity": "严重", "title": "AI 检索爬虫被 robots 屏蔽",
                         "problem": f"robots.txt 拦截了 {', '.join(acc['blocked'])}。",
                         "impact": "AI 抓不到站点内容。",
                         "solution": "放行 AI 检索爬虫（GPTBot/ClaudeBot 等）。",
                         "evidence": [{"url": "/robots.txt", "quote": f"Disallow 命中 {', '.join(acc['blocked'])}"}]})
    # OGP：只评首页（OGP-01/02 的 scope=home）。内页缺标签只作为建议项、
    # 不参与计分；反过来，内页有标签也不能掩盖首页的缺口。
    home = next((p for p in pages if p["role"] == "home"), None)

    def ogp_missing(p):
        ogp = p.get("ogp") or {}
        missing = [tag for tag in ("og:title", "og:description", "og:image", "og:url") if not ogp.get(tag)]
        if "twitter:card" not in (p.get("html") or "").lower():
            missing.append("twitter:card")
        return missing

    if home and ogp_missing(home):
        missing = ogp_missing(home)
        findings.append({"severity": "高" if not home["ogp"] else "中",
                         "title": "首页 Open Graph 标签不完整" if home["ogp"] else "首页缺少 Open Graph 标签",
                         "problem": f"首页缺少 {', '.join(missing)}（OGP 只评首页，内页有覆盖也不补分）。",
                         "impact": "首页是分享与 AI 摘要最常引用的入口，缺标签会让标题/配图/摘要不可控。",
                         "solution": "为首页补全 og:title / og:description / og:image / og:url 与 twitter:card。",
                         "code": OGP_EXAMPLE,
                         "evidence": [{"url": home["url"], "quote": "缺 " + " / ".join(missing)}]})
    elif not any(p["ogp"] for p in pages) and pages:
        findings.append({"severity": "高", "title": "开放图谱完全缺失",
                         "problem": "所有页面都没有 og:title/description/image。",
                         "impact": "分享与 AI 摘要时没有配图标题。",
                         "solution": "为重要页面补 og:title/description/image。",
                         "code": OGP_EXAMPLE,
                         "evidence": [{"url": pages[0]["url"], "quote": "缺 og:title / og:description / og:image / og:url"}]})

    inner_missing_ogp = [p for p in pages if p is not home and p["role"] == "content" and ogp_missing(p)]
    if inner_missing_ogp:
        findings.append({"severity": "低", "scored": False,
                         "title": "内页 Open Graph 标签不完整（建议项，不计分）",
                         "problem": f"{len(inner_missing_ogp)} 个内容页缺少 OGP 标签；OGP 维度只评首页，故不计分。",
                         "impact": "内页被转发或引用时标题与配图可能不完整，但不影响本轮评分。",
                         "solution": "为文章与重点落地页补 og:title/description/image 与 twitter:card。",
                         "code": OGP_EXAMPLE,
                         "evidence": [{"url": p["url"], "quote": "缺 " + " / ".join(ogp_missing(p))} for p in inner_missing_ogp[:3]]})

    # ── 维度驱动的发现项 ──
    missing = _org_missing(org) if org else None
    if missing:
        findings.append({"severity": "高", "title": "Organization 实体属性不完整",
                         "problem": f"已有 Organization 节点，但缺少：{'、'.join(missing)}。",
                         "impact": "AI 拿不到可核验的实体事实，难以把品牌与知识图谱中的实体对齐，"
                                   "在「是什么品牌/在哪/凭什么可信」类问题里引用意愿低。",
                         "solution": "在 Organization 中补 sameAs、foundingDate、address、knowsAbout；信息与站内 About 页保持一致。",
                         "code": ORG_JSONLD_EXAMPLE,
                         "evidence": [{"url": "", "quote": f"缺 {', '.join(missing)}"}]})

    no_h1 = [p for p in content_pages if len(p["h1"]) != 1]
    if content_pages and len(no_h1) > len(content_pages) * 0.5:
        findings.append({"severity": "高", "title": "页面缺少唯一 H1 主标题",
                         "problem": f"{len(no_h1)}/{len(content_pages)} 个内容页服务端 HTML 中没有且仅有一个 H1。",
                         "impact": "H1 是页面主题的最强信号，缺失会让 AI 难以判定该页的主实体与主题，摘要时易抓错重点。",
                         "solution": "商品/内容页主标题改用唯一 H1（每页仅一个），H2/H3 用于分层。",
                         "code": H1_EXAMPLE,
                         "evidence": [{"url": p["url"], "quote": (p["h1"][0] if len(p["h1"]) >= 1 else "无 H1")} for p in no_h1[:3]]})

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

    if not any("faq" in p["url"].lower() for p in pages):
        findings.append({"severity": "中", "title": "缺少 FAQ / 深度内容资产",
                         "problem": "样本中未发现 FAQ 页，也未发现成规模的指南/博客类长内容。",
                         "impact": "缺少问答型与教程型内容，AI 在长尾问题里没有可引用的素材。",
                         "solution": "围绕用户高频问题建 FAQ（配 FAQPage schema）与选购/保养指南类长文。",
                         "code": FAQ_EXAMPLE})

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
        findings.append({"severity": "中", "title": "页面缺少 canonical 标签",
                         "problem": f"{len(no_canonical)}/{len(content_pages)} 个内容页缺自引用 canonical。",
                         "impact": "AI 和搜索引擎难以判断权威 URL，可能把参数页/重复页当独立页。",
                         "solution": "为每个页面补 <link rel=\"canonical\"> 指向权威 URL。",
                         "evidence": [{"url": u, "quote": "缺 canonical"} for u in no_canonical[:3]]})

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

    return findings


def build_strengths(cln, ent, acc, schema_info):
    strengths = []
    if not ent["brand_conflict"] and not ent["email_conflict"]:
        strengths.append("品牌与实体高度一致，邮箱域名统一。")
    org = schema_info["org"] or {}
    if org.get("sameAs") and org.get("foundingDate"):
        strengths.append("Organization 结构化数据完整（sameAs 社交链接 + 成立日期）。")
    if acc["has_llms"]:
        strengths.append("提供 llms.txt，已向 AI 提供结构化站点摘要。")
    if not acc["blocked"]:
        if acc.get("reachable") is True:
            strengths.append("robots.txt 放行 AI 检索爬虫，实测四个 AI UA 均可正常抓取。")
        elif acc.get("reachable") is None:
            strengths.append("robots.txt 未屏蔽任何 AI 检索爬虫（未做实测可达性）。")
        # reachable is False：实测被拦截，不得作为优势（另出 finding）
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
DIMENSION_MAX = {"schema": 15, "entity": 15, "ogp": 5, "richness": 15, "kg": 10,
                 "absorption": 15, "trust": 15, "on_page": 5, "quality": 5}


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
        if dims.get("trust", 0) > 7.5 + 0.001 or dims.get("entity", 0) > 4.5 + 0.001:
            flags.append({"dimension": "trust", "kind": "ceiling_not_applied",
                          "detail": "命中 Trust Ceiling，但 trust/entity 仍高于 7.5 / 4.5 的封顶值"})
    return flags


def build_dimension_details(dims, pages, cln, ent, schema_info, acc):
    """每个维度给一段「本维度主要发现」，供报告分维度评估章节使用。"""
    org = schema_info["org"] or {}
    content_pages = [p for p in pages if p["role"] in ("content", "home")]
    n = len(content_pages) or 1
    title_ok = sum(1 for p in content_pages if 10 <= len(p["title"]) <= 60)
    h1_ok = sum(1 for p in content_pages if len(p["h1"]) == 1)
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
                "（只评首页，内页不计分）。"),
        "richness": (f"FAQ 页 {faq_count} 个；文章/博客页 {article_count} 个；"
                     f"内容页正文合计 {total_content_len} 字符。"),
        "kg": ("实体信号：sameAs " + (f"{len(org.get('sameAs') or [])} 条" if org.get("sameAs") else "缺") +
               "、foundingDate " + ("有" if org.get("foundingDate") else "缺") +
               "、knowsAbout " + ("有" if org.get("knowsAbout") else "缺") + "。"),
        "absorption": _absorption_detail(acc),
        "trust": ("信任页：About " + ("有" if any('about' in p['url'].lower() for p in pages) else "缺") +
                  "、Contact " + ("有" if any('contact' in p['url'].lower() for p in pages) else "缺") +
                  "、合规页 " + ("有" if any(p['role'] == 'legal' for p in pages) else "缺") +
                  "（About/Contact 需实质内容，默认合规模板不计分）。"),
        "on_page": (f"Title 合格 {title_ok}/{n}、Meta {meta_ok}/{n}、唯一 H1 {h1_ok}/{n}。"),
        "quality": ("占位文案 " + (f"{len(cln['lorem'])} 处" if cln['lorem'] else "无") +
                    "、0 值计数器 " + (f"{len(cln['zero'])} 处" if cln['zero'] else "无") +
                    "、默认合规模板 " + (f"{len(cln['legal'])} 处" if cln['legal'] else "无") + "。"),
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
        "blocked": acc["blocked"],
        "has_llms": acc["has_llms"],
        # run.py 的必检页后置补入结果：找不到 FAQ/About/Contact/Privacy 时在此告警，
        # 报告「检测范围」页据此提示「相关维度可能因缺页被低估」。
        "scope_warnings": list(site.get("scope_warnings") or []),
        "crawler_access": {
            "reachable": acc.get("reachable"),
            "ai_blocked": acc.get("ai_blocked") or [],
            "waf_challenge": bool(acc.get("waf_challenge")),
        },
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

    dims = score_dimensions(pages, site, cln, ent, schema_info, acc)

    # Trust Ceiling
    ceiling = None
    ceiling_note = ""
    if ent["trust_ceiling"]:
        ceiling = 70
        ceiling_note = "品牌写法/邮箱域名冲突 → 信任度≤7.5、品牌与实体≤4.5、总分≤70"
        dims["trust"] = min(dims["trust"], 7.5)
        dims["entity"] = min(dims["entity"], 4.5)
    if cln["lorem"]:
        ceiling = 75 if ceiling is None else min(ceiling, 75)
        ceiling_note = (ceiling_note + "；" if ceiling_note else "") + "残留 lorem 占位 → 总分≤75"

    base = round(sum(dims.values()), 1)
    if ceiling:
        base = min(base, ceiling)

    # penalty / bonus
    penalty, bonus = 0, 0
    adjustments = []
    # ACC-01 / ACC-02 / ACC-03：AI 检索爬虫不可达 → −15。
    # robots.txt 屏蔽与实测拦截（WAF/挑战页）是同一个后果的两种成因，只扣一次，不叠加。
    robots_blocked = list(acc.get("blocked") or [])
    live_blocked = list(acc.get("ai_blocked") or [])
    _waf = bool(acc.get("waf_challenge"))
    if robots_blocked or live_blocked or _waf:
        penalty += 15
        if robots_blocked and (live_blocked or _waf):
            reason = ("AI 爬虫不可达：robots.txt 屏蔽 " + ", ".join(robots_blocked)
                      + "；实测同样被拦截（WAF/挑战页）。两种成因计一次")
        elif robots_blocked:
            reason = f"AI 爬虫被 robots.txt 屏蔽（{', '.join(robots_blocked)}）"
        else:
            names = ", ".join(live_blocked) if live_blocked else "普通请求"
            reason = f"AI 爬虫实测被拦截（{names} 命中 WAF/挑战页，robots.txt 放行但取不到）"
        adjustments.append({"type": "penalty", "points": -15, "reason": reason})
    if acc["has_llms"]:
        bonus += 3
        adjustments.append({"type": "bonus", "points": 3, "reason": "有 llms.txt"})

    overall = int(max(0, min(100, base - penalty + bonus)))
    grade = grade_for(overall)

    dims_meta = [
        {"name": "结构化数据", "key": "schema", "max": 15},
        {"name": "品牌与实体一致性", "key": "entity", "max": 15},
        {"name": "开放图谱与分享", "key": "ogp", "max": 5},
        {"name": "内容覆盖与新鲜度", "key": "richness", "max": 15},
        {"name": "站内实体信号", "key": "kg", "max": 10},
        {"name": "答案可吸收性", "key": "absorption", "max": 15},
        {"name": "信任度", "key": "trust", "max": 15},
        {"name": "页面主题与元数据", "key": "on_page", "max": 5},
        {"name": "内容质量", "key": "quality", "max": 5},
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

    return {
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
                     "scoring_version": "v1.1"},
        "data_integrity_flags": integrity_flags(dims, acc, ent),
        "dimensions": dims_meta,
        "dimension_details": dimension_details,
        "scope": scope,
        "findings": findings,
        "strengths": strengths,
        "llm_enabled": llm_enabled,
        "overall_summary": summary,
        "closing": "优先处理上述高优先级问题，再持续补充真实内容与实体声明。" if findings else "技术基础与内容结构良好，保持并持续补充真实内容即可。",
    }


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
