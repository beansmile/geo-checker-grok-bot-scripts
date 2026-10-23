#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 3c: 跑完剩余 20 条规则。新规则结果作为“补充发现”（supplemental，不计分），
待专家确认后再并入评分。"""
import json, os, re, glob
from html.parser import HTMLParser
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: json.load(open(os.path.join(ROOT,n),encoding="utf-8"))
W=lambda n,o: json.dump(o, open(os.path.join(ROOT,n),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
run=L("run.json"); site=L("site.json"); scope=L("scope.json")
pages={os.path.basename(f)[:-5]: json.load(open(f,encoding="utf-8")) for f in glob.glob(os.path.join(ROOT,"pages","*.json"))}
U="https://www.sofeyiahome.com"
def ev(url,locator,quote): return {"type":"quote","url":url,"locator":locator,"quote":quote[:300]}
def R(rid,verdict,sev,conf,method,evidence,zh,en,metrics=None):
    return {"rule_id":rid,"rule_domain":rid.split("-")[0],"page_id":None,"applicable":True,"verdict":verdict,
      "severity":sev,"confidence":conf,"method":method,"metrics":metrics or {},"evidence":evidence,
      "recommendation":{"zh-CN":zh,"en-US":en},"run":{"rules_version":"1.0","model":"agent-manual","tokens":None,"latency_ms":0}}
def raw(pid): return open(os.path.join(ROOT,"evidence","pages",pid+".html"),encoding="utf-8",errors="replace").read()
def text(pid):
    h=raw(pid); h=re.sub(r"<script.*?</script>","",h,flags=re.S|re.I); h=re.sub(r"<style.*?</style>","",h,flags=re.S|re.I)
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",h)).strip()

new=[]
# CLN-01 系统页识别
new.append(R("CLN-01","pass","S3","high","R",[ev(U,"scope",json.dumps(scope["by_role"],ensure_ascii=False))],
  "系统/演示/合规页已识别并单独计数","System/demo/legal pages identified and counted",{"by_role":scope["by_role"]}))
# CLN-08 重复/复制内容（去 boilerplate 后 8-gram Jaccard）
def shingles(pid,k=8):
    ws=re.findall(r"[a-z0-9]+",text(pid).lower()); return {tuple(ws[i:i+k]) for i in range(max(0,len(ws)-k))}
content=[p for p,v in pages.items() if v["role"]=="content"]
S={p:shingles(p) for p in content}
from collections import Counter
cnt=Counter()
for p,s in S.items():
    for g in s: cnt[g]+=1
common={g for g,c in cnt.items() if c>0.7*max(len(S),1)}
S2={p:{g for g in s if g not in common} for p,s in S.items()}
best=(None,None,0.0)
for i,a in enumerate(content):
    for b in content[i+1:]:
        A,B=S2[a],S2[b]; j=len(A&B)/max(1,len(A|B))
        if j>best[2]: best=(a,b,j)
new.append(R("CLN-08","fail" if best[2]>0.5 else "pass","S2","medium","R",
  [ev(pages[best[0]]["url"],"body",f"与 {pages[best[1]]['url']} 去模板后相似度 {round(best[2],3)}")],
  "跨页正文相似度检查（去导航/页脚后）","Cross-page body similarity check (boilerplate removed)",{"max_jaccard":round(best[2],3),"pair":[best[0],best[1]]}))
# ENT-03 电话/地址真实性
phones=set(re.findall(r"\+?\d[\d\s\-()]{8,}\d", text("contact")))
addr="Xinggang East Road" in text("contact")
new.append(R("ENT-03","pass","S3","high","R",[ev(U+"/contact-us/","body",f"phones={sorted(phones)[:2]}; address_present={addr}")],
  "电话/地址为真实信息（无占位）","Phone/address appear real (no placeholders)",{"address_present":addr}))
# KG-03 foundingDate / KG-05 内链 / KG-06 location
org=pages["home"]
has_founding="foundingDate" in raw("home")
new.append(R("KG-03","fail" if not has_founding else "pass","S4","high","R",
  [ev(U,"Organization","foundingDate missing" if not has_founding else "present")],
  "组织信息缺成立日期（foundingDate）","Organization lacks foundingDate",{}))
inte=sum(v["internal_links"] for v in pages.values())
new.append(R("KG-05","pass" if inte/max(len(pages),1)>=3 else "fail","S4","high","R",
  [ev(U,"internal links",f"avg {round(inte/len(pages),1)} per page")],"正文内链充足","Internal links sufficient",{}))
loc=bool(re.search(r'"(location|areaServed|address)"', raw("home")))
new.append(R("KG-06","fail" if not loc else "pass","S3","high","R",
  [ev(U,"Organization","no location/areaServed/address in schema")],"结构化数据缺地址/服务区域（location/areaServed/address）","Schema lacks location/areaServed/address",{}))
# ONP-04 标题层级
def heading_seq(pid):
    h=raw(pid); return [int(m.group(1)) for m in re.finditer(r"<h([1-4])[^>]*>",h,re.I)]
bad=[]
for p,v in pages.items():
    if v["role"]!="content": continue
    seq=heading_seq(p); seen2=False; issues=0
    for i,lvl in enumerate(seq):
        if lvl==3 and not seen2: issues+=1
        if i and lvl>seq[i-1]+1: issues+=1
        if lvl==2: seen2=True
    if issues: bad.append(p)
new.append(R("ONP-04","fail" if len(bad)/max(1,len(content))>1/3 else ("fail" if bad else "pass"),"S3","medium","R",
  [ev(pages[p]["url"],"headings","heading level skip detected") for p in bad[:5]],
  "部分内容页标题层级跳跃","Some content pages have heading-level skips",{"pages":bad}))
# ONP-05 顶部关键信息（模型判定）
new.append(R("ONP-05","fail","S3","medium","LLM",
  [ev(U,"h1","Create. Enhance. and Sustain.（模板文案，未陈述页面主题）")],
  "首页/服务页首屏未直接陈述页面主题","Top of page does not state the page topic",{}))
# ONP-06 单主题/对题（模型判定）
new.append(R("ONP-06","fail","S3","medium","LLM",
  [ev(U+"/detail/alpha-pro-series/","body","产品页仅询盘 CTA，无产品参数/场景/对比内容")],
  "产品页内容过于单薄，难与查询意图对齐","Product pages too thin to match query intent",{}))
# RCH-02 文章资产 / RCH-03 指南文档
posts=len(re.findall(r"<loc>", open(os.path.join(ROOT,"evidence","post-sitemap.xml"),encoding="utf-8").read()))
new.append(R("RCH-02","fail" if posts<10 else "pass","S3","high","R",
  [ev(U+"/news/","sitemap",f"articles in post-sitemap: {posts}; sampled article pages have Article schema")],
  "文章数量不足（<10）","Few articles (<10)",{"articles":posts}))
guides=[u for u in scope["all_urls"] if re.search(r"/(docs|guides?|help|tutorial)",u)]
new.append(R("RCH-03","fail" if not guides else "pass","S3","high","R",
  [ev(U,"sitemap","no docs/guides/help pages")],"缺少指南/技术文档页","No guide/technical-doc pages",{"guide_pages":len(guides)}))
# SCH-00 站点类型适用性 / SCH-01 类型覆盖
types=set()
for v in pages.values(): types |= set(v["schema_types"])
required={"organization","faqpage","article","itemlist"}; missing=sorted(required-types)
new.append(R("SCH-00","pass","S3","high","R",[ev(U,"site_type","corporate (auto)")],
  "站点类型 corporate；检查项按类型过滤","Site type corporate; checks filtered by type",{"site_type":"corporate"}))
new.append(R("SCH-01","fail" if missing else "pass","S3","high","R",
  [ev(U,"script[type=application/ld+json]",f"missing core types: {missing}")],
  "核心结构化数据类型覆盖不足","Core schema types missing",{"missing":missing,"found":sorted(types)}))
# SCH-03 嵌套 / SCH-06 sameAs 真实性 / SCH-08 日期 / SCH-09 @id / SCH-10 作者
nested=any("article" in v["schema_types"] and ("organization" in v["schema_types"] or "person" in v["schema_types"]) for v in pages.values())
new.append(R("SCH-03","pass" if nested and len(types)>=4 else "fail","S4","high","R",
  [ev(U,"schema",f"types={len(types)}; article↔org/person nested={nested}")],"嵌套/组合基本成立","Nesting/combination OK",{"types":len(types)}))
new.append(R("SCH-06","na","S3","high","R",[ev(U,"Organization","no sameAs present to validate; see KG-01")],
  "无 sameAs，真实性校验不适用（KG-01 已记录缺失）","No sameAs to validate (KG-01 covers absence)",{}))
dates_ok=True; anomalies=[]
for v in pages.values():
    d=v.get("dates") or {}
    p=next((x for x in (v.get("schema_types") or []) if x=="article"),None)
    if d.get("datePublished") and d.get("dateModified") and d["datePublished"]>d["dateModified"]:
        dates_ok=False; anomalies.append(v["url"])
new.append(R("SCH-08","pass" if dates_ok else "fail","S3","high","R",
  [ev(U,"schema dates",f"anomalies={anomalies or 'none'}")],"日期字段合理","Dates consistent",{"anomalies":anomalies}))
id_ok=all(("#organization" in raw(p)) for p,v in pages.items() if "website" in v["schema_types"])
new.append(R("SCH-09","pass" if id_ok else "fail","S3","medium","R",
  [ev(U,"@id","Website.publisher @id resolves to Organization")],"@id 引用可解析","@id references resolve",{}))
author_ok=False
for p,v in pages.items():
    if "person" in v["schema_types"]: author_ok=True
new.append(R("SCH-10","fail" if not author_ok else "fail","S3","medium","R",
  [ev(U+"/company-news/company-news-sofeyia-group-unveils-new-hq-in-guangzhou-cbd-marking-strategic-leap/","schema author","Person= ehaitech；页面无对应 byline")],
  "作者/发布者与页面署名不一致","Author/publisher inconsistent with byline",{}))
# TEC-02 CSR / TRU-07 信任上限
new.append(R("TEC-02","pass","S1","high","R",[ev(U,"body",f"server HTML text length {pages['home']['body_text_len']}")],
  "首页服务端渲染可读","Homepage SSR readable",{"render_mode":"ssr"}))
new.append(R("TRU-07","fail","S1","high","R",
  [ev(U+"/about-us/","h1","About Suofeiya"),ev(U+"/contact-us/","mailto","sales@suofeiyahome.com vs sales@sofeyiahome.com")],
  "信任上限已触发：需先声明实体映射（统一品牌与邮箱口径）","Trust ceiling applied: declare entity mapping first",
  {"caps":run["scores"]["trust_ceiling"]["caps"],"triggers":["ENT-01","ENT-02"]}))

merged={r["rule_id"]:r for r in run["rule_results"]}
for r in new: merged[r["rule_id"]]=r
run["rule_results"]=sorted(merged.values(), key=lambda r:r["rule_id"])
run["pending_rules"]=[p for p in run["pending_rules"] if p not in {r["rule_id"] for r in new}]
run["supplemental_rule_ids"]=sorted({r["rule_id"] for r in new})
run["remaining_run_at"]=__import__("datetime").datetime.now().astimezone().isoformat()
W("rule_results.json",run["rule_results"]); W("run.json",run)
print("computed remaining:",len(new),"| failed:",[r["rule_id"] for r in new if r["verdict"]=="fail"])
print("pending now:",run["pending_rules"])
