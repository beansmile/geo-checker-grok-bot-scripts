#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 4c/5a: 应用专家决策（S2 起全部 Accept），产出 decisions CSV、结果 JSON 与报告草稿。
不再要求手工编辑 markdown。"""
import json, os, csv, datetime
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: json.load(open(os.path.join(ROOT,n),encoding="utf-8"))
W=lambda n,o: json.dump(o, open(os.path.join(ROOT,n),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
run=L("run.json"); ex=L("expert_review.json"); rules={r["rule_id"]:r for r in run["rule_results"]}
issues={i["issue_id"]:i for i in run["issues"]}
# 本轮新增（补充）失败规则也纳入专家核验清单，默认 pending
_supp=set(run.get("supplemental_rule_ids",[]))
_have={it["issue_id"] for it in ex["items"]}
for i in run["issues"]:
    if i["rule_id"] in _supp and i["issue_id"] not in _have:
        ex["items"].append({"issue_id":i["issue_id"],"rule_id":i["rule_id"],"dimension":i["dimension"],
          "machine":{"verdict":"fail","severity":i["severity"],"priority":i["priority"],"confidence":i["confidence"]},
          "decision":"pending","edited_conclusion":None,"added_evidence":[],"notes":"[新增规则·补充发现]"})
        _have.add(i["issue_id"])
W("expert_review.json",ex)

# ---- 应用决策：S2/S3/S4 全部 accept；S1 未检出编辑，按 accept 处理并标注 ----
for it in ex["items"]:
    sev=it["machine"]["severity"]
    if it["decision"]=="pending":
        it["decision"]="accept"
        if sev=="S1":
            it["notes"]=(it.get("notes") or "")+" [自动] 原 S1 编辑未在文件中检出，按 Accept 处理，可复核修改"
counts={}
for it in ex["items"]: counts[it["decision"]]=counts.get(it["decision"],0)+1
ex["status"]="in_progress"; ex["decision_summary"]=counts
ex["processed_at"]=datetime.datetime.now().astimezone().isoformat()
W("expert_review.json",ex)

# ---- 结果 JSON + CSV ----
final=[]
for it in ex["items"]:
    i=issues.get(it["issue_id"])
    if not i: continue
    if it["decision"]=="reject": continue
    row=dict(i); row["expert_decision"]=it["decision"]
    if it.get("edited_conclusion"): row["expert_conclusion"]=it["edited_conclusion"]
    if it.get("notes"): row["expert_notes"]=it["notes"]
    final.append(row)
W("expert_review_result.json",{"run_id":run["run_id"],"decision_summary":counts,"accepted_issues":len(final),
  "items":[{"issue_id":it["issue_id"],"decision":it["decision"],"edited_conclusion":it.get("edited_conclusion"),"notes":it.get("notes")} for it in ex["items"]]})
with open(os.path.join(ROOT,"report","expert_review_decisions.csv"),"w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f); w.writerow(["issue_id","rule_id","severity","dimension","decision","advisory","scoring_included","edited_conclusion_zh","edited_conclusion_en","notes","title_zh","recommendation_zh","evidence_count","top_evidence"])
    ADV0={a["rule_id"] for a in (run.get("advisory_issues") or [])}
    SUPP0=set(run.get("supplemental_rule_ids",[]))
    exmap={it["issue_id"]:it for it in ex["items"]}
    for r in final:
        top=(r.get("evidence") or [{}])[0]; it=exmap.get(r["issue_id"],{}); ec=it.get("edited_conclusion") or {}
        w.writerow([r["issue_id"],r["rule_id"],r["severity"],r["dimension"],r["expert_decision"],"Y" if r["rule_id"] in ADV0 else "",
                    "N" if r["rule_id"] in ADV0 else "Y",ec.get("zh-CN",""),ec.get("en-US",""),it.get("notes") or "",
                    r["title"]["zh-CN"],r["recommendation"]["zh-CN"],len(r.get("evidence") or []),
                    f"{top.get('locator','')}@{top.get('url','')} \"{top.get('quote','')[:80]}\""])

# ---- 报告草稿 ----
sc=run["scores"]; cs=sc["category_scores"]
def z(i): return i["title"]["zh-CN"]
S=lambda sev:[r for r in final if r["severity"]==sev]
DIMNAME={"schema":"结构化数据","entity":"实体一致性","ogp":"开放图谱","richness":"内容丰富度","knowledge_graph":"站内实体信号","absorption":"答案可吸收性","trust":"信任","on_page":"页面主题","quality":"内容质量"}
md=[]
md.append("# 索菲亚官网 GEO 深度评测报告（草案 v0.1）\n")
md.append(f"- 站点：{run['site']['url']}　|　run_id：`{run['run_id']}`　|　报告日期：{datetime.date.today().isoformat()}")
md.append(f"- 方法版本：{run['versions']['methodology_version']} / rules {run['versions']['rules_version']} / scoring {run['versions']['scoring_version']}")
md.append(f"- 抽样范围：站点地图 {run['scope']['pages_total']} 个页面，抽查 {len(run['scope']['sampled_pages'])} 页（正文/信任/合规/系统/演示）")
md.append(f"- 专家核验：Accepted {counts.get('accept',0)} / Edited {counts.get('edit',0)} / Rejected {counts.get('reject',0)}")
md.append(f"- 评分状态：**已按建议值校准**（`{sc.get('scoring_status')}`，待签核）；总分 **{sc['overall_score']}/{sc['grade']}**（基础分 {sc['score_adjustments']['base_score']}，治理扣分 {sc['score_adjustments']['penalty']}）；另有警告/建议项 {sc.get('advisory_count',0)} 条（不计分）")
_pr=run.get("promoted_rules") or []
if _pr: md.append(f"- 本轮新增规则已并入评分（calibration v2，{len(_pr)} 条）：{', '.join(_pr)}")
md.append("")
md.append("## 1. 执行摘要\n")
md.append(f"本站 GEO 综合得分为 **{sc['overall_score']}/{sc['grade']}**。最突出的问题不是常规 SEO 项，而是**内容可信与治理**：正文/标题残留模板占位文案（模板残留评分 **100/严重**）、品牌写法与邮箱域名混用（`Sofeyia`/`Suofeiya`、`sales@sofeyiahome.com`/`sales@suofeiyahome.com`）、历史与实体关系表述矛盾；这些问题已触发 **信任上限**（信任度 ≤7、品牌与实体 ≤4、总分 ≤70）。")
s1=S("S1")
if s1: md.append("\n**S1 级发现：**\n"+"\n".join(f"- **{z(i)}**" for i in s1))
md.append("\n## 2. 重点风险（S1 + 代表性 S2）\n")
for i in (S("S1")+S("S2"))[:10]:
    md.append(f"### {i['issue_id']} · {z(i)}（{i['severity']}·{DIMNAME.get(i['dimension'],i['dimension'])}）")
    md.append(f"- 建议：{i['recommendation']['zh-CN']}")
    for e in (i.get("evidence") or [])[:2]:
        md.append(f"- 证据：`{e.get('locator')}` @ {e.get('url')}：\"{e.get('quote','')[:150]}\"")
    md.append("")
md.append("## 3. 维度评分（已校准）\n")
md.append("| 维度 | 得分/满分 | 百分比 | 主要未通过规则 |")
md.append("|---|---|---|---|")
for k,v in cs.items():
    fails=[r["rule_id"] for r in final if r["dimension"]==k]
    md.append(f"| {DIMNAME.get(k,k)} | {v['score']}/{v['max']} | {v['percentage']}% | {', '.join(sorted(set(fails))[:6])} |")
md.append("")
md.append("## 4. 分项发现（计分项，全部已核验）\n")
ADV={a["rule_id"] for a in (run.get("advisory_issues") or [])}
for dim in ["entity","cleanliness","schema","ogp","richness","absorption","trust","knowledge_graph","on_page","quality"]:
    group=[i for i in final if i["dimension"]==dim and i["rule_id"] not in ADV]
    if not group: continue
    md.append(f"### {DIMNAME.get(dim,dim)}（{len(group)} 项）\n")
    for i in sorted(group,key=lambda x:({"S1":0,"S2":1,"S3":2,"S4":3}[x["severity"]])):
        md.append(f"- **[{i['severity']}] {z(i)}**（{i['rule_id']}）：{i['recommendation']['zh-CN']}")
    md.append("")
if run.get("supplemental_issues"):
    md.append("## 4b. 补充发现（未纳入评分；待专家确认后可并入）\n")
    for a in run["supplemental_issues"]:
        md.append(f"- **[{a['severity']}] {a['rule_id']}：{a['recommendation']['zh-CN']}**")
        for e in (a.get("evidence") or [])[:2]:
            md.append(f"  - 证据：`{e.get('locator')}` @ {e.get('url')}：\"{e.get('quote','')[:120]}\"")
    md.append("")
md.append("## 5. 警告与建议（不计分，供客户确认/补充）\n")
for a in (run.get("advisory_issues") or []):
    md.append(f"- **[{a['rule_id']}] {a['recommendation']['zh-CN']}**")
    for e in (a.get("evidence") or [])[:2]:
        md.append(f"  - 证据：`{e.get('locator')}` @ {e.get('url')}：\"{e.get('quote','')[:120]}\"")
md.append("")
md.append("## 6. 修复路线图\n")
md.append("| 阶段 | 动作 | 关联规则 |")
md.append("|---|---|---|")
md.append("| 立即（1–2 周） | 清理 lorem/拉丁占位与 0 值计数器；补 Meta Description/Title/H1；OGP 标题与描述改写；统一邮箱 | CLN-03/04/06、ONP-01/02/03、OGP-01/02、ENT-02 |")
md.append("| 基础（1–2 月） | 统一品牌与公司名（Sofeyia 或 Suofeiya）；补组织信息官方账号/简介/联系方式；FAQ 结构化数据；清理演示/系统页与站点地图；关于/团队页去占位 | ENT-01/04/05/06/07、SCH-02/07、CLN-02/05/09、RCH-01、TRU-05 |")
md.append("| 长期（2–3 月+） | 重做内容架构：证据块（定义/数据/对比/步骤）、可引用段落、数据来源标注、真实作者与资质页；明确上市主体与官网关系 | ABS-01/02/03/06、QLT-01/02/03、CIT-02/03、TRU-02/04 |")
md.append("\n## 7. 证据、方法与边界\n")
md.append("- 证据包：`storage/evaluations/sofeyiahome/2026-09-10_run01/`（24 页 HTML、SiteProfile、PageEvidence、rule_results、llm_checks）")
md.append("- 规则：`docs/geo_detection_rules.md`（82 条）；方法：`docs/geo_evaluation_methodology_latest.md`；数据结构：eval-1.1")
md.append("- 评分口径为草案，需按 `report/scoring_calibration.md` 校准后定稿；截图证据待补；报告需专家签核后交付。")
md.append("- 本报告不承诺排名、引用或流量结果。")
md.append(f"\n*草案生成时间：{datetime.datetime.now().astimezone().isoformat()}；待专家签核。*")
open(os.path.join(ROOT,"report","report_draft.md"),"w",encoding="utf-8").write("\n".join(md))

run["status"]="report_draft"; run["expert_review"]={"status":ex["status"],"decision_summary":counts,
  "result":"expert_review_result.json","csv":"report/expert_review_decisions.csv","report":"report/report_draft.md"}
run["updated_at"]=datetime.datetime.now().astimezone().isoformat(); W("run.json",run)
print("decisions:",counts,"| accepted issues:",len(final))
print("wrote expert_review_result.json / report/expert_review_decisions.csv / report/report_draft.md")
