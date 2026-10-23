#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户版 v2.0：官方正式风格（设计规范见 .impeccable.md）。
长文可读性优先 → 排版/层级 → 数据可视化 → 精致度；沿用产品 Indigo 色板与 Geist 字族。
输出 report/sofeyia_geo_report_for_client_v3.1_long.html（长文版）。"""
import os, sys, json, html, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_report_client as B   # 复用证据样本 / 代码示例 / 文案（会同时刷新 v1.1）
ROOT=B.ROOT; run=B.run; site=B.site; scope=B.scope; sc=B.sc; cs=B.cs
issues=B.issues; ADV=B.ADV; S=B.S; CODE=B.CODE; NARR=B.NARR; IMPROVE=B.IMPROVE
CLIENT_FIX=B.CLIENT_FIX; strengths=B.strengths; actions=B.actions; dim_issues=B.dim_issues
date=datetime.date.today().isoformat()
def E(x): return html.escape(str(x if x is not None else ""))
SEV={"S1":("danger","严重"),"S2":("warning","高"),"S3":("info","中"),"S4":("muted","低")}
GRADE_VAR={"A+":"success","A":"success","B":"info","C":"warning","D":"danger"}
sevc={s:sum(1 for i in issues if i["severity"]==s) for s in ("S1","S2","S3","S4")}
total=sum(sevc.values()) or 1
DIMS=[("schema","结构化数据"),("entity","品牌与实体一致性"),("ogp","开放图谱与分享"),("richness","内容覆盖与新鲜度"),
      ("knowledge_graph","站内实体信号"),("absorption","答案可吸收性"),("trust","信任度"),
      ("on_page","页面主题与元数据"),("quality","内容质量")]
# ---------- 数据可视化 ----------
def score_meter():
    zones=[("D",0,59,"danger"),("C",60,69,"warning"),("B",70,79,"info"),("A",80,89,"success"),("A+",90,100,"success")]
    segs="".join(f'<span class="z z-{k}" style="left:{a}%;width:{b-a}%"></span>' for _,a,b,k in zones)
    marks="".join(f'<span class="zl" style="left:{(a+b)/2}%">{g}</span>' for g,a,b,_ in zones)
    return f'''<div class="meter" role="img" aria-label="站内准备度 {sc["overall_score"]} 分，等级 {E(sc["grade"])}">
  <div class="track">{segs}<span class="marker" style="left:{sc["overall_score"]}%"><i></i><b>{sc["overall_score"]}</b></span></div>
  <div class="zlabels">{marks}</div><div class="meter-ends"><span>0</span><span>100</span></div></div>'''
def sev_bar():
    order=[("S1","danger","严重"),("S2","warning","高"),("S3","info","中"),("S4","muted","低")]
    segs="".join(f'<span class="sb sb-{k}" style="width:{sevc[s]/total*100:.1f}%" title="{lab}: {sevc[s]}"></span>' for s,k,lab in order)
    legend="".join(f'<span><i class="dot d-{k}"></i>{lab} <b>{sevc[s]}</b></span>' for s,k,lab in order)
    return f'<div class="sevbar"><div class="sb-track">{segs}</div><div class="sb-legend">{legend}<span class="muted">共 {total} 项</span></div></div>'
def dim_chart():
    rows=""
    for k,name in DIMS:
        v=cs[k]; pctv=v["percentage"]; space=100-pctv
        rows+=f'''<div class="lc-row"><div class="lc-name">{E(name)}</div>
        <div class="lc-track"><span class="lc-fill" style="width:{pctv}%;background:var(--{GRADE_VAR[v["grade"]]})"></span><span class="lc-space" style="width:{space}%"></span></div>
        <div class="lc-val"><b>{v["score"]}</b><span>/{v["max"]}</span><em class="g g-{GRADE_VAR[v["grade"]]}">{E(v["grade"])}</em></div></div>'''
    return f'<figure class="chart" role="img" aria-label="九个维度的得分与提升空间"><div class="lc">{rows}</div><figcaption>深色为当前得分，浅色为该维度剩余提升空间；每条为各维度自身满分（15 / 10 / 5）。</figcaption></figure>'
def scope_bar():
    order=[("content","正文页","primary"),("trust","信任页","info"),("demo","模板演示页","warning"),("system","系统页","muted"),("legal","合规页","success")]
    tot=scope["pages_total"]
    segs=""; leg=""
    for key,label,col in order:
        n=scope["by_role"].get(key,0)
        segs+=f'<span class="sb sb-{col}" style="width:{n/tot*100:.1f}%" title="{label}: {n}"></span>'
        leg+=f'<span><i class="dot d-{col}"></i>{label} <b>{n}</b></span>'
    return f'<div class="sevbar"><div class="sb-track">{segs}</div><div class="sb-legend">{leg}<span class="muted">共 {tot} 个页面</span></div></div>'
# ---------- 组件 ----------
def finding(i, idx):
    smp=S.get(i["rule_id"]) or []; code=CODE.get(i["rule_id"])
    fix=CLIENT_FIX.get(i["rule_id"]) or i["recommendation"]["zh-CN"]
    ev="".join(f'<li><code>{E(e.get("url"))}</code><span>{E(e.get("quote"))}</span></li>' for e in (i.get("evidence") or [])[:2])
    smp_html=('<div class="ev"><div class="ev-label">问题内容</div><ul>'+"".join(f'<li><code>{E(u)}</code><span>{E(t)}</span></li>' for u,t in smp)+'</ul></div>') if smp else ""
    code_html=(f'<details class="code"><summary><span>修复示例</span><em>仅供参考，请替换占位信息</em></summary><div class="codewrap"><div class="codebar">HTML</div><pre>{E(code[0])}</pre></div></details>') if code else ""
    src_html=(f'<details class="src"><summary>检测来源</summary><ul>{ev}</ul></details>') if ev else ""
    extra_html=(f'<div class="sub">建议的实体映射</div>{B.EXTRA[i["rule_id"]]}') if i["rule_id"] in B.EXTRA else ""
    return f'''<article class="finding"><header>
      <span class="fnum">{idx:02d}</span><span class="sev sev-{SEV[i["severity"]][0]}">{SEV[i["severity"]][1]}</span>
      <h4>{E(i["title"]["zh-CN"])}</h4></header>
      <p class="fix">{E(fix)}</p>{smp_html}{extra_html}{code_html}{src_html}</article>'''
def dim_section(idx,k,name):
    v=cs[k]; items=dim_issues(k); gv=GRADE_VAR[v["grade"]]
    body="".join(finding(i,n+1) for n,i in enumerate(items))
    return f'''<section class="chapter dim">
  <header class="chap-head"><span class="chap-num">{idx:02d}</span>
    <h3>{E(name)}</h3>
    <div class="chap-score"><b class="c-{gv}">{v["score"]}</b><span>/{v["max"]}</span><em class="g g-{gv}">{E(v["grade"])}</em>
      <div class="mini"><i style="width:{v["percentage"]}%;background:var(--{gv})"></i></div></div></header>
  <p class="prose">{E(NARR[k])}</p>
  {('<div class="sub">主要发现</div>'+body) if body else ''}
  <div class="callout"><b>提升建议</b><p>{E(IMPROVE[k])}</p></div></section>'''
chap1=("01","总体评价"); chap2=("02","表现良好的部分"); chap3=("03","关键发现"); chap4=("04","分维度评估"); chap5=("05","优先改进建议"); chap6=("06","检测范围")
CSS='''
:root{
 --primary:#4F46E5;--primary-hover:#4338CA;--primary-light:#EEF2FF;--primary-dim:rgba(79,70,229,.08);
 --bg:#F1F4F9;--surface:#FFFFFF;--surface-2:#F8FAFC;--surface-3:#E8EEF5;--border:#E2E8F0;--border-2:#CBD5E1;
 --text:#0F172A;--text-2:#475569;--text-3:#5E6C7F;
 --success:#15803D;--warning:#D97706;--danger:#DC2626;--info:#0284C7;--muted:#64748B;
 --font-sans:Geist,"Geist Sans",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
 --font-mono:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 --space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:24px;--space-6:32px;--space-7:48px;--space-8:64px;--space-9:96px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
h1,h2,h3,h4{font-weight:650}
::selection{background:var(--primary-light)}
pre::selection,pre *::selection,code::selection,.codebar::selection{background:#475569;color:#fff}
a:focus-visible,summary:focus-visible{outline:2px solid var(--primary);outline-offset:2px;border-radius:3px}
.toc a{color:inherit;border-bottom:0}.toc a:hover{color:var(--primary)}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-sans);font-size:16px;line-height:1.78;
 letter-spacing:-.003em;-webkit-font-smoothing:antialiased}
.sheet{max-width:900px;margin:0 auto;background:var(--surface);padding:var(--space-8) var(--space-8) var(--space-9);
 box-shadow:0 1px 2px rgba(15,23,42,.04),0 24px 60px -40px rgba(15,23,42,.25)}
.mono,code,pre,.lc-val,.chip,.fnum{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
a{color:var(--primary);text-decoration:none;border-bottom:1px solid color-mix(in oklab,var(--primary) 30%,transparent)}
a:hover{border-bottom-color:var(--primary)}
/* ---------- cover ---------- */
.cover{padding-bottom:var(--space-7);border-bottom:2px solid var(--text)}
.kicker{font-size:11.5px;letter-spacing:.22em;text-transform:uppercase;color:var(--primary);font-weight:600}
.cover h1{font-size:clamp(30px,5vw,44px);line-height:1.22;letter-spacing:-.02em;margin:var(--space-4) 0 var(--space-2)}
.cover .sub{font-size:19px;color:var(--text-2);margin:0 0 var(--space-6)}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:var(--space-4) var(--space-6);
 padding:var(--space-5) 0;border-top:1px solid var(--border)}
.facts dt{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--text-3);margin-bottom:4px}
.facts dd{margin:0;font-size:15px}
.scorepanel{display:grid;grid-template-columns:auto 1fr;gap:var(--space-6);align-items:center;padding:var(--space-5) 0 0;border-top:1px solid var(--border)}
.bigscore{font-size:76px;line-height:.9;letter-spacing:-.04em;font-weight:700;color:var(--danger)}
.bigscore small{font-size:22px;color:var(--text-3);font-weight:500;letter-spacing:0}
.bigscore em{display:block;font-style:normal;font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--text-3);margin-top:6px}
/* meter */
.meter{margin-top:var(--space-3)}.track{position:relative;height:14px;background:var(--surface-3);border-radius:2px;overflow:visible}
.track .z{position:absolute;top:0;bottom:0;opacity:.5}
.z-danger{background:color-mix(in oklab,var(--danger) 22%,#fff)}.z-warning{background:color-mix(in oklab,var(--warning) 22%,#fff)}
.z-info{background:color-mix(in oklab,var(--info) 18%,#fff)}.z-success{background:color-mix(in oklab,var(--success) 18%,#fff)}
.marker{position:absolute;top:-10px;transform:translateX(-50%);text-align:center}
.marker i{display:block;width:2px;height:34px;background:var(--text)}
.marker b{position:absolute;top:-26px;left:50%;transform:translateX(-50%);font-size:18px;font-weight:700}
.zlabels{position:relative;height:18px;margin-top:6px}.zl{position:absolute;transform:translateX(-50%);font-size:11px;color:var(--text-3);letter-spacing:.08em}
.meter-ends{display:flex;justify-content:space-between;font-size:11px;color:var(--text-3);margin-top:2px}
/* stacked bars */
.sevbar{margin-top:var(--space-3)}.sb-track{display:flex;height:12px;border-radius:2px;overflow:hidden;background:var(--surface-3)}
.sb{display:block;height:100%}
.sb-danger{background:var(--danger)}.sb-warning{background:var(--warning)}.sb-info{background:var(--info)}.sb-muted{background:var(--muted)}.sb-primary{background:var(--primary)}.sb-success{background:var(--success)}
.sb-legend{display:flex;flex-wrap:wrap;gap:var(--space-4);margin-top:var(--space-2);font-size:12.5px;color:var(--text-2)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.d-danger{background:var(--danger)}.d-warning{background:var(--warning)}.d-info{background:var(--info)}.d-muted{background:var(--muted)}.d-primary{background:var(--primary)}.d-success{background:var(--success)}
.muted{color:var(--text-3)}
/* toc */
.toc{margin:var(--space-7) 0 0}
.toc h2{font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--text-3);margin:0 0 var(--space-3)}
.toc ol{list-style:none;margin:0;padding:0;border-top:1px solid var(--border)}
.toc li{display:flex;gap:var(--space-4);align-items:baseline;padding:10px 0;border-bottom:1px solid var(--border);font-size:15px}
.toc .n{font-size:12px;color:var(--text-3);min-width:22px}
.toc .dots{flex:1;border-bottom:1px dotted var(--border-2);transform:translateY(-4px)}
/* chapters */
.chapter{margin-top:var(--space-9)}
.chap-head{display:flex;align-items:baseline;gap:var(--space-3);border-bottom:2px solid var(--text);padding-bottom:var(--space-3)}
.chap-num{font-size:13px;color:var(--text-3);letter-spacing:.1em}
.chap-head h2{font-size:26px;letter-spacing:-.015em;margin:0;flex:1}
.chap-head h3{font-size:21px;letter-spacing:-.01em;margin:0;flex:1}
.chap-score{display:flex;align-items:baseline;gap:3px;flex-wrap:wrap;justify-content:flex-end;min-width:170px}
.chap-score b{font-size:28px}.chap-score span{color:var(--text-3);font-size:14px}
.g{font-style:normal;font-size:11.5px;letter-spacing:.08em;border:1px solid currentColor;border-radius:3px;padding:0 5px;margin-left:6px}
.g-success{color:var(--success)}.g-info{color:var(--info)}.g-warning{color:var(--warning)}.g-danger{color:var(--danger)}
.c-success{color:var(--success)}.c-info{color:var(--info)}.c-warning{color:var(--warning)}.c-danger{color:var(--danger)}
.mini{margin-top:6px;height:3px;background:var(--surface-3);width:100%;flex-basis:100%}
.mini i{display:block;height:100%}
.prose{max-width:68ch;color:var(--text-2);margin:var(--space-5) 0 0;font-size:16.5px}
.prose strong,.fix strong{color:var(--text)}
.lead{font-size:19px;line-height:1.75;color:var(--text);max-width:66ch}
.sub{margin:var(--space-6) 0 var(--space-3);font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--text-3)}
/* findings */
.finding{border-top:1px solid var(--border);padding:var(--space-5) 0}
.finding header{display:flex;align-items:baseline;gap:var(--space-3);flex-wrap:wrap}
.fnum{font-size:12px;color:var(--text-3)}
.sev{font-size:11px;letter-spacing:.1em;padding:1px 6px;border-radius:3px;color:#fff}
.sev-danger{background:var(--danger)}.sev-warning{background:var(--warning)}.sev-info{background:var(--info)}.sev-muted{background:var(--muted)}
.finding h4{margin:0;font-size:18.5px;letter-spacing:-.012em;line-height:1.45}
.fix{margin:var(--space-2) 0 var(--space-3);color:var(--text-2);max-width:70ch}
.ev{background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:var(--space-3) var(--space-4);margin:var(--space-3) 0}
.ev-label{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--text-3);margin-bottom:var(--space-2)}
.ev ul{margin:0;padding:0;list-style:none}
.ev li{display:grid;grid-template-columns:1fr;gap:2px;padding:6px 0;border-top:1px dotted var(--border)}
.ev li:first-child{border-top:0}
.ev code{font-size:12px;color:var(--primary)}
.ev span{font-size:14.5px;color:var(--text)}
details summary{cursor:pointer;list-style:none;font-size:13.5px;color:var(--primary);display:flex;gap:var(--space-3);align-items:baseline}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"▸";font-size:12px;color:var(--text-3)}
details[open] summary::before{content:"▾"}
details summary em{font-style:normal;color:var(--text-3);font-size:12.5px}
details.src ul{margin:var(--space-2) 0 0;padding-left:var(--space-5);font-size:13.5px;color:var(--text-2)}
.codewrap{margin:var(--space-3) 0 var(--space-4);border:1px solid #1E293B;border-radius:6px;overflow:hidden}
.codebar{background:#1E293B;color:#CBD5E1;font-size:11px;letter-spacing:.14em;text-transform:uppercase;padding:7px 14px}
pre{margin:0;background:#0F172A;color:#E2E8F0;padding:var(--space-4);overflow:auto;font-size:12.8px;line-height:1.7;white-space:pre-wrap}
.callout{background:var(--primary-light);border:1px solid color-mix(in oklab,var(--primary) 22%,#fff);border-radius:6px;padding:var(--space-4) var(--space-5);margin-top:var(--space-5)}
.callout b{display:block;font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--primary-hover);margin-bottom:4px}
.callout p{margin:0;color:var(--text);max-width:70ch}
/* lists */
ul.plain{list-style:none;margin:var(--space-4) 0 0;padding:0;max-width:74ch}
ul.plain li{position:relative;padding:8px 0 8px 26px;border-top:1px solid var(--border);color:var(--text-2)}
ul.plain li::before{content:"";position:absolute;left:4px;top:16px;width:7px;height:7px;border-radius:50%;background:var(--success)}
/* action list */
.actions{margin-top:var(--space-5);border-top:2px solid var(--text)}
.arow{display:grid;grid-template-columns:minmax(180px,1.1fr) 2.4fr auto;gap:var(--space-5);padding:var(--space-4) 0;border-bottom:1px solid var(--border);align-items:start}
.arow h4{margin:0;font-size:16px}
.arow p{margin:0;color:var(--text-2);font-size:14.5px}
.gain{font-size:14px;color:var(--success);font-weight:700;white-space:nowrap;text-align:right}
.note{color:var(--text-3);font-size:13px;margin-top:var(--space-3)}
/* chart */
.chart{margin:var(--space-6) 0 0}
.lc{display:grid;gap:10px}
.lc-row{display:grid;grid-template-columns:150px 1fr 92px;gap:var(--space-4);align-items:center}
.lc-name{font-size:14px;color:var(--text-2);text-align:right}
.lc-track{display:flex;height:10px;background:var(--surface-3);border-radius:2px;overflow:hidden}
.lc-fill{display:block;height:100%}.lc-space{display:block;height:100%;background:repeating-linear-gradient(90deg,transparent 0 3px,color-mix(in oklab,var(--border-2) 55%,transparent) 3px 5px)}
.lc-val{font-size:13.5px;color:var(--text-3)}.lc-val b{font-size:15px;color:var(--text)}
figcaption{margin-top:var(--space-4);font-size:13px;color:var(--text-3);max-width:70ch}
footer.doc{margin-top:var(--space-9);padding-top:var(--space-5);border-top:1px solid var(--border);color:var(--text-3);font-size:12.5px;display:flex;justify-content:space-between;gap:var(--space-4);flex-wrap:wrap}
@media (max-width:760px){.sheet{padding:var(--space-6) var(--space-5) var(--space-8)}.lc-row{grid-template-columns:96px 1fr 78px}.lc-name{font-size:12.5px}.arow{grid-template-columns:1fr}}
@media print{
 @page{size:A4;margin:16mm 14mm}
 body{background:#fff}.sheet{box-shadow:none;max-width:none;padding:0}
 .chapter,.cover{break-before:page}.toc{break-after:page}
 .finding,.arow,.ev,.callout,.chart{break-inside:avoid}
 p,li{orphans:3;widows:3}
 details{display:block}details>summary{display:none}details.code,details.src{display:block}
 pre{white-space:pre-wrap;font-size:11px}
}
@media (prefers-reduced-motion:no-preference){
 .cover .kicker,.cover h1,.cover .sub{animation:rise .5s cubic-bezier(.16,1,.3,1) both}
 .cover h1{animation-delay:.06s}.cover .sub{animation-delay:.12s}
 @keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
}
'''
# 关键发现 top10
top=[i for i in issues if i["severity"] in ("S1","S2")][:10]
findings_html="".join(finding(i,n+1) for n,i in enumerate(top))
dims_html="".join(dim_section(n+1,k,name) for n,(k,name) in enumerate(DIMS))
toc_items="".join(f'<li><span class="n">{n}</span><a href="#{sid}">{E(t)}</a><span class="dots"></span></li>' for n,t,sid in
  [("01","总体评价","s1"),("02","表现良好的部分","s2"),("03","关键发现","s3"),("04","分维度评估","s4"),("05","优先改进建议","s5"),("06","检测范围","s6")])
actions_html="".join(f'<div class="arow"><div><h4>{E(a)}</h4><p>{E(b)}</p></div><span class="cycle">{E(d)} · {E(e)}</span></div>' for a,b,c,d,e in actions)
HTML=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>索菲亚官网 GEO 评测报告</title>
<style>{CSS}</style></head><body><main class="sheet">
<header class="cover">
  <div class="kicker">生成式引擎优化 · 技术与内容准备度评测报告</div>
  <h1>索菲亚官网 GEO 评测报告</h1>
  <p class="sub">站内准备度：面向生成式搜索的可理解性、可信度与内容可引用性评估</p>
  <dl class="facts">
    <div><dt>站点</dt><dd class="mono">{E(site["url"])}</dd></div>
    <div><dt>报告日期</dt><dd class="mono">{date}</dd></div>
    <div><dt>检测范围</dt><dd>{scope["pages_total"]} 个 URL · 深度检测 {len(scope["sampled_pages"])} 页</dd></div>
    <div><dt>方法版本</dt><dd class="mono">{E(run["versions"]["methodology_version"])} · rules {E(run["versions"]["rules_version"])}</dd></div>
  </dl>
  <div class="scorepanel">
    <div><div class="bigscore">{sc["overall_score"]}<small>/100</small><em>站内准备度 {E(sc["grade"])}</em></div></div>
    <div>{score_meter()}
      <p class="prose" style="margin-top:14px;font-size:14px">分数由 9 个维度相加得出（维度合计 {sc["score_adjustments"]["base_score"]} 分，扣除内容治理扣分 {abs(sc["score_adjustments"]["penalty"])} 分）。因未声明实体映射（品牌写法与邮箱域名不一致且缺少 sameAs / alternateName 等声明），信任度与品牌与实体维度受评分上限约束。</p>
    </div>
  </div>
  <div style="margin-top:var(--space-5)">{sev_bar()}</div>
</header>

<nav class="toc"><h2>目录</h2><ol>{toc_items}</ol></nav>

<section class="chapter" id="s1"><header class="chap-head"><span class="chap-num">01</span><h2>总体评价</h2></header>
<p class="lead">本站 <strong>GEO 站内准备度为 {sc["overall_score"]} 分（{E(sc["grade"])}）</strong>。网站在技术基础与信息架构上具备良好起点，但在品牌与实体一致性、内容可信度、结构化数据完整性三方面存在明显短板，是当前影响 AI 搜索表现的主要因素。</p>
<p class="prose">本次高优先级问题共 {sevc["S1"]} 项，集中在两处：品牌写法与邮箱域名混用（Sofeyia / Suofeiya、两个邮箱域名），以及页面中残留的模板占位文案与演示内容。这两类问题会直接影响 AI 与搜索引擎对“品牌是谁、内容是否可信”的判断，进而降低被正确引用的概率。</p>
<p class="prose">本报告采用新版检测口径，在原有“信号是否存在”的基础上增加了“内容是否正确、建议是否可用”的判定，因此分数与旧版报告不可直接比较。分数衡量的是网站在生成式搜索中被正确理解、信任与引用的准备度，而非排名或流量结果。</p>
</section>

<section class="chapter" id="s2"><header class="chap-head"><span class="chap-num">02</span><h2>表现良好的部分</h2></header>
<ul class="plain">{"".join(f"<li>{E(s)}</li>" for s in strengths)}</ul></section>

<section class="chapter" id="s3"><header class="chap-head"><span class="chap-num">03</span><h2>关键发现</h2></header>
<p class="prose">以下为本轮评估中最需要优先处理的问题，按影响程度排序。每条给出问题内容原文与修复示例（示例仅供参考，请替换占位信息）。</p>
{findings_html}</section>

<section class="chapter" id="s4"><header class="chap-head"><span class="chap-num">04</span><h2>分维度评估</h2></header>
<p class="prose">共 9 个维度，满分 100 分。下图为各维度当前得分与剩余提升空间，其后逐维给出解读、主要发现与提升建议。</p>
{dim_chart()}
{dims_html}</section>

<section class="chapter" id="s5"><header class="chap-head"><span class="chap-num">05</span><h2>优先改进建议</h2></header>
<p class="prose">按优先级排列的行动建议。“可恢复空间”＝该维度满分 − 当前得分（或已计入总分的治理扣分），可从上文维度表逐项核对；各项不叠加，总分以 100 分为上限。</p>
<div class="actions">{actions_html}</div>
<p class="note">说明：以上建议按“先解决可信与一致性问题、再补结构化与内容深度”的顺序排列；其中品牌与实体统一是解除评分上限的关键前置项。</p></section>

<section class="chapter" id="s6"><header class="chap-head"><span class="chap-num">06</span><h2>检测范围</h2></header>
<p class="prose">域名 <span class="mono">{E(site["domain"])}</span> 共发现 {scope["pages_total"]} 个 URL；本次深度检测 {len(scope["sampled_pages"])} 页，覆盖首页、关于、联系、FAQ、新闻与文章、产品、项目、条款以及模板演示与系统页。页面构成如下：</p>
{scope_bar()}
<p class="prose">另有 {len(run.get("advisory_issues",[]))} 项“需确认或补充的信息”（如数据来源、资质出处、社交账号策略等）已单独整理，供贵司核对，不影响本报告评分。</p></section>

<footer class="doc"><span>索菲亚官网 GEO 评测报告 · {date}</span><span class="mono">run {E(run["run_id"])}</span></footer>
</main></body></html>'''
open(os.path.join(ROOT,"report","sofeyia_geo_report_for_client_v3.1_long.html"),"w",encoding="utf-8").write(HTML)
r=json.load(open(os.path.join(ROOT,"run.json"),encoding="utf-8"))
r.setdefault("report_refs",{})["client_official_html"]="report/sofeyia_geo_report_for_client_v3.1_long.html"
json.dump(r,open(os.path.join(ROOT,"run.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("wrote report/sofeyia_geo_report_for_client_v3.1_long.html",len(HTML),"chars")
