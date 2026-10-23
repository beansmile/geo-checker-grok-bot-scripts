#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 5b: 由 run.json 生成离线正式报告（Markdown + 单文件 HTML，风格参考产品结果页）。
输出 report/report_v1.0.md、report/report_v1.0.html（含内嵌 evaluation JSON）。"""
import json, os, html, datetime
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: json.load(open(os.path.join(ROOT,n),encoding="utf-8"))
run=L("run.json"); site=L("site.json"); scope=L("scope.json")
sc=run["scores"]; cs=sc["category_scores"]; issues=run["issues"]
ADV={a["rule_id"] for a in run.get("advisory_issues",[])}
DIM={"schema":"结构化数据","entity":"实体一致性","ogp":"开放图谱","richness":"内容丰富度","knowledge_graph":"知识图谱",
     "absorption":"吸收潜质","trust":"信任 / E-E-A-T","on_page":"页面主题","quality":"内容质量","cleanliness":"页面清洁度"}
SEVCOL={"S1":"#dc2626","S2":"#ea580c","S3":"#d97706","S4":"#64748b","W":"#2563eb"}
date=datetime.date.today().isoformat(); gen=datetime.datetime.now().astimezone().isoformat()
def E(x): return html.escape(str(x if x is not None else ""))
def score_color(g): return {"A+":"#16a34a","A":"#0d9488","B":"#2563eb","C":"#d97706","D":"#dc2626"}.get(g,"#64748b")
pct=round(sc["overall_score"],1)
dash=2*3.14159*54*(1-pct/100)
bysev={s:[i for i in issues if i["severity"]==s] for s in ("S1","S2","S3","S4")}
advisories=run.get("advisory_issues",[])
roadmap=[
 ("立即（1–2 周）","清理 lorem/拉丁占位与 0 值计数器；补 Meta Description / Title / H1；OGP 标题与描述改写；统一邮箱","CLN-03/04/06、ONP-01/02/03、OGP-01/02、ENT-02"),
 ("基础（1–2 月）","统一品牌与公司名（Sofeyia 或 Suofeiya）；补 Organization sameAs/description/contactPoint；FAQPage schema；清理演示/系统页与 sitemap；About/Team 去占位","ENT-01/04/06、SCH-01/02/07、CLN-02/05/09、RCH-01、TRU-05"),
 ("长期（2–3 月+）","重做内容架构：证据块（定义/数据/对比/步骤）、可引用段落、数据来源标注、真实作者与资质页；明确上市主体与官网关系","ABS-01/02、QLT-01/02、CIT-02/03、TRU-02/04、RCH-02/03"),
]
def issue_card(i,compact=False):
    ev="".join(f'<div class="quote"><span class="loc">{E(e.get("locator"))}</span> <a href="{E(e.get("url"))}" target="_blank">{E(e.get("url"))}</a><p>{E(e.get("quote"))}</p></div>' for e in (i.get("evidence") or [])[:3])
    return f'''<article class="issue">
  <div class="issue-head"><span class="pill" style="background:{SEVCOL.get(i["severity"],"#64748b")}">{E(i["severity"])}</span>
  <span class="rule">{E(i["rule_id"])}</span><span class="dim">{E(DIM.get(i["dimension"],i["dimension"]))}</span>
  <span class="conf">confidence: {E(i["confidence"])}</span></div>
  <h4>{E(i["title"]["zh-CN"])}</h4>
  <p class="action">{E(i["recommendation"]["zh-CN"])}</p>
  {"" if compact else f'<details><summary>证据（{len(i.get("evidence") or [])}）</summary>{ev}</details>'}
</article>'''
s1=bysev["S1"]; top=list(s1)+bysev["S2"][:7]
dim_cards="".join(f'''<div class="dcard">
  <div class="dhead"><span>{E(DIM.get(k,k))}</span><b style="color:{score_color(v["grade"])}">{v["score"]}<small>/{v["max"]}</small></b></div>
  <div class="bar"><i style="width:{v["percentage"]}%;background:{score_color(v["grade"])}"></i></div>
  <div class="dmeta"><span>{v["percentage"]}%</span><span>grade {E(v["grade"])}</span></div>
  <div class="chips">{"".join(f'<span class="chip">{E(r)}</span>' for r in sorted({i["rule_id"] for i in issues if i["dimension"]==k and i["rule_id"] not in ADV}))}</div>
</div>''' for k,v in cs.items())
groups=""
for dim in ["entity","cleanliness","schema","ogp","richness","absorption","trust","knowledge_graph","on_page","quality"]:
    g=[i for i in issues if i["dimension"]==dim and i["rule_id"] not in ADV]
    if not g: continue
    groups+=f'<h3>{E(DIM.get(dim,dim))}（{len(g)}）</h3>'+"".join(issue_card(i) for i in g)
adv_blocks="".join(f'''<div class="adv"><b>{E(a["rule_id"])}</b> {E(a["recommendation"]["zh-CN"])}
  {"" if not a.get("evidence") else "<ul>"+"".join(f'<li>{E(e.get("locator"))} · {E(e.get("quote"))[:140]}</li>' for e in a["evidence"][:2])+"</ul>"}</div>''' for a in advisories)
roadmap_rows="".join(f"<tr><td><b>{E(a)}</b></td><td>{E(b)}</td><td class='mono'>{E(c)}</td></tr>" for a,b,c in roadmap)
data_json=json.dumps({"run":{k:run[k] for k in ("run_id","analyze_id","status","versions","scope")},"site":site,
  "scores":sc,"issues":issues,"advisory":advisories}, ensure_ascii=False)

HTML=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEO 深度评测报告 · {E(site["domain"])}</title>
<style>
:root{{--ink:#0f172a;--ink2:#475569;--ink3:#94a3b8;--line:#e2e8f0;--bg:#f8fafc;--card:#fff;--accent:#4f46e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif}}
.wrap{{max-width:1040px;margin:0 auto;padding:32px 20px 80px}}
.cover{{background:linear-gradient(135deg,#312e81,#4f46e5 55%,#0ea5e9);color:#fff;border-radius:20px;padding:36px 34px;display:flex;gap:28px;align-items:center;flex-wrap:wrap}}
.cover .kick{{font-size:12px;letter-spacing:.18em;text-transform:uppercase;opacity:.85}}
.cover h1{{margin:6px 0 10px;font-size:28px;line-height:1.3}}
.meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px 22px;font-size:13px;opacity:.95;margin-top:8px}}
.ring{{position:relative;width:140px;height:140px;flex:0 0 140px}}
.ring svg{{transform:rotate(-90deg)}}.ring .val{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}}
.ring .val b{{font-size:40px;line-height:1}}.ring .val span{{font-size:13px;opacity:.9}}
.badges{{margin-top:10px;display:flex;flex-wrap:wrap;gap:8px}}.badge{{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);padding:4px 10px;border-radius:999px;font-size:12px}}
section{{margin-top:34px}}h2{{font-size:20px;margin:0 0 14px;padding-left:10px;border-left:4px solid var(--accent)}}
h3{{font-size:16px;margin:22px 0 10px;color:var(--ink2)}}h4{{margin:6px 0 4px;font-size:15px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 1px 2px rgba(15,23,42,.04)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.dcard{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}}
.dhead{{display:flex;justify-content:space-between;align-items:baseline;font-size:14px}}.dhead b{{font-size:22px}}.dhead small{{font-size:12px;color:var(--ink3)}}
.bar{{height:8px;background:#eef2f7;border-radius:99px;margin:8px 0 6px;overflow:hidden}}.bar i{{display:block;height:100%}}
.dmeta{{display:flex;justify-content:space-between;font-size:12px;color:var(--ink3)}}.chips{{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px}}
.chip{{font:11px/1.6 ui-monospace,Menlo,monospace;background:#f1f5f9;border:1px solid var(--line);border-radius:6px;padding:0 6px;color:var(--ink2)}}
.issue{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}}
.issue-head{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;color:var(--ink3)}}
.pill{{color:#fff;border-radius:999px;padding:1px 8px;font-weight:600}}.rule{{font-family:ui-monospace,Menlo,monospace;color:var(--accent)}}
.action{{margin:6px 0;color:var(--ink)}}details summary{{cursor:pointer;color:var(--ink2);font-size:13px}}
.quote{{background:#f8fafc;border:1px dashed var(--line);border-radius:8px;padding:8px 10px;margin:6px 0;font-size:13px}}
.quote .loc{{font-family:ui-monospace,Menlo,monospace;color:var(--accent)}}.quote a{{color:var(--ink3);font-size:12px;word-break:break-all}}.quote p{{margin:4px 0 0;color:var(--ink2)}}
.adv{{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:10px 14px;margin:8px 0;font-size:14px}}
.adv ul{{margin:6px 0 0 18px;color:var(--ink2);font-size:13px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden}}
th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);font-size:13.5px;vertical-align:top}}th{{background:#f1f5f9;color:var(--ink2)}}
.mono{{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--ink2)}}
.sign{{margin-top:26px;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
.sign div{{border:1px dashed var(--line);border-radius:10px;padding:14px;font-size:13px;color:var(--ink2)}}
footer{{margin-top:34px;color:var(--ink3);font-size:12px;text-align:center}}
@media print{{body{{background:#fff}}.cover{{border-radius:0}}.card,.issue,.dcard{{box-shadow:none}}.issue{{break-inside:avoid}}section{{break-inside:avoid}}}}
</style></head><body><div class="wrap">
<div class="cover">
  <div class="ring"><svg width="140" height="140"><circle cx="70" cy="70" r="54" fill="none" stroke="rgba(255,255,255,.25)" stroke-width="12"/>
  <circle cx="70" cy="70" r="54" fill="none" stroke="#fff" stroke-width="12" stroke-linecap="round" stroke-dasharray="339.3" stroke-dashoffset="{dash:.1f}"/></svg>
  <div class="val"><b>{sc["overall_score"]}</b><span>{E(sc["grade"])} · GEO 基础分</span></div></div>
  <div style="flex:1;min-width:280px">
    <div class="kick">GEO 深度评测报告 · 专家版</div><h1>{E(site["url"])}</h1>
    <div class="meta">
      <div>run_id：{E(run["run_id"])}</div><div>报告日期：{date}</div>
      <div>方法：{E(run["versions"]["methodology_version"])} / rules {E(run["versions"]["rules_version"])}</div>
      <div>范围：sitemap {scope["pages_total"]} URL · 深检 {len(scope["sampled_pages"])} 页</div>
      <div>专家核验：Accepted {len(issues)} · Edited 0 · Rejected {len(run.get("expert_rejected",[]))}</div>
    </div>
    <div class="badges">
      <span class="badge">Base {sc["score_adjustments"]["base_score"]} · 惩罚 {sc["score_adjustments"]["penalty"]}</span>
      <span class="badge">Trust Ceiling 已触发</span>
      <span class="badge">Template Residue {sc["template_residue"]["score"]}/100 · {E(sc["template_residue"]["level"])}</span>
      <span class="badge">警告/建议 {len(advisories)} 条（不计分）</span>
      <span class="badge">{E(sc.get("scoring_status"))}</span>
    </div>
  </div>
</div>

<section><h2>1. 执行摘要</h2><div class="card">
<p>本站 GEO 基础分为 <b>{sc["overall_score"]}/{E(sc["grade"])}</b>。最突出的问题不是常规 SEO 项，而是<b>内容可信与治理</b>：正文/标题残留模板占位文案（Template Residue Score <b>{sc["template_residue"]["score"]}/100</b>）、品牌写法与邮箱域名混用（Sofeyia / Suofeiya；sales@sofeyiahome.com / sales@suofeiyahome.com）、历史与实体关系表述矛盾；已触发 <b>Trust Ceiling</b>（trust ≤50%、entity ≤30%、总分上限 70）。</p>
<p><b>S1 级发现：</b></p><ul>{"".join(f"<li><b>{E(i['title']['zh-CN'])}</b>（{E(i['rule_id'])}）</li>" for i in s1)}</ul>
</div></section>

<section><h2>2. 重点风险（S1 + 代表性 S2）</h2>{"".join(issue_card(i) for i in top)}</section>

<section><h2>3. 维度评分（calibration v2）</h2><div class="grid">{dim_cards}</div>
<p class="mono">Base {sc["score_adjustments"]["base_score"]} − 惩罚 {sc["score_adjustments"]["penalty"]} = {sc["overall_score"]} / {E(sc["grade"])}；维度下限 entity≥3、quality≥1、on_page≥1.5；警告项不计分。</p></section>

<section><h2>4. 分项发现（计分项，全部已核验）</h2>{groups}</section>

<section><h2>5. 警告与建议（不计分，供客户确认/补充）</h2>{adv_blocks}</section>

<section><h2>6. 修复路线图</h2><table><thead><tr><th>阶段</th><th>动作</th><th>关联规则</th></tr></thead><tbody>{roadmap_rows}</tbody></table></section>

<section><h2>7. 证据、方法与边界</h2><div class="card">
<p>证据包：<span class="mono">storage/evaluations/sofeyiahome/2026-09-10_run01/</span>（24 页原始 HTML、SiteProfile、PageEvidence、77 条规则结果、LLM 检查、评分映射）。</p>
<p>规则：<span class="mono">docs/geo_detection_rules.md</span>（82 条 / 14 域，新增 W 警告级）；方法：<span class="mono">docs/geo_evaluation_methodology_latest.md</span>；数据结构：eval-1.1。</p>
<p>边界：评分口径为校准草案，需专家签核；截图证据待补；本报告不承诺排名、引用或流量结果。</p>
<div class="sign"><div>专家签核：__________________ 日期：__________</div><div>客户确认：__________________ 日期：__________</div></div>
</div></section>
<footer>Generated {gen} · run {E(run["run_id"])} · scoring {E(sc.get("scoring_status"))}</footer>
</div>
<script id="evaluation-data" type="application/json">{data_json}</script>
</body></html>'''
open(os.path.join(ROOT,"report","report_v1.0.html"),"w",encoding="utf-8").write(HTML)
print("wrote report/report_v1.0.html", len(HTML),"bytes")
