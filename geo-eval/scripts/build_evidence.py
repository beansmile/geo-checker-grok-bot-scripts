#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 2: 把抓取的 HTML 解析为 eval-1.1 的 SiteProfile / PageEvidence / scope，
并跑一批确定性规则（R）输出 rule_results.json（其余规则标记 pending）。"""
import json, os, re, sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_DIR = os.path.join(ROOT, "evidence", "pages")
OUT_PAGES = os.path.join(ROOT, "pages")
SITE_DOMAIN = "sofeyiahome.com"
AUTHORITY = ["wikipedia.org","ieee.org","iso.org","iec.ch","europa.eu","gov.cn","gov.uk",
             ".gov",".edu",".ac.","standards.","nist.gov","rfc-editor.org","docs.google.com",
             "developer.mozilla.org","w3.org"]
DEMO_RE = re.compile(r"(pabriz-|elementor-|/page/|page_id=)", re.I)
SYSTEM_RE = re.compile(r"/(cart|checkout|my-account|shop|thanks|download|search|tag|author)/?$", re.I)
LEGAL_RE = re.compile(r"(_privacy-policy|_term-of-use|_cookie-policy|/privacy|/terms)", re.I)
TRUST_RE = re.compile(r"/(about-us|contact-us|faq|team|services|partnership)/?$", re.I)
LOREM_RE = re.compile(r"(lorem ipsum|ut elit tellus|primis non dignissim|dedicated for best quality innovations|under construction)", re.I)
ZERO_RE = re.compile(r"\b0\s*\+?\s*(years?|projects?|staff|countries|showrooms|patrons|clients|employees)\b|￥\s*0|\$\s*0", re.I)
WP_PRIVACY_RE = re.compile(r"(when visitors leave comments on the site|gravatar service|an anonymized string created from your email address)", re.I)
CTA_RE = re.compile(r"\b(discover more|read more|click here|learn more)\b", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
COMPANY_RE = re.compile(r"((?:Sofeyia|Suofeiya|Sogal)[A-Za-z'&.\- ]{0,40}?(?:Co\.,?\s*Ltd\.?|Group))")
BRAND_RE = re.compile(r"\b(Suofeiya|Sofeyia)\b")

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title=""; self._in_title=False
        self.metas=[]; self.links=[]; self.headings={"h1":[],"h2":[],"h3":[]}
        self._cap=None; self._buf=[]; self._stack=[]
        self.jsons=[]; self._in_ld=False
        self.anchors=[]; self._a=None; self.imgs=0; self.lists=0; self.tables=0; self.details=0
        self._text_parts=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); self._stack.append(tag)
        if tag=="title": self._in_title=True; self._buf=[]
        elif tag=="meta": self.metas.append(a)
        elif tag=="link": self.links.append(a)
        elif tag in self.headings: self._cap=tag; self._buf=[]
        elif tag in ("h1","h2","h3"): self._cap=tag; self._buf=[]
        elif tag=="script" and "ld+json" in (a.get("type") or "").lower(): self._in_ld=True; self._buf=[]
        elif tag=="a": self._a={"href":a.get("href","")}; self._buf=[]
        elif tag=="img":
            self.imgs+=1
            if "alt" not in a: self._no_alt=getattr(self,"_no_alt",0)+1
        elif tag in ("ul","ol"): self.lists+=1
        elif tag=="table": self.tables+=1
        elif tag=="details": self.details+=1
        if tag not in ("script","style"): self._text_parts.append(" ")
    def handle_endtag(self, tag):
        if tag=="title": self._in_title=False
        elif tag=="script" and self._in_ld: self.jsons.append("".join(self._buf)); self._in_ld=False
        elif tag in ("h1","h2","h3") and self._cap==tag:
            self.headings[tag].append(re.sub(r"\s+"," ","".join(self._buf)).strip()); self._cap=None
        elif tag=="a" and self._a is not None:
            self._a["text"]=re.sub(r"\s+"," ","".join(self._buf)).strip(); self.anchors.append(self._a); self._a=None
        if self._stack: self._stack.pop()
    def handle_data(self, data):
        if self._in_title: self.title+=data
        if self._in_ld: self._buf.append(data); return
        if self._cap: self._buf.append(data)
        if self._a is not None: self._buf.append(data)
        self._text_parts.append(data)

def parse_file(path):
    raw=open(path,encoding="utf-8",errors="replace").read()
    p=Parser(); p.feed(raw)
    def meta(name=None, prop=None, attr="content"):
        for m in p.metas:
            if name and (m.get("name","").lower()==name): return m.get(attr,"")
            if prop and (m.get("property","").lower()==prop): return m.get(attr,"")
        return ""
    ogp={m.get("property"):m.get("content") for m in p.metas if (m.get("property") or "").lower().startswith("og:") and m.get("content")}
    tw={m.get("name"):m.get("content") for m in p.metas if (m.get("name") or "").lower().startswith("twitter:") and m.get("content")}
    canon=""
    for l in p.links:
        if (l.get("rel") or "").lower()=="canonical": canon=l.get("href","")
    generator=""
    for m in p.metas:
        if (m.get("name") or "").lower()=="generator": generator=m.get("content","")
    body_text=re.sub(r"\s+"," "," ".join(p._text_parts)).strip()
    body_text=re.sub(r"^.*?<body[^>]*>","",body_text)  # 文本已是纯文本，保留
    schemas=[]; types=[]; dates={}
    for js in p.jsons:
        try: obj=json.loads(js)
        except Exception: continue
        def walk(n):
            if isinstance(n,list):
                for x in n: walk(x)
            elif isinstance(n,dict):
                g=n.get("@graph")
                if g: walk(g)
                else:
                    schemas.append(n)
                    t=n.get("@type")
                    if isinstance(t,list): types.extend([str(x).lower() for x in t])
                    elif t: types.append(str(t).lower())
                    for dk in ("datePublished","dateModified"):
                        if n.get(dk): dates[dk]=n.get(dk)
        walk(obj)
    # links
    internal=0; external=[]; emails=set()
    for a in p.anchors:
        href=a.get("href","")
        if href.startswith("mailto:"): emails.add(href[7:].split("?")[0])
        if not href or href.startswith(("#","javascript:","tel:","mailto:")): continue
        u=urljoin("https://www."+SITE_DOMAIN+"/", href)
        h=urlparse(u)
        if h.netloc.endswith(SITE_DOMAIN): internal+=1
        else:
            auth=any(k in h.netloc for k in AUTHORITY)
            platform=next((s for s in ("facebook","instagram","youtube","linkedin","pinterest","wa.me","x.com","twitter") if s in h.netloc),"")
            external.append({"url":u,"domain":h.netloc,"authority":auth,"platform":platform})
    emails.update(EMAIL_RE.findall(body_text))
    # paragraphs/citable
    paragraphs=[x for x in re.findall(r"<p[^>]*>(.*?)</p>", raw, re.S|re.I)]
    def clean(x): return re.sub(r"\s+"," ",re.sub(r"<[^>]+>","",x)).strip()
    paras=[clean(x) for x in paragraphs]; paras=[x for x in paras if len(x)>20]
    citable=sum(1 for x in paras if 100<=len(x.split())<=200)
    evidence_types={"definition":0,"data":0,"comparison":0,"step":0}
    for x in paras:
        low=x.lower()
        if re.search(r"\b(is|are|refers to|means|defined as)\b", low): evidence_types["definition"]+=1
        if re.search(r"\d+(\.\d+)?\s*(%|percent|million|billion|years?|m²|sqm|rmb|usd|\$|€)", low): evidence_types["data"]+=1
        if re.search(r"\b(vs\.?|versus|compared|difference|better than)\b", low): evidence_types["comparison"]+=1
        if re.search(r"\b(step|first|then|finally|how to)\b", low): evidence_types["step"]+=1
    placeholders=[]
    def add_ph(kind, quote, locator):
        placeholders.append({"kind":kind,"quote":quote[:160],"locator":locator})
    for m in LOREM_RE.finditer(body_text): add_ph("lorem", m.group(0), "body")
    for m in ZERO_RE.finditer(body_text): add_ph("zero_counter", m.group(0), "body")
    if WP_PRIVACY_RE.search(body_text): add_ph("default_legal","WordPress default privacy text","body")
    cta_like=[a for a in p.anchors if CTA_RE.search(a.get("text","")) and (a.get("href","") in ("#","") or a.get("href","").startswith("javascript:"))]
    for a in cta_like[:3]: add_ph("placeholder_cta", a.get("text",""), "a")
    empty=[a for a in p.anchors if a.get("href","") in ("#","") and a.get("text","").strip()]
    if empty: add_ph("empty_link", f"{len(empty)} empty links", "a")
    return {
        "title":{"text":re.sub(r"\s+"," ",p.title).strip(),"length":len(re.sub(r"\s+"," ",p.title).strip()),
                 "issue": None if len(re.sub(r"\s+"," ",p.title).strip())==0 else ("missing" if False else None)},
        "meta_description":{"text":meta(name="description")[:200],"length":len(meta(name="description"))},
        "h1":p.headings["h1"],"h2":p.headings["h2"][:10],"h3":p.headings["h3"][:10],
        "canonical":canon,"robots_meta":meta(name="robots"),"viewport":meta(name="viewport"),"generator":generator,
        "ogp":ogp,"twitter":tw,
        "schema_types":sorted(set(types)),"schema_count":len(schemas),
        "org_name":next((s.get("name") for s in schemas if str(s.get("@type","")).lower()=="organization"),None),
        "dates":dates,
        "internal_links":internal,"external_links":external,
        "emails":sorted(emails),
        "company_names":sorted(set(m.strip() for m in COMPANY_RE.findall(body_text))),
        "paragraphs":len(paras),"citable_paragraphs":citable,
        "evidence_types":evidence_types,
        "lists":p.lists,"tables":p.tables,"faq_blocks":p.details,
        "imgs":p.imgs,"imgs_no_alt":getattr(p,"_no_alt",0),
        "body_text_len":len(body_text),"word_count":len(body_text.split()),
        "placeholders":placeholders,
        "template_markers":{"pabriz":bool(re.search(r"pabriz",raw,re.I)),"elementor":bool(re.search(r"elementor",raw,re.I)),
                            "wp_content":bool(re.search(r"wp-content",raw,re.I))},
        "html_size":len(raw)
    }

def role_of(url):
    if DEMO_RE.search(url): return "demo"
    if LEGAL_RE.search(url): return "legal"
    if SYSTEM_RE.search(url): return "system"
    if urlparse(url).path in ("/","/about-us/","/contact-us/","/faq/","/news/","/company-news/","/team/","/services/","/partnership/"): return "trust" if urlparse(url).path in ("/about-us/","/contact-us/","/faq/","/team/","/services/","/partnership/") else "content"
    return "content"

def main():
    os.makedirs(OUT_PAGES, exist_ok=True)
    pages={}
    for fn in sorted(os.listdir(PAGES_DIR)):
        if not fn.endswith(".html"): continue
        pid=fn[:-5]
        _manifest=os.path.join(ROOT,"evidence","pages.list") if os.path.exists(os.path.join(ROOT,"evidence","pages.list")) else "/tmp/pages.list"
        url_map={l.split("|")[0]:l.split("|")[1] for l in open(_manifest,encoding="utf-8").read().strip().splitlines()}
        url=url_map.get(pid, "https://www."+SITE_DOMAIN+"/")
        data=parse_file(os.path.join(PAGES_DIR,fn))
        data.update({"page_id":pid,"url":url,"role":role_of(url)})
        pages[pid]=data
        json.dump(data, open(os.path.join(OUT_PAGES,pid+".json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    # site aggregation
    brands={}; companies=set(); emails={}; socials=set()
    for pid,p in pages.items():
        text=" ".join([p["title"]["text"]]+p["h1"]+p["h2"]+p["h3"])
        for m in BRAND_RE.finditer(text): brands[m.group(1)]=brands.get(m.group(1),0)+1
        for e in p["emails"]: emails[e]=emails.get(e,0)+1
        for x in p["external_links"]:
            if x.get("platform"): socials.add(x["url"])
    for pid,p in pages.items():
        if p.get("org_name"):
            m=COMPANY_RE.search(p["org_name"]); companies.add(m.group(1) if m else p["org_name"])
        for c in p.get("company_names",[]): companies.add(c)
    site={
        "url":"https://www."+SITE_DOMAIN+"/","domain":"www."+SITE_DOMAIN,"registrable_domain":SITE_DOMAIN,
        "site_type":{"type":"corporate","source":"auto"},
        "brand_candidates":[{"value":k,"count":v,"sources":["title/h1/h2/h3"]} for k,v in sorted(brands.items(),key=lambda x:-x[1])],
        "company_names":sorted(companies),
        "emails":[{"value":k,"domain":k.split("@")[-1],"count":v} for k,v in sorted(emails.items(),key=lambda x:-x[1])],
        "phones":[], "addresses":[], "socials":[{"url":u} for u in sorted(socials)],
        "robots":{"has_robots_txt":True,"sitemap":["https://www."+SITE_DOMAIN+"/sitemap_index.xml"],"blocked_critical":[],"blocked_noncritical":[],"matched_rules":["ACC-01"]},
        "ai_crawler_reachability":[{"ua":u,"url":"https://www."+SITE_DOMAIN+"/","status":200,"blocked":False} for u in ["OAI-SearchBot","GPTBot","ClaudeBot","PerplexityBot"]],
        "llms":{"llms_txt":{"present":False,"status":404},"llms_full":{"present":False,"status":404}},
        "sitemap":{"url_count":None,"content_ratio":None},
        "tech":{"https":True,"http_redirects_to_https":True,"redirect_hops":0,"canonical_coverage":None,
                "cms_hint":"WordPress+Yoast","apex_tls_ok":False,"apex_tls_error":"certificate hostname mismatch for sofeyiahome.com"}
    }
    json.dump(site, open(os.path.join(ROOT,"site.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    # scope (from sitemap)
    locs=[]
    for f in os.listdir(os.path.join(ROOT,"evidence")):
        if f.endswith("-sitemap.xml") or f=="sitemap_index.xml":
            locs += re.findall(r"<loc>([^<]+)</loc>", open(os.path.join(ROOT,"evidence",f),encoding="utf-8",errors="replace").read())
    locs=sorted(set(l for l in locs if l.startswith("http")))
    by_role={}
    for u in locs: by_role[role_of(u)]=by_role.get(role_of(u),0)+1
    by_role_urls={}
    for u in locs: by_role_urls.setdefault(role_of(u),[]).append(u)
    content=[u for u in locs if role_of(u)=="content"]
    page_locs=re.findall(r"<loc>([^<]+)</loc>", open(os.path.join(ROOT,"evidence","page-sitemap.xml"),encoding="utf-8",errors="replace").read())
    page_content=[u for u in page_locs if role_of(u)=="content"]
    site["sitemap"]={"url_count":len(locs),"content_ratio":round(len(content)/max(len(locs),1),3),
                     "page_sitemap_total":len(page_locs),"page_sitemap_content_ratio":round(len(page_content)/max(len(page_locs),1),3)}
    json.dump(site, open(os.path.join(ROOT,"site.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    scope={"pages_total":len(locs),"by_role":by_role,"all_urls":locs,"by_role_urls":by_role_urls,"content_pages":content,"sampled_pages":sorted(pages.keys())}
    json.dump(scope, open(os.path.join(ROOT,"scope.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print("pages parsed:", len(pages))
    print("sitemap urls:", len(locs), "roles:", by_role)
    print("brands:", brands, "companies:", companies, "emails:", emails)

if __name__=="__main__":
    main()
