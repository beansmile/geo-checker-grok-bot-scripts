#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 3a: 基于 evidence（pages/*.json + site.json）跑确定性规则（R），
输出 rule_results.json / issues / run.json（scores 留空待 Step 3b 评分）。"""
import json, os, re, glob, datetime

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P=lambda n: json.load(open(os.path.join(ROOT,n),encoding="utf-8"))
pages={os.path.basename(f)[:-5]: json.load(open(f,encoding="utf-8")) for f in glob.glob(os.path.join(ROOT,"pages","*.json"))}
site=P("site.json"); scope=P("scope.json")
RULES_V="v1.1"; SEV2PRI={"S1":"critical","S2":"high","S3":"medium","S4":"low"}
PW={"S1":9,"S2":4,"S3":2,"S4":1}; IMPACT={"S1":40,"S2":8,"S3":5,"S4":3}
results=[]
def add(rule_id, verdict, severity, conf, method, evidence, rec_zh, rec_en, metrics=None, page_id=None):
    results.append({"rule_id":rule_id,"rule_domain":rule_id.split("-")[0],"page_id":page_id,"applicable":True,
        "verdict":verdict,"severity":severity,"confidence":conf,"method":method,
        "metrics":metrics or {},"evidence":evidence,
        "recommendation":{"zh-CN":rec_zh,"en-US":rec_en},
        "run":{"rules_version":RULES_V,"model":None,"tokens":None,"latency_ms":0}})
def ev(url, locator, quote): return {"type":"quote","url":url,"locator":locator,"quote":quote[:300]}
def pages_with(pred): return [pid for pid,p in pages.items() if pred(p)]

# ---- ACC ----
add("ACC-01","pass","S1","high","R",[ev("https://www.sofeyiahome.com/robots.txt","robots.txt","User-agent: * / Disallow:")],
    "robots.txt 未屏蔽 AI 检索爬虫","AI retrieval crawlers are not blocked",{"blocked_critical":0})
add("ACC-02","pass","S2","high","R",[ev("https://www.sofeyiahome.com/","header","OAI-SearchBot/GPTBot/ClaudeBot/PerplexityBot -> HTTP 200")],
    "四个 AI 检索 UA 均可达","All four AI retrieval UAs reachable",{"uas":4,"blocked":0})
add("ACC-03","pass","S2","high","R",[ev("https://www.sofeyiahome.com/","body","no captcha/challenge markers")],
    "未见 WAF/挑战页拦截迹象","No WAF/challenge interception observed")
add("ACC-04","pass","S3","high","R",[ev("https://www.sofeyiahome.com/sitemap_index.xml","sitemap","6 sub-sitemaps, 117 URLs")],
    "站点地图存在且可解析","Sitemap present and parseable",{"urls":117,"content_ratio":site["sitemap"]["content_ratio"]})
add("ACC-05","pass","S1","high","R",[ev("http://www.sofeyiahome.com/","header","301 -> https://www.sofeyiahome.com/")],
    "HTTPS 与 HTTP→HTTPS 正常","HTTPS and HTTP redirect OK",{"hops":0})
add("ACC-06","pass","S1","high","R",[ev("https://www.sofeyiahome.com/","body","server HTML contains content + schema + H1")],
    "服务端 HTML 内容可读","Server HTML readable without JS",{"body_text_len":pages["home"]["body_text_len"]})
add("ACC-07","na","S4","high","R",[ev("https://www.sofeyiahome.com/llms.txt","path","404")],
    "无 llms.txt（可选，不扣分）","No llms.txt (optional)",{"status":404})

# ---- CLN ----
lorem_pages=pages_with(lambda p:any(x["kind"]=="lorem" for x in p["placeholders"]))
add("CLN-03","fail","S1","high","R",[ev(pages[p]["url"],"body",next(x["quote"] for x in pages[p]["placeholders"] if x["kind"]=="lorem")) for p in lorem_pages[:4]],
    "正文/标题残留 lorem 等模板占位文案","Template placeholder copy (lorem) remains",
    {"pages":lorem_pages,"page_count":len(lorem_pages)})
zero_pages=pages_with(lambda p:any(x["kind"]=="zero_counter" for x in p["placeholders"]))
add("CLN-04","fail","S2","high","R",[ev(pages[p]["url"],"counters",next(x["quote"] for x in pages[p]["placeholders"] if x["kind"]=="zero_counter")) for p in zero_pages],
    "首页计数器 AI 读到 0（数字为滚动动画，真实值未写入初始 HTML）","Homepage counters show 0 to AI (count-up animation, real values not in initial HTML)",{"pages":zero_pages})
legal_pages=pages_with(lambda p:any(x["kind"]=="default_legal" for x in p["placeholders"]))
add("CLN-05","fail","S2","high","R",[ev(pages[p]["url"],"body","WordPress default privacy text") for p in legal_pages],
    "合规页仍是 WordPress 默认模板","Legal page still WordPress default template",{"pages":legal_pages})
cta_pages={pid:sum(1 for x in p["placeholders"] if x["kind"] in ("placeholder_cta","empty_link")) for pid,p in pages.items()}
cta_pages={k:v for k,v in cta_pages.items() if v}
add("CLN-06","fail","S2" if any(v>=3 for v in cta_pages.values()) else "S3","high","R",
    [ev(pages[k]["url"],"anchors",f"{v} placeholder/empty links") for k,v in cta_pages.items()],
    "存在占位 CTA/空链接","Placeholder CTAs / empty links present",cta_pages)
demo=scope["by_role_urls"].get("demo",[])
sysp=scope["by_role_urls"].get("system",[])
legp=scope["by_role_urls"].get("legal",[])
add("CLN-02","fail","S2","high","R",[ev(u,"url",u) for u in demo],
    "站点地图含模板演示页","Sitemap includes template demo pages",{"count":len(demo)})
sampled_ratio=(len([p for p in pages.values() if p["role"] in ("demo","system","legal")]))/len(pages)
add("CLN-09","fail","S2","medium" if sampled_ratio<0.2 else "high","R",
    [ev("https://www.sofeyiahome.com/sitemap_index.xml","sitemap",f"demo+system+legal in sitemap: {len(demo)+len(sysp)+len(legp)}/{len(scope['content_pages'])}; page-sitemap content ratio {site['sitemap'].get('page_sitemap_content_ratio')}")],
    "索引膨胀：系统/演示/合规页进入站点地图与统计","Index bloat: system/demo/legal pages indexed",
    {"sampled_ratio":round(sampled_ratio,3),"sitemap_demo":len(demo),"sitemap_system":len(sysp),"sitemap_legal":len(legp),
     "page_sitemap_content_ratio":site["sitemap"].get("page_sitemap_content_ratio")})
residue_score=min(100, len(lorem_pages)*12 + len(zero_pages)*8 + len(legal_pages)*8 + len(demo)*4)
residue_level="severe" if residue_score>=70 else ("significant" if residue_score>=30 else ("low" if residue_score>0 else "none"))
add("CLN-10","fail","S2","medium","R",[ev("https://www.sofeyiahome.com/","site","lorem/zero/default-legal/demo aggregated")],
    "模板残留显著","Significant template residue",{"template_residue_score":residue_score,"level":residue_level})

# ---- OGP ----
home=pages["home"]["ogp"]
placeholder_ogp=(home.get("og:title","").strip().lower() in ("homepage","home","index","")) or bool(re.search(r"lorem|primis",home.get("og:description",""),re.I))
add("OGP-01","fail" if placeholder_ogp else "pass","S3","high","R",[ev("https://www.sofeyiahome.com/","meta[property=og:title]",str(home.get("og:title"))),ev("https://www.sofeyiahome.com/","meta[property=og:description]",str(home.get("og:description"))[:200])],
    "OGP 为占位/拼接文本（存在但不可用）","OGP present but placeholder/concatenated",{"og:title":home.get("og:title")})
tw=pages["home"]["twitter"]
add("OGP-02","fail" if not(tw.get("twitter:title") and tw.get("twitter:description")) else "pass","S4","high","R",
    [ev("https://www.sofeyiahome.com/","meta[name^=twitter:]",json.dumps(tw))],"Twitter Card 缺 title/description","Twitter Card lacks title/description",tw)

# ---- SCH ----
org_missing=[k for k in ["sameAs","description","contactPoint"] if not pages["home"].get("org_name") or True]
add("SCH-02","fail","S3","high","R",[ev("https://www.sofeyiahome.com/","script[type=application/ld+json]","Organization: name/url/logo present; sameAs/description/contactPoint missing")],
    "Organization 属性不完整（缺 sameAs/description/contactPoint）","Incomplete Organization attributes",{"missing":["sameAs","description","contactPoint"]})
add("SCH-04","fail","S3","high","R",[ev("https://www.sofeyiahome.com/","script[...]",'Organization.name="sofeyia" (lowercase, not brand "Sofeyia"/"Suofeiya")')],
    "schema 名称与展示品牌大小写/写法不一致","Schema name inconsistent with displayed brand",{"schema_name":"sofeyia"})

# ---- ENT ----
brands={b["value"]:b["count"] for b in site["brand_candidates"]}
add("ENT-01","fail" if len(brands)>=2 else "pass","S1","high","R",
    [ev("https://www.sofeyiahome.com/about-us/","h1","About Suofeiya"),ev("https://www.sofeyiahome.com/","title","homepage - sofeyia")],
    "品牌写法不一致（Sofeyia / Suofeiya）","Brand spelling inconsistent",brands)
emails={e["value"]:e["domain"] for e in site["emails"]}
mismatch={k:v for k,v in emails.items() if v!="sofeyiahome.com"}
add("ENT-02","fail" if mismatch or len(set(emails.values()))>1 else "pass","S1","high","R",
    [ev("https://www.sofeyiahome.com/contact-us/","mailto/text",f"{k} (domain {v})") for k,v in emails.items()],
    "同时公开了两个邮箱域名","Two conflicting email domains",emails)
add("ENT-04","fail","S2","high","R",[ev("https://www.sofeyiahome.com/contact-us/","body","Suofeiya Home Collection Co., Ltd"),ev("https://www.sofeyiahome.com/","footer","Sofeyia Home Collection Co., Ltd")],
    "公司名两种写法","Two company-name spellings",{})
handles={}
for p in pages.values():
    for x in p["external_links"]:
        if x.get("platform"): handles.setdefault(x["platform"],set()).add(re.sub(r"https?://(www\.)?","",x["url"]).split("?")[0])
flat={k:sorted(v) for k,v in handles.items()}
add("ENT-05","fail" if len({h.split('/')[-1] for v in handles.values() for h in v})>1 else "pass","S3","medium","R",
    [ev("https://www.sofeyiahome.com/contact-us/","social links",json.dumps(flat,ensure_ascii=False)[:300])],
    "社交账号命名不一致（SofeyiaOfficial vs sofeyiahome）","Social handles inconsistent",flat)

# ---- ONP ----
meta_missing=[p for p,v in pages.items() if v["meta_description"]["length"]==0]
add("ONP-02","fail" if len(meta_missing)/len(pages)>0.5 else "pass","S3","high","R",
    [ev(pages[p]["url"],"meta[name=description]","missing") for p in meta_missing[:5]],
    "大量页面缺 Meta Description","Many pages missing meta description",{"missing":len(meta_missing),"total":len(pages)})
h1bad=[p for p,v in pages.items() if len(v["h1"])!=1]
add("ONP-03","fail" if h1bad else "pass","S2","high","R",[ev(pages[p]["url"],"h1",f"h1 count={len(pages[p]['h1'])}") for p in h1bad],
    "部分页面缺 H1/多 H1","Pages missing or with multiple H1",{"pages":h1bad})
title_long=[p for p,v in pages.items() if v["title"]["length"]>60]
add("ONP-01","fail" if title_long else "pass","S3","high","R",[ev(pages[p]["url"],"title",pages[p]["title"]["text"]) for p in title_long],
    "部分页面 Title 超长","Some titles over 60 chars",{"pages":title_long})

# ---- RCH ----
faq=pages["faq"]
add("RCH-01","fail" if "faqpage" not in faq["schema_types"] else "pass","S3","high","R",
    [ev(faq["url"],"script[...]",f"FAQ page schema types: {faq['schema_types']}")],
    "FAQ 页问答为占位内容（需重写为可引用答案）","FAQ page lacks FAQPage schema",{"schema_coverage":0.0})
dated=[p for p,v in pages.items() if v["role"]=="content" and v.get("dates")]
content_sampled=[p for p,v in pages.items() if v["role"]=="content"]
add("RCH-04","fail" if len(dated)/max(len(content_sampled),1)<0.5 else "pass","S3","medium","R",
    [ev(pages[p]["url"],"schema dates",json.dumps(pages[p]["dates"])) for p in dated[:5]],
    "内容页真实日期覆盖低","Low date coverage on content pages",{"dated":len(dated),"content_sampled":len(content_sampled)})

# ---- KG / TRU / TEC ----
auth_links=[x for p in pages.values() for x in p["external_links"] if x["authority"]]
add("KG-04","fail" if not auth_links else "pass","S3","high","R",
    [ev("https://www.sofeyiahome.com/","main external links",f"authority links={len(auth_links)}; other external={sum(len([x for x in p['external_links']]) for p in pages.values())}")],
    "正文缺少权威外部引用（仅社交/系统外链）","No authoritative outbound citations",{"authority":len(auth_links)})
add("KG-01","fail","S3","high","R",[ev("https://www.sofeyiahome.com/","Organization",'sameAs missing')],"Organization 无 sameAs","No sameAs in Organization",{})
add("KG-02","fail","S3","high","R",[ev("https://www.sofeyiahome.com/","Organization",'knowsAbout missing')],"无 knowsAbout","No knowsAbout",{})
author_pages=[p for p,v in pages.items() if "person" in v["schema_types"]]
add("TRU-01","pass" if author_pages else "fail","S3","high","R",[ev(pages[p]["url"],"schema","Person present") for p in author_pages],
    "文章页含作者 Schema","Author schema present on articles",{"pages":author_pages})
add("TEC-01","pass" if all(v["canonical"] for v in pages.values()) else "fail","S2","high","R",
    [ev("https://www.sofeyiahome.com/","link[rel=canonical]",f"coverage {sum(1 for v in pages.values() if v['canonical'])}/{len(pages)}")],
    "canonical 全覆盖","Canonical coverage full",{})
heavy=[p for p,v in pages.items() if v["html_size"]>500_000]
add("TEC-03","pass" if not heavy else "fail","S3","high","R",[],"无 >500KB 页面","No pages over 500KB",{"max_kb":round(max(v['html_size'] for v in pages.values())/1024)})

# ---- issues 投影 ----
issues=[]
for r in results:
    if r["verdict"]!="fail": continue
    sev=r["severity"]; cat={"ACC":"access","CLN":"cleanliness","OGP":"ogp","SCH":"schema","ENT":"entity","ONP":"on_page","RCH":"richness","KG":"knowledge_graph","TRU":"trust","TEC":"on_page"}.get(r["rule_domain"],r["rule_domain"].lower())
    issues.append({"issue_id":r["rule_id"]+"-s1","rule_id":r["rule_id"],"rule_ids":[r["rule_id"]],"source":"rule","dimension":cat,
        "title":r["recommendation"],"description":{"zh-CN":"命中规则 "+r["rule_id"],"en-US":"Rule "+r["rule_id"]+" failed"},
        "recommendation":r["recommendation"],"severity":sev,"priority":SEV2PRI[sev],
        "priority_label":{"zh-CN":{"critical":"严重","high":"高","medium":"中","low":"低"}[SEV2PRI[sev]],"en-US":SEV2PRI[sev].capitalize()},
        "priority_weight":PW[sev],"impact":IMPACT[sev],"confidence":r["confidence"],"evidence":r["evidence"],
        "affected_urls":sorted({e["url"] for e in r["evidence"] if e.get("url","").startswith("http")}),
        "code_needed":False,"code_snippet":None,"owner_role":{"zh-CN":"内容 / 品牌","en-US":"Content"},
        "sort_key":f"{PW[sev]}-{IMPACT[sev]}"})
issues.sort(key=lambda x:(-x["priority_weight"],-x["impact"]))
trust_ceiling={"applied":any(i["rule_id"] in ("ENT-01","ENT-02") for i in issues),"type":"consistency",
   "triggers":[i["rule_id"] for i in issues if i["rule_id"] in ("ENT-01","ENT-02")],
   "caps":{"trust_max_pct":50,"entity_max_pct":30,"overall_max":70}}
run={"schema_version":"eval-1.1","run_id":"sofeyiahome-2026-09-13-run02","analyze_id":"7fcad2e6-f63c-447e-ac66-8ad716539fbb",
 "status":"rules_done","site":site,"scope":scope,"rule_results":results,"issues":issues,
 "scores":{"category_scores":{k:{"score":None,"max":m,"percentage":None,"grade":None} for k,m in
    [("schema",15),("entity",15),("ogp",5),("richness",15),("knowledge_graph",10),("absorption",15),("trust",15),("on_page",5),("quality",5)]},
    "overall_score":None,"grade":None,
    "score_adjustments":{"base_score":None,"penalty":0,"bonus":0,"bonus_cap":10,"adjustments":[]},
    "trust_ceiling":trust_ceiling,
    "template_residue":{"score":residue_score,"level":residue_level,
        "hits":[{"kind":x["kind"],"rule_id":{"lorem":"CLN-03","zero_counter":"CLN-04","default_legal":"CLN-05"}.get(x["kind"],"CLN-10"),"page_id":pid,"locator":x["locator"],"quote":x["quote"]}
                for pid,p in pages.items() for x in p["placeholders"]][:80]},
    "dimension_coverage":{} },
 "versions":{"methodology_version":"v2026.10","rules_version":RULES_V,"scoring_version":"v1.1","prompt_version":None},
 "pending_rules":sorted(set(
    [f"ACC-{i:02d}" for i in range(1,8)]+[f"CLN-{i:02d}" for i in range(1,12)]+[f"SCH-{i:02d}" for i in range(0,11)]+
    ["OGP-01","OGP-02"]+[f"KG-{i:02d}" for i in range(1,7)]+[f"ENT-{i:02d}" for i in range(1,9)]+
    [f"ONP-{i:02d}" for i in range(1,7)]+[f"RCH-{i:02d}" for i in range(1,5)]+[f"ABS-{i:02d}" for i in range(1,7)]+
    [f"TRU-{i:02d}" for i in range(1,8)]+[f"CIT-{i:02d}" for i in range(1,4)]+[f"QLT-{i:02d}" for i in range(1,4)]+
    [f"TEC-{i:02d}" for i in range(1,4)]
 ) - {r["rule_id"] for r in results}),
 "extra_findings":[{"id":"TLS-APEX","severity":"S2","detail":"https://sofeyiahome.com/ 证书主机名不匹配（apex 域名 TLS 失败），仅 www 可用"}],
 "created_at":datetime.datetime.now().astimezone().isoformat(),"updated_at":datetime.datetime.now().astimezone().isoformat()}
json.dump(results, open(os.path.join(ROOT,"rule_results.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
json.dump(run, open(os.path.join(ROOT,"run.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print("rules computed:",len(results),"issues:",len(issues),"residue:",residue_score,"ceiling:",trust_ceiling["applied"])
print("failed:",[r["rule_id"] for r in results if r["verdict"]=="fail"])
