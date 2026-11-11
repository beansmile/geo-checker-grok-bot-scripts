#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract content-GEO signals from crawled HTML or text snapshots.

Input: run_dir with evidence/pages/*.{html,md,txt} and optional pages.list / site.json
Output: content_extract.json (page inventory + text stats + taxonomy hints)
scoring v1.3 also attaches image_locked / unverified_claims / entity address flags.
"""

from __future__ import annotations

import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.meta_desc = ""
        self.h1 = []
        self.headings = []  # (level, text)
        self._heading_level = 0
        self._heading_buf = []
        self.links = []
        self.images_total = 0
        self.images_with_alt = 0
        self._skip = 0
        self._text_parts = []
        self.canonical = ""

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (ad.get("name") or ad.get("property") or "").lower()
            if name in ("description", "og:description") and not self.meta_desc:
                self.meta_desc = (ad.get("content") or "").strip()
        elif tag == "link" and (ad.get("rel") or "").lower() == "canonical":
            self.canonical = (ad.get("href") or "").strip()
        elif tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag in ("h1", "h2", "h3", "h4"):
            self._heading_level = int(tag[1])
            self._heading_buf = []
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
        elif tag in ("h1", "h2", "h3", "h4") and self._heading_level:
            text = re.sub(r"\s+", " ", "".join(self._heading_buf)).strip()
            if text:
                self.headings.append((self._heading_level, text))
                if self._heading_level == 1:
                    self.h1.append(text)
            self._heading_level = 0
            self._heading_buf = []

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        elif self._heading_level:
            self._heading_buf.append(data)
        else:
            self._text_parts.append(data)


PAGE_TYPE_RULES = [
    ("home", re.compile(r"(index\.html?|/home/?$|^\s*$)", re.I)),
    ("about", re.compile(r"about|company|概况|关于", re.I)),
    ("contact", re.compile(r"contact|联系", re.I)),
    ("privacy", re.compile(r"privacy|隐私", re.I)),
    ("faq", re.compile(r"faq|问答|常见问题", re.I)),
    ("product", re.compile(r"product|产品|chanpin|/cp/|hot-products", re.I)),
    ("event", re.compile(
        r"summit|峰会|经销商大会|经销商年会|dealer[- ]?(meet|summit|conference)|"
        r"open[- ]day|展会|博览|开业典礼",
        re.I,
    )),
    ("case", re.compile(r"case|project|工程案例|cases|客户案例", re.I)),
    ("news", re.compile(r"news|资讯|动态|媒体|新闻|公告|arcnews|media", re.I)),
    ("solution", re.compile(r"solution|解决方案|(?<!行)方案", re.I)),
    ("rd", re.compile(r"patent|研发|技术|rd|research|spec", re.I)),
    ("download", re.compile(r"download|资料", re.I)),
    ("market", re.compile(r"market|region|cities|locations|coverage|服务区域|/city/|区域业务", re.I)),
]


SLOGAN_RE = re.compile(
    r"(专业|品质卓越|匠心|因光而生|点亮未来|值得信赖|行业领先|"
    r"professional|excellent quality|world[- ]class|leading manufacturer)",
    re.I,
)
SPEC_RE = re.compile(
    r"(\d+\s*(W|kW|V|mm|m|IP\d+|kg)|规格|参数|功率|配光|材质|风压|模块化|"
    r"specification|watt|lumen|modular)",
    re.I,
)
EVIDENCE_RE = re.compile(
    r"(专利|资质|奖|认证|壹级|甲级|案例|项目|发明|iF|神灯|质量奖|"
    r"patent|certif|award|ISO|case study)",
    re.I,
)


def classify_page_type(url: str, title: str, text: str) -> str:
    blob = f"{url} {title}"
    for name, pat in PAGE_TYPE_RULES:
        if pat.search(blob):
            return name
    if EVIDENCE_RE.search(text[:2000]) and "news" in url.lower():
        return "news"
    return "other"


def extract_file(path: str, url: str = "") -> dict:
    raw = open(path, "rb").read()
    # Detect encoding lightly
    try:
        text_in = raw.decode("utf-8")
    except UnicodeDecodeError:
        text_in = raw.decode("gbk", "replace")

    ext = os.path.splitext(path)[1].lower()
    out = {
        "path": path,
        "url": url,
        "source_format": ext.lstrip(".") or "unknown",
        "title": "",
        "meta_description": "",
        "h1": [],
        "headings": [],
        "canonical": "",
        "word_count": 0,
        "char_count": 0,
        "internal_link_count": 0,
        "images_total": 0,
        "images_with_alt": 0,
        "slogan_hits": 0,
        "spec_hits": 0,
        "evidence_hits": 0,
        "text_excerpt": "",
        "page_type": "other",
    }

    body_text = text_in
    if ext in (".html", ".htm") or ("<html" in text_in[:500].lower()):
        p = _PageParser()
        try:
            p.feed(text_in)
        except Exception:  # noqa: BLE001
            pass
        out["title"] = re.sub(r"\s+", " ", p.title).strip()
        out["meta_description"] = p.meta_desc
        out["h1"] = p.h1
        out["headings"] = [{"level": lv, "text": t} for lv, t in p.headings[:40]]
        out["canonical"] = p.canonical
        out["images_total"] = p.images_total
        out["images_with_alt"] = p.images_with_alt
        body_text = re.sub(r"\s+", " ", " ".join(p._text_parts)).strip()
        host = urlparse(url).netloc if url else ""
        internal = 0
        for href in p.links:
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            if href.startswith("/") or (host and host in href):
                internal += 1
        out["internal_link_count"] = internal
    else:
        # markdown / plain text snapshot from alternate fetch
        m = re.search(r"^#\s+(.+)$", text_in, re.M)
        if m:
            out["title"] = m.group(1).strip()
            out["h1"] = [m.group(1).strip()]
        headings = re.findall(r"^(#{1,4})\s+(.+)$", text_in, re.M)
        out["headings"] = [{"level": len(h), "text": t.strip()} for h, t in headings[:40]]
        if not out["title"] and out["headings"]:
            out["title"] = out["headings"][0]["text"]
        body_text = re.sub(r"[#>*`\[\]\(\)]+", " ", text_in)
        body_text = re.sub(r"\s+", " ", body_text).strip()

    out["char_count"] = len(body_text)
    out["word_count"] = len(re.findall(r"[\w\u4e00-\u9fff]+", body_text))
    out["slogan_hits"] = len(SLOGAN_RE.findall(body_text))
    out["spec_hits"] = len(SPEC_RE.findall(body_text))
    out["evidence_hits"] = len(EVIDENCE_RE.findall(body_text))
    out["text_excerpt"] = body_text[:1200]
    out["page_type"] = classify_page_type(url or path, out["title"], body_text)
    # scoring v1.3 extractability / claim signals
    try:
        import geo_signals_v13 as v13
        lock = v13.detect_image_locked({**out, "content": body_text, "html": text_in if ext in (".html", ".htm") or ("<html" in text_in[:500].lower()) else ""})
        out["image_locked"] = bool(lock.get("locked"))
        out["image_locked_severity"] = lock.get("severity", 0)
        out["image_locked_reasons"] = lock.get("reasons") or []
        out["unverified_claims"] = v13.detect_unverified_claims(body_text, [])
        out["entity_address_visible"] = bool(v13.ADDRESS_TEXT_RE.search(body_text)) if hasattr(v13, "ADDRESS_TEXT_RE") else False
        # ADDRESS_TEXT_RE exported via entity helper:
        ev = v13.entity_verifiability(body_text, None)
        out["entity_address_visible"] = bool(ev.get("visible_address_text"))
        out["entity_phone_visible"] = bool(ev.get("visible_phone_text"))
    except Exception:
        out["image_locked"] = False
        out["image_locked_severity"] = 0
        out["image_locked_reasons"] = []
        out["unverified_claims"] = []
        out["entity_address_visible"] = False
        out["entity_phone_visible"] = False
    return out


def load_pages_list(run_dir: str) -> list[tuple[str, str]]:
    """Return list of (slug_or_name, url)."""
    pages_list = os.path.join(run_dir, "evidence", "pages", "pages.list")
    items = []
    if os.path.isfile(pages_list):
        for line in open(pages_list, encoding="utf-8"):
            line = line.strip()
            if not line or "|" not in line:
                continue
            slug, url = line.split("|", 1)
            items.append((slug, url))
    return items


def extract_run(run_dir: str) -> dict:
    pages_dir = os.path.join(run_dir, "evidence", "pages")
    listed = {slug: url for slug, url in load_pages_list(run_dir)}
    pages = []
    if os.path.isdir(pages_dir):
        for name in sorted(os.listdir(pages_dir)):
            if name in ("pages.list", "crawler_access.json"):
                continue
            path = os.path.join(pages_dir, name)
            if not os.path.isfile(path):
                continue
            if not re.search(r"\.(html?|md|txt)$", name, re.I):
                continue
            slug = os.path.splitext(name)[0]
            url = listed.get(slug, "")
            # also match if pages.list used different slug
            if not url:
                for s, u in listed.items():
                    if s.replace("-", "_") == slug.replace("-", "_"):
                        url = u
                        break
            pages.append(extract_file(path, url))

    site = {}
    site_path = os.path.join(run_dir, "site.json")
    if os.path.isfile(site_path):
        site = json.load(open(site_path, encoding="utf-8"))

    types = {}
    for p in pages:
        types[p["page_type"]] = types.get(p["page_type"], 0) + 1

    payload = {
        "run_dir": run_dir,
        "domain": site.get("registrable_domain") or site.get("domain") or "",
        "site_url": site.get("url") or "",
        "pages": pages,
        "page_type_counts": types,
        "pages_analyzed": len(pages),
    }
    out_path = os.path.join(run_dir, "content_extract.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def main():
    if len(sys.argv) < 2:
        print("Usage: content_extract.py <run_dir>")
        sys.exit(2)
    data = extract_run(sys.argv[1])
    print(f"Extracted {data['pages_analyzed']} pages → {sys.argv[1]}/content_extract.json")


if __name__ == "__main__":
    main()
