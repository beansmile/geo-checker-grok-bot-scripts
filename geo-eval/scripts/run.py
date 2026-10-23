#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEO 深度评测 · 参数化入口

用法:
    python3 run.py <目标网址> [--site-type corporate|personal|blog|ecommerce|saas] [--max-pages 24]

作用:
    1) 抓 robots / sitemap / llms.txt
    2) 从 sitemap 发现 URL，按页面角色分类（home/content/trust/legal/system/demo）
    3) 抽样抓取深检页面 HTML
    4) 生成 run 目录 + site.json + scope.json（后续 Step 2~5 的输入）

说明:
    本脚本完成「Step 1 抓站 + 页面角色分类 + 站点画像」这一通用部分；
    后续 Step 3~5 的规则判定/LLM/专家复核/报告，见同目录下其余脚本与 ../pipeline.md。
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin, urlparse

# 抓取 UA：与 geo_ready 的 HttpFetcher::USER_AGENT 保持一致的主流桌面 Chrome 串。
# 早期带 `GeoEval/1.0` 后缀、版本停在 Chrome/126，部分站点会按「非主流 UA」直接 403/挑战。
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
}

# 页面角色判定（优先级 demo > system > legal > trust > content）
ROLE_RULES = [
    ("demo", re.compile(r"(pabriz-|elementor-|/page/|\?page_id=|/template|/demo)", re.I)),
    ("system", re.compile(r"(/cart|/checkout|/my-account|/account|/login|/signin|/register|/search|/tag/|/archive|/feed|/404|/thanks)", re.I)),
    ("legal", re.compile(r"(privacy|terms|tos|cookie|legal)", re.I)),
    ("trust", re.compile(r"(/about|/contact|/team|/our-story|/mission|/company|/partnership|/history)", re.I)),
]

ROLE_PRIORITY = {"demo": 0, "system": 1, "legal": 2, "trust": 3, "content": 4}
ROLE_QUOTA = {"home": 1, "trust": 6, "content": 12, "legal": 3, "system": 4, "demo": 4}

# 必检页：FAQ 页决定 richness(+5) 与 absorption(+3)，About/Contact 决定 trust(+4/+3)，
# Privacy 决定 trust 的合规项(+3)。角色配额抽样可能在达到 --max-pages 前就把它们挤掉
# （btphysio 实测：/faqs/ 在 sitemap 里，却因 16 页上限没入样，同一事实连丢 8 分）。
REQUIRED_PAGES = (
    ("faq", r"faq"),
    ("about", r"about"),
    ("contact", r"contact"),
    ("privacy", r"privacy"),
)


def classify_role(url):
    path = urlparse(url).path
    role = "content"
    for name, pat in ROLE_RULES:
        if pat.search(path):
            role = name
            break
    return role


def backfill_required_pages(discovered, sampled):
    """角色配额抽样后的后置强制补入：确保 FAQ / About / Contact / Privacy 各入样至少一页。

    超额补入，不挤掉已抽样页；sitemap 里确实没有对应页面时输出 scope 警告，
    供报告「检测范围」页说明相关维度可能被低估。
    """
    warnings = []
    taken = set(sampled)
    for name, pat in REQUIRED_PAGES:
        if any(re.search(pat, u, re.I) for u in sampled):
            continue
        cand = next((u for u in discovered if re.search(pat, u, re.I)), None)
        if cand and cand not in taken:
            sampled.append(cand)
            taken.add(cand)
        else:
            warnings.append({"required": name, "reason": "not_found"})
    return sampled, warnings


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode("utf-8", "replace")


# ── ACC-02 / ACC-03：AI 爬虫实测可达性 + WAF 挑战识别 ──────────────
# rules.md 要求用真实 AI UA 实抓，而不是只读 robots.txt：
#   ACC-02 AI UA 可达性：OAI-SearchBot / GPTBot / ClaudeBot / PerplexityBot 各抓首页
#   ACC-03 WAF/挑战拦截迹象：普通 UA 抓取返回挑战页 / 403 / 429
AI_UA_PROBES = {
    "OAI-SearchBot": "Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",
    "GPTBot":        "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)",
    "ClaudeBot":     "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
}
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
# 挑战页特征：SiteGround 用 202 + sg-captcha + meta refresh 跳验证页
CHALLENGE_MARKERS = re.compile(
    r"sg-?captcha|/sgcaptcha|captcha|challenge|cf-browser-verification|"
    r"just a moment|attention required|verify you are human|"
    r"enable javascript and cookies|checking your browser", re.I)
