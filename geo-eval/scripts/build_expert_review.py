#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 4a: 生成专家核验工作单与 ExpertReview 骨架（eval-1.1）。"""
import json, os, datetime
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: json.load(open(os.path.join(ROOT,n),encoding="utf-8"))
W=lambda n,o: json.dump(o, open(os.path.join(ROOT,n),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
run=L("run.json"); issues=run["issues"]; rules={r["rule_id"]:r for r in run["rule_results"]}; smap=L("scoring_map.json")
SEV=["S1","S2","S3","S4"]; SEVNAME={"S1":"S1 阻断/强信任问题","S2":"S2 显著影响","S3":"S3 一般优化","S4":"S4 轻微/可选"}
DIM={"schema":"结构化数据","entity":"实体一致性","ogp":"开放图谱","richness":"内容丰富度","knowledge_graph":"知识图谱","absorption":"吸收潜质","trust":"信任/E-E-A-T","on_page":"页面主题","quality":"内容质量","cleanliness":"页面清洁度"}
TITLES={
 "CLN-03":"模板占位文案残留（lorem/拉丁填充）","CLN-04":"首页计数器 AI 读到 0（数字为滚动动画）","CLN-05":"合规页为默认模板",
 "CLN-06":"占位按钮/空链接","CLN-02":"站点地图含模板演示页","CLN-09":"索引膨胀：系统/演示页可索引",
 "CLN-10":"模板残留显著（模板残留评分 100）","CLN-11":"模板来源指纹（Elementor / Hello / Pabriz 类模板）",
 "OGP-01":"开放图谱为占位/拼接文本","OGP-02":"Twitter 卡片不完整",
 "SCH-02":"组织信息属性缺失（官方账号/简介/联系方式）","SCH-04":"结构化数据名称与展示品牌不一致",
 "SCH-07":"缺联系方式（contactPoint）且邮箱域名不一致",
 "ENT-01":"品牌写法不一致（Sofeyia / Suofeiya）","ENT-02":"同时公开了两个邮箱域名",
 "ENT-04":"公司名多种写法","ENT-05":"社交账号命名不一致","ENT-06":"子品牌/代理关系不清晰",
 "ENT-07":"历史/声明时间线矛盾且主体不明","ENT-08":"信任页内容匹配（pass）",
 "ONP-01":"标题标签超长","ONP-02":"大量页面缺元描述","ONP-03":"H1 缺失/多 H1",
 "RCH-01":"FAQ 页问答为占位内容，需重写为可引用答案","RCH-04":"内容页真实日期覆盖低",
 "KG-01":"组织信息缺官方账号（sameAs）","KG-02":"缺业务范围（knowsAbout）","KG-04":"正文无权威外部引用",
 "TRU-02":"文章作者为默认/建站方账号","TRU-04":"资质/经验表述无出处","TRU-05":"关于/团队页面含占位内容",
 "ABS-01":"段落可引用率极低","ABS-02":"证据块覆盖不足","ABS-03":"关键数据无来源",
 "ABS-04":"首屏缺少直接回答","ABS-06":"页面内容与查询意图对题度低",
 "CIT-02":"声明/数字未标注来源","CIT-03":"实体映射与外部可核验主体不一致",
 "QLT-01":"缺少一手经验与作者／过程／依据","QLT-02":"批量重复/模板占位内容","QLT-03":"无出处的绝对化营销语"}
for i in issues:
    if TITLES.get(i["rule_id"]): i["title"]={"zh-CN":TITLES[i["rule_id"]],"en-US":i["rule_id"]}
W("run.json",run)

# ---- ExpertReview 骨架 ----
# 保护已有决策：若 expert_review.json 已存在，保留 decision/edited_conclusion/notes/added_evidence/reviewer
prev={}
p=os.path.join(ROOT,"expert_review.json")
if os.path.exists(p):
    try:
        old=L("expert_review.json")
        prev={it["issue_id"]:it for it in old.get("items",[])}
        old_reviewer, old_status = old.get("reviewer"), old.get("status")
    except Exception: old_reviewer, old_status = None, None
else: old_reviewer, old_status = None, None
expert={"reviewer":None,"status":"pending",
 "intake":{"client":"索菲亚 / Sofeyia Home（Sofeyiahome.com）",
   "goals":["提升官网的 AI 可读性与品牌可信度","清理模板残留与内容治理问题","明确品牌/实体关系"],
   "concerns":["品牌写法 Sofeyia vs Suofeiya","邮箱域名不一致","模板 Demo 内容残留","上市主体与官网关系表述"],
   "authorization":{"scope":"public pages only","sensitive_pages_excluded":[]},
   "questions_for_client":[
     "品牌标准写法确认为 Sofeyia 还是 Suofeiya？与上市公司主体（索菲亚家居股份有限公司 002572.SZ）的官方关系如何表述？",
     "统一邮箱应使用哪个域名（sofeyiahome.com / suofeiyahome.com / 官方域名）？",
     "是否接受在报告中点名“模板残留/演示页上线”这类发现？",
     "项目数量/营收等数字是否可提供可公开引用的来源？",
     "历史时间线（Sogal 1981 / 引入中国 20 年 / 2001 成立 / 2011 上市）哪一版为准？"]},
 "items":[],"custom_sections":[],"signoff":None,
 "machine_passed_rules":[r["rule_id"] for r in run["rule_results"] if r["verdict"]=="pass"],
 "machine_na_rules":[r["rule_id"] for r in run["rule_results"] if r["verdict"]=="na"]}
for i in issues:
    old=prev.get(i["issue_id"],{})
    expert["items"].append({"issue_id":i["issue_id"],"rule_id":i["rule_id"],"dimension":i["dimension"],
      "machine":{"verdict":"fail","severity":i["severity"],"priority":i["priority"],"confidence":i["confidence"]},
      "decision":old.get("decision","pending"),"edited_conclusion":old.get("edited_conclusion"),
      "added_evidence":old.get("added_evidence",[]),"notes":old.get("notes")})
expert["reviewer"]=old_reviewer
if old_status in ("in_progress","done"): expert["status"]=old_status
W("expert_review.json",expert)
run["status"]="expert_review"; run["expert_review"]={"status":"pending","worklist":"report/expert_review_worklist.md",
  "items":len(expert["items"]),"reviewer":None,"calibration":"report/scoring_calibration.md"}
run["updated_at"]=datetime.datetime.now().astimezone().isoformat(); W("run.json",run)

# ---- 工作单 markdown ----
md=["# 索菲亚评测 · Step 4 专家核验工作单\n",
 f"- run：`{run['run_id']}`；机器结论 {len(issues)} 条；总分草案 **{run['scores']['overall_score']}/{run['scores']['grade']}**（待核准）",
 "- 核验方式：对每条 issue 勾选 **Accept / Edit / Reject**；Edit 请填写修订结论与理由；可补充截图/链接证据。",
 "- 机器证据均可在 `evidence/` 与 `pages/` 中回溯；引用为页面原文。\n",
 "## 0. 需客户/项目确认的事项（Intake）\n"]
for q in expert["intake"]["questions_for_client"]: md.append(f"- [ ] {q}")
md.append("")
for sev in SEV:
    group=[i for i in issues if i["severity"]==sev]
    if not group: continue
    md.append(f"## {SEVNAME[sev]}（{len(group)} 条）\n")
    for i in group:
        r=rules.get(i["rule_id"],{}); 
        md.append(f"### {i['issue_id']} · {i['rule_id']} · {DIM.get(i['dimension'],i['dimension'])} · confidence={i['confidence']}")
        md.append(f"- **机器结论**：{i['title']['zh-CN']}")
        md.append(f"- **建议动作**：{i['recommendation']['zh-CN']}")
        if r.get("metrics"): md.append(f"- **指标**：`{json.dumps(r['metrics'],ensure_ascii=False)[:300]}`")
        evs=(i.get("evidence") or [])[:3]
        if evs:
            md.append("- **证据**：")
            for e in evs: md.append(f"  - `{e.get('locator')}` @ {e.get('url')}：\"{e.get('quote','')[:160]}\"")
        md.append(f"- **决策**：☐ Accept　☐ Edit　☐ Reject　｜ 修订结论：______________________________")
        md.append(f"- 备注：______________________________________________\n")
md.append("## 附：机器判定为通过/不适用（供报告引用，不必逐条核验）\n")
md.append(f"- PASS：{', '.join(expert['machine_passed_rules']) or '—'}")
md.append(f"- N/A：{', '.join(expert['machine_na_rules']) or '—'}")
open(os.path.join(ROOT,"report","expert_review_worklist.md"),"w",encoding="utf-8").write("\n".join(md))

# ---- 评分校准表 ----
cal=["# 索菲亚评测 · 评分校准表（Step 4b）\n",
 f"- 当前草案：Base **{smap['base_score']}** − 惩罚 **{abs(sum(p['points'] for p in smap['penalties']))}** = **{smap['overall_score']}/{smap['grade']}**（`draft_needs_expert_review`）",
 "- 请逐项确认扣分力度；如需调整，修改 `scoring_map.json` 的 deduction 或脚本 `merge_llm.py` 的 DEDUCT 表后重跑。\n",
 "## 1. 维度扣分明细\n","| 规则 | 维度 | 扣分 |","|---|---|---|"]
for d in smap["deductions"]: cal.append(f"| {d['rule_id']} | {d['dimension']} | {d['points']} |")
cal += ["","## 2. 惩罚项\n","| 规则 | 扣分 | 理由 |","|---|---|---|"]
for p in smap["penalties"]: cal.append(f"| {p['rule_id']} | {p['points']} | {p['reason']['zh-CN']} |")
cal += ["","## 3. 需要确认的口径（专家逐条勾选）\n",
 "- [ ] `entity` 归零（ENT-01/02/04/05/06/07 合计扣 18.5，cap 30%）是否过严？建议改为：☐ 保持 0　☐ 保留 3（cap）　☐ 其他 ______",
 "- [ ] `quality` 归零（QLT-01/02/03 + CLN-04/06）是否过严？建议改为：☐ 保持 0　☐ ≥1　☐ 其他 ______",
 "- [ ] `on_page` 归零（ONP-01/02/03 + TEC）是否合理？建议：☐ 保持 0　☐ ≥1　☐ 其他 ______",
 "- [ ] 惩罚力度：lorem −8 / 模板残留 −5 / 索引膨胀 −3 / 演示页 −2 是否合适？建议 ______",
 "- [ ] Trust Ceiling：consistency → trust ≤50%、entity ≤30%、总分 ≤70 是否合适？建议 ______",
 "- [ ] 是否将“apex 域名 TLS 证书不匹配”升级为正式规则（新 TEC-04：域名/证书一致性）？建议 ______",
 "- [ ] 是否把“拉丁占位（Massa volutpat/Nisi arcu）”纳入 CLN-03 已生效（已在规则手册补充）——确认阈值。\n",
 "## 4. 重算方式\n","```bash","python3 scripts/merge_llm.py   # 调整 DEDUCT/惩罚后重算","python3 scripts/build_summary.py","```"]
open(os.path.join(ROOT,"report","scoring_calibration.md"),"w",encoding="utf-8").write("\n".join(cal))
print("wrote report/expert_review_worklist.md, report/scoring_calibration.md, expert_review.json")
print("review items:",len(expert["items"]),"| pass:",len(expert["machine_passed_rules"]),"| na:",len(expert["machine_na_rules"]))
