#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 1: 重新抓取目标站点证据包（robots / sitemaps / llms / 24 个深检页面）。
产出 evidence/{robots.txt, sitemap_index.xml, *-sitemap.xml, llms*.txt, pages/*.html}
以及 evidence/pages.list（slug|url 清单，供 build_evidence.py 还原页面 URL）。"""
import os, re, sys, time, json, urllib.request, urllib.error
from urllib.parse import urljoin

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(ROOT, "evidence")
PAGES = os.path.join(EVID, "pages")
BASE = "https://www.sofeyiahome.com"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"}

# 深检页面（与 2026-09-10 首轮同一组 24 页，保证口径可比）
SAMPLED = {
    "home": "/",
    "about": "/about-us/",
    "contact": "/contact-us/",
    "faq": "/faq/",
    "news": "/news/",
    "company_news": "/company-news/",
    "article_hq": "/company-news/company-news-sofeyia-group-unveils-new-hq-in-guangzhou-cbd-marking-strategic-leap/",
    "article_canton": "/company-news/exhibition-news-sofeyia-at-the-137th-canton-fair-2025/",
    "products": "/products/",
    "product_detail": "/detail/alpha-pro-series/",
    "project": "/project/",
    "project_detail": "/detail/cavalli-tower-location-erbil-iraq/",
    "partnership": "/partnership/",
    "team": "/team/",
    "services": "/services/",
    "privacy": "/_privacy-policy/",
    "terms": "/_term-of-use/",
    "cookie": "/_cookie-policy/",
    "demo_header": "/pabriz-header/",
    "demo_error": "/pabriz-error-404/",
    "system_cart": "/cart/",
    "system_checkout": "/checkout/",
    "system_account": "/my-account/",
    "system_thanks": "/thanks/",
}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode("utf-8", "replace")

def save(name, content_bytes):
    p = os.path.join(EVID, name)
    with open(p, "wb") as f:
        f.write(content_bytes)
    return len(content_bytes)

def main():
    os.makedirs(PAGES, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    log = []

    # robots.txt
    st, b = get(BASE + "/robots.txt"); save("robots.txt", b); log.append(f"robots.txt HTTP {st} {len(b)}B")

    # sitemap index + 子站点地图
    st, b = get(BASE + "/sitemap_index.xml"); save("sitemap_index.xml", b)
    sub = sorted(set(re.findall(r"<loc>([^<]+)</loc>", b.decode("utf-8", "replace"))))
    log.append(f"sitemap_index HTTP {st} sub-sitemaps={len(sub)}")
    for u in sub:
        name = u.rstrip("/").split("/")[-1]
        if not name.endswith(".xml"):
            name = "sitemap-" + name + ".xml"
        st2, b2 = get(u); save(name, b2); log.append(f"  {name} HTTP {st2} {len(b2)}B")

    # llms.txt / llms-full.txt（预期 404，仅记录状态）
    for n in ("llms.txt", "llms-full.txt"):
        st3, b3 = get(BASE + "/" + n); save(n, b3); log.append(f"{n} HTTP {st3} {len(b3)}B")

    # 深检页面
    manifest = []
    for slug, path in SAMPLED.items():
        url = BASE + path
        st4, b4 = get(url)
        save(os.path.join("pages", slug + ".html"), b4)
        manifest.append(f"{slug}|{url}")
        log.append(f"page {slug:16s} HTTP {st4} {len(b4)}B")
        time.sleep(0.15)

    # manifest（build_evidence.py 读取）
    manifest_text = "\n".join(manifest) + "\n"
    with open(os.path.join(EVID, "pages.list"), "w", encoding="utf-8") as f:
        f.write(manifest_text)
    with open("/tmp/pages.list", "w", encoding="utf-8") as f:  # 兼容旧脚本路径
        f.write(manifest_text)
    log.append("pages.list written (%d pages)" % len(manifest))

    print("\n".join(log))
    # 汇总 sitemap URL 数
    locs = set()
    for fn in os.listdir(EVID):
        if fn.endswith("-sitemap.xml") or fn == "sitemap_index.xml":
            locs |= set(re.findall(r"<loc>([^<]+)</loc>",
                                    open(os.path.join(EVID, fn), encoding="utf-8", errors="replace").read()))
    print("TOTAL sitemap URLs:", len(locs))

if __name__ == "__main__":
    main()