CHALLENGE_HEADERS = re.compile(r"^(sg-captcha|cf-mitigated|x-robot-challenge)", re.I)


def _probe(url, ua, timeout=20):
    """用指定 UA 抓一次，返回状态/是否挑战页/响应头。"""
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, body, hdrs = r.status, r.read(20000), r.headers
    except urllib.error.HTTPError as e:
        status, body, hdrs = e.code, e.read(20000)[:20000], e.headers
    except Exception as e:  # noqa: BLE001
        return {"status": 0, "challenge": False, "error": str(e)[:200], "size": 0}
    text = body.decode("utf-8", "replace")
    chal = bool(CHALLENGE_MARKERS.search(text))
    for k, v in (hdrs or {}).items():
        if CHALLENGE_HEADERS.match(f"{k}") and re.search(r"challenge|block|verify", f"{k}:{v}", re.I):
            chal = True
    # 202 且体积很小 → 典型挑战页；403/429 直接算拦截
    if status == 202 or status in (403, 429):
        chal = True
    return {"status": status, "challenge": chal, "size": len(body),
            "content_length": (hdrs or {}).get("content-length"), "error": ""}


def test_crawler_access(base_url, out_path):
    """实测 AI 爬虫可达性；结果落盘供 analyze.py 读取（离线也能复现）。"""
    results = []
    for name, ua in AI_UA_PROBES.items():
        r = _probe(base_url, ua)
        r["ua"] = name
        results.append(r)
        print(f"      [crawler] {name:14s} HTTP {r['status']:<3} "
              f"{'CHALLENGE' if r['challenge'] else 'ok'}  {r['size']}B")
    baseline = _probe(base_url, BROWSER_UA)
    baseline["ua"] = "browser"
    results.append(baseline)
    print(f"      [crawler] {'browser':14s} HTTP {baseline['status']:<3} "
          f"{'CHALLENGE' if baseline['challenge'] else 'ok'}  {baseline['size']}B")

    ai_blocked = [r for r in results if r["ua"] != "browser" and (r["challenge"] or r["status"] in (0, 403, 429))]
    payload = {
        "url": base_url,
        "ua_results": results,
        "ai_blocked": [r["ua"] for r in ai_blocked],
        "waf_challenge": bool(baseline["challenge"]),
        "reachable": all(r["status"] == 200 and not r["challenge"] for r in results),
    }
    save(out_path, json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def save(path, content_bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(content_bytes, bytes) else "w"
    with open(path, mode, encoding=None if mode == "wb" else "utf-8") as f:
        f.write(content_bytes)
    return len(content_bytes)


def parse_sitemap_urls(body):
    urls = re.findall(rb"<loc>\s*([^<\s]+)\s*</loc>", body)
    return [html_unescape(u.decode("utf-8", "replace")) for u in urls]


def html_unescape(s):
    return (s.replace("&amp;", "&").replace("&lt;", "<")
             .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))


def is_sitemap_index(body):
    return b"<sitemapindex" in body[:2000].lower()


def is_xml_url(url):
    path = urlparse(url).path.lower()
    return path.endswith(".xml") or path.endswith(".xml.gz") or "/sitemap" in path


def expand_sitemap(base, body, run_dir):
    """展开 sitemap：若为 sitemapindex 则递归抓取子 sitemap，返回真实页面 URL（剔除 XML）。"""
    urls = parse_sitemap_urls(body)
    if not is_sitemap_index(body):
        return [u for u in urls if not is_xml_url(u)]

    children = [u for u in urls if urlparse(u).netloc == urlparse(base).netloc or not urlparse(u).netloc]
    children = [urljoin(base + "/", u) for u in children]
    print(f"      检测到 sitemapindex，展开 {len(children)} 个子 sitemap")

    sm_dir = os.path.join(run_dir, "evidence", "sitemaps")

    def grab(u):
        return u, *fetch(u)

    page_urls, seen = [], set()
    with ThreadPoolExecutor(max_workers=5) as ex:
        for u, code, cbody in ex.map(grab, children):
            name = re.sub(r"[^a-z0-9]+", "_", urlparse(u).path.strip("/")).strip("_") or "sitemap"
            save(os.path.join(sm_dir, f"{name}.xml"), cbody)
            if code != 200:
                print(f"      [{code}] 子 sitemap 抓取失败：{u}")
                continue
            found = [x for x in parse_sitemap_urls(cbody) if not is_xml_url(x)]
            print(f"      [{code}] {u.split('/')[-1][:48]}  → {len(found)} 个页面 URL")
            for x in found:
                if x not in seen:
                    seen.add(x)
                    page_urls.append(x)
    return page_urls


def registrable_domain(url):
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def next_run_id(domain):
    """同一天多次评测自动递增（run01 → run02 …）。

    原先硬编码 run01：同一天重跑会**静默覆盖**上一次的 evidence 与报告
    （report.engine.json / report.json / report/ 全部被改写），无法回滚对比。
    """
    date = datetime.now().strftime("%Y-%m-%d")
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    domain_dir = os.path.join(skill_root, "runs", domain)
    for i in range(1, 100):
        candidate = f"{date}_run{i:02d}"
        if not os.path.isdir(os.path.join(domain_dir, candidate)):
            return candidate
    return f"{date}_run{int(time.time())}"


def main():
    ap = argparse.ArgumentParser(description="GEO 深度评测 · 抓站入口")
    ap.add_argument("url")
    ap.add_argument("--site-type", default=None)
    ap.add_argument("--max-pages", type=int, default=24)
    ap.add_argument("--fetch-only", action="store_true", help="只抓站，跳过检测与报告")
    args = ap.parse_args()

    base = args.url.rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    domain = registrable_domain(base)

    run_id = next_run_id(domain)
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run_dir = os.path.join(skill_root, "runs", domain, run_id)
    ev = os.path.join(run_dir, "evidence", "pages")
    os.makedirs(ev, exist_ok=True)

    print(f"[1/4] 抓 robots / sitemap / llms  →  {base}")
    robots_body = fetch(base + "/robots.txt")[1]
    sitemap_body = fetch(base + "/sitemap.xml")[1]
    llms_body = fetch(base + "/llms.txt")[1]
    save(os.path.join(run_dir, "evidence", "robots.txt"), robots_body)
    save(os.path.join(run_dir, "evidence", "sitemap.xml"), sitemap_body)
    save(os.path.join(run_dir, "evidence", "llms.txt"), llms_body)

    print("[2/4] 从 sitemap 发现 URL 并分类")
    urls = expand_sitemap(base, sitemap_body, run_dir)
    print(f"      sitemap 共发现 {len(urls)} 个真实页面 URL")

    home_url = base + "/"
    discovered = [home_url] + [u for u in urls
                               if u.rstrip("/") != base and not is_xml_url(u)]

    # 按角色分桶后再抽样：保证 trust / legal 等少数角色不被海量商品页挤掉
    buckets = {}
    for u in discovered:
        role = "home" if urlparse(u).path in ("", "/") else classify_role(u)
        buckets.setdefault(role, []).append(u)
    for role, items in buckets.items():
        print(f"      角色 {role:8s} {len(items)} 个")

    # trust 角色内优先 about / contact（品牌/邮箱一致性检测的关键页）
    def trust_priority(u):
        p = urlparse(u).path.lower()
        if "about" in p:
            return 0
        if "contact" in p:
            return 1
        return 2

    sampled = []
    for role in ("home", "trust", "legal", "content", "system", "demo"):
        limit = ROLE_QUOTA.get(role, 0)
        items = buckets.get(role, [])
        if role == "trust":
            items = sorted(items, key=trust_priority)
        for u in items[:limit]:
            if len(sampled) >= args.max_pages:
                break
            sampled.append(u)

    # 名额未用满时，用剩余页面补齐（同角色内顺延）
    if len(sampled) < args.max_pages:
        taken = set(sampled)
        for role in ("content", "trust", "legal", "system", "demo"):
            for u in buckets.get(role, []):
                if len(sampled) >= args.max_pages:
                    break
                if u not in taken:
                    sampled.append(u)
                    taken.add(u)

    # 后置强制补入必检页（FAQ/About/Contact/Privacy）。配额抽样可能把它们挤掉，
    # 而 checklist 里缺页会系统性低估多个维度，必须在抓取前补回。
    sampled, scope_warnings = backfill_required_pages(discovered, sampled)
    for w in scope_warnings:
        print(f"      [scope] 缺少必检页：{w['required']}（相关维度可能被低估）")

    print(f"[3/4] 抓取 {len(sampled)} 个深检页面（并发）")
    def fetch_one(u):
        code, body = fetch(u)
        return u, code, body

    pages = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        for u, code, body in ex.map(fetch_one, sampled):
            slug = re.sub(r"[^a-z0-9]+", "_", urlparse(u).path.strip("/") or "home").strip("_") or "home"
            save(os.path.join(ev, f"{slug}.html"), body)
            role = "home" if urlparse(u).path in ("", "/") else classify_role(u)
            pages.append({"url": u, "slug": slug, "role": role, "status": code})
            print(f"      [{code}] {u}  ({role})")

    with open(os.path.join(ev, "pages.list"), "w", encoding="utf-8") as f:
        f.write("\n".join(f"{p['slug']}|{p['url']}" for p in pages))

    # 站点画像（Step 2 build_evidence.py 的输入）
    site = {
        "url": base + "/",
        "domain": urlparse(base).hostname or "",
        "registrable_domain": domain,
        "site_type": {"type": args.site_type or "corporate", "source": "manual" if args.site_type else "auto"},
        "sitemap": {"url_count": len(urls)},
        "pages_sampled": pages,
        "scope_warnings": scope_warnings,
    }
    save(os.path.join(run_dir, "site.json"), json.dumps(site, ensure_ascii=False, indent=2))
    save(os.path.join(run_dir, "scope.json"), json.dumps({"pages": pages, "pages_total": len(urls)}, ensure_ascii=False, indent=2))

    # ACC-02 / ACC-03：用真实 AI UA 实测可达性（robots.txt 只管自愿遵守，不代表能取到）
    print("[4/5] 实测 AI 爬虫可达性（ACC-02/ACC-03）")
    try:
        test_crawler_access(site["url"], os.path.join(ev, "crawler_access.json"))
    except Exception as e:  # noqa: BLE001
        print(f"      [crawler] 实测失败，已跳过：{e}")

    print(f"[4/4] 抓取完成 → {run_dir}")

    # Step 3~5：通用检测 + 评分 + LLM 深度解读 + 出报告（analyze.py → enrich.py → build_report.py）
    if not args.fetch_only:
        import subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print("[5/7] 规则检测 + 9 维评分  →  report.engine.json")
        subprocess.run([sys.executable, os.path.join(script_dir, "analyze.py"), run_dir], check=False)
        print("[6/7] LLM 深度解读（复核 findings + 重写分维度/总评）  →  report.json")
        subprocess.run([sys.executable, os.path.join(script_dir, "enrich.py"), run_dir], check=False)
        print("[7/7] 生成报告  →  report/report.md + report/report.html")
        subprocess.run([sys.executable, os.path.join(script_dir, "build_report.py"), run_dir], check=False)
        print(f"\n完成。报告在 {run_dir}/report/ 下，可直接打开 report.html 查看。")
    else:
        print("      已用 --fetch-only，跳过检测与报告；后续手动跑 analyze.py / enrich.py / build_report.py（见 ../pipeline.md）")


if __name__ == "__main__":
    main()
