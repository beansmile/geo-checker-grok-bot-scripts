#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 3b: 由主模型（非百炼）完成 LLM 类规则判定 + 规则→维度评分映射，
合并进 run.json / rule_results.json，输出 llm_checks.json 与 scoring_map.json。"""
import json, os, datetime

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: json.load(open(os.path.join(ROOT,n),encoding="utf-8"))
W=lambda n,o: json.dump(o, open(os.path.join(ROOT,n),"w",encoding="utf-8"), ensure_ascii=False, indent=2)
run=L("run.json"); site=L("site.json"); results=run["rule_results"]
# 专家 reject 的规则不参与计分与 issue 输出；本轮新增规则为“补充发现”，不改变已校准分数
try:
    _ex=L("expert_review.json"); REJECTED={it["rule_id"] for it in _ex["items"] if it.get("decision")=="reject"}
except Exception: REJECTED=set()
SUPP=set(run.get("supplemental_rule_ids",[]))  # 已并入评分（calibration v2），保留记录
SEV2PRI={"S1":"critical","S2":"high","S3":"medium","S4":"low"}; PRI={"high":"高","medium":"中","low":"低","critical":"严重"}
def ev(url,locator,quote): return {"type":"quote","url":url,"locator":locator,"quote":quote[:300]}
def R(rid,verdict,sev,conf,method,evidence,zh,en,metrics=None):
    return {"rule_id":rid,"rule_domain":rid.split("-")[0],"page_id":None,"applicable":True,"verdict":verdict,
        "severity":sev,"confidence":conf,"method":method,"metrics":metrics or {},"evidence":evidence,
        "recommendation":{"zh-CN":zh,"en-US":en},"run":{"rules_version":"1.0","model":"agent-manual","tokens":None,"latency_ms":0}}
U="https://www.sofeyiahome.com"
llm=[
R("QLT-01","fail","S2","medium","LLM",[
  ev(U+"/services/","p","Massa volutpat ridiculus consectetuer euismod lobortis potenti dapibus nec risus dictumst at."),
  ev(U+"/team/","p","Lorem ipsum dolor sit amet, consectetur adipiscing elit. Ut elit tellus… (×3)"),
  ev(U+"/company-news/company-news-sofeyia-group-unveils-new-hq-in-guangzhou-cbd-marking-strategic-leap/","body","正文段落仅评论表单与页脚，缺少可核验的一手细节")],
  "重点页面缺少一手经验与作者／过程／依据，多为通用营销文案与占位文本",
  "Key pages lack first-hand experience and Who/How/Why; mostly generic boilerplate and placeholders",
  {"pages":["services","team","article_hq"]}),
R("QLT-02","fail","S2","high","LLM",[
  ev(U+"/about-us/","p","Boost productivity with imported machinery（重复 9 次）"),
  ev(U+"/services/","p","Nisi arcu auctor himenaeos sodales pulvinar praesent parturient（重复 9 次）"),
  ev(U+"/team/","p","Lorem ipsum…（重复 3 段）")],
  "存在批量重复/模板占位内容（Elementor/模板残留）与低价值索引页，可能稀释站点质量信号；建议清理或 noindex（不宜定性为 spam abuse：该术语指以操纵排名为目的的大规模造页）",
  "Bulk repeated/template placeholder content detected; treat as scaled-content-abuse risk and clean it",
  {"repeat_boost":9,"repeat_nisi":9,"team_lorem":3}),
R("QLT-03","fail","S3","medium","LLM",[
  ev(U+"/","p","World-Leading Whole-House Customization Brand / China's No.1 publicly listed customized company"),
  ev(U+"/","p","The ONLY fully integrated digital platform in the industry")],
  "存在无出处的绝对化营销表述（No.1/ONLY/World-Leading），需以可核验事实或来源支撑",
  "Unsupported superlatives (No.1/ONLY/World-Leading) need verifiable support or sources",{}),
R("ENT-06","fail","S2","medium","LLM",[
  ev(U+"/","p","Sofeyia introduced France’s Sogal brand to China 20 years ago, building on its legacy since 1981."),
  ev(U+"/about-us/","p","Introduced French brand \"Schmidt Cabinetry\"（2014）；Milanna brand issued Sofeyia brand positioning（2021）")],
  "Sofeyia/Suofeiya/Sogal/Schmidt/Milanna 之间的实体关系未声明清晰（无组织信息关联、无官方账号）",
  "Entity relationships among Sofeyia/Suofeiya/Sogal/Schmidt/Milanna are not clearly declared",{}),
R("ENT-07","fail","S2","medium","LLM",[
  ev(U+"/","p","Sofeyia introduced France’s Sogal brand to China 20 years ago"),
  ev(U+"/about-us/","p","45-year Leading in the Industry / Originated from France Since 1981 / 2001 Sofeyia Foundation"),
  ev(U+"/about-us/","p","Sustained Steady Performance in 14 Years as a Public Company")],
  "成立/引入/上市时间线互相冲突且主语不清；外部可核验主体为「索菲亚家居股份有限公司（002572.SZ）」，与站内 Sofeyia/Suofeiya 命名不一致",
  "Conflicting timeline and ambiguous subject; externally verifiable entity is Suofeiya Home Collection (002572.SZ), inconsistent with on-site naming",
  {"external_refs":["eastmoney 002572","pedaily 索菲亚上市","sfygroup.com"]}),
R("TRU-02","fail","S2","high","LLM",[
  ev(U+"/company-news/company-news-sofeyia-group-unveils-new-hq-in-guangzhou-cbd-marking-strategic-leap/","schema Person",'{"@type":"Person","name":"ehaitech"}')],
  "文章署名指向默认/建站方账号 `ehaitech`，非真实作者；无作者页与资质",
  "Article author is the default/vendor account `ehaitech`, not a real author",{}),
R("TRU-04","fail","S3","medium","LLM",[
  ev(U+"/about-us/","p","CNAS accreditation / 20 years of foreign trade experiences（均为自述，无证书链接或第三方来源）")],
  "资质/经验表述为自述，缺少可验证出处（证书、公告、第三方页面）",
  "Credentials/experience are self-asserted without verifiable references",{}),
R("TRU-05","fail","S3","medium","LLM",[
  ev(U+"/team/","p","Our Team 区域 3 段 Lorem ipsum 占位"),
  ev(U+"/about-us/","h1","About Suofeiya（与全站 Sofeyia 不一致）")],
  "About/Team 存在占位内容，未满足“真实团队信息”要求",
  "About/Team contain placeholders and zero counters, failing the real-team requirement",{}),
R("TRU-06","pass","S3","medium","LLM",[
  ev(U+"/project/","p","Penang,Malaysia:5-Star Hotel … Room Quantity: 134 / Erbil,Iraq:Apartment … Room Quantity: 745")],
  "存在带数量的一手项目案例（通过）","First-hand project cases with quantities present (pass)",{}),
R("ABS-03","fail","S3","medium","LLM",[
  ev(U+"/about-us/","p","2024 Revenue: RMB 10.494 billion / Net Profit: RMB 1.371 billion（无来源/时间标注）"),
  ev(U+"/project/","p","Room Quantity: 745（项目数据无第三方可核验来源）")],
  "关键数据缺少来源标注（对应信通院“来源可溯”），无法交叉验证",
  "Key figures lack sources (traceability), cannot be cross-verified",{}),
R("ABS-06","fail","S3","medium","LLM",[
  ev(U+"/","h1","Create. Enhance. and Sustain.（模板文案，非页面主题答案）"),
  ev(U+"/detail/alpha-pro-series/","body","产品页仅询盘 CTA，无产品参数/对比/适用场景等可回答问题")],
  "首页与产品页未就查询意图给出直接、自包含答案（对题度低）",
  "Homepage/product pages do not directly answer query intents (low alignment)",{}),
R("CIT-02","fail","S3","high","LLM",[
  ev(U+"/about-us/","p","营收/净利/分红等数字无出处链接"),
  ev(U+"/","p","Sogal since 1981 等历史声明无来源")],
  "关键数字与历史声明未标注来源，用户/AI 无法独立核验",
  "Key figures and history claims have no cited sources",{}),
R("CIT-03","fail","S2","medium","LLM",[
  ev("https://emweb.securities.eastmoney.com/CompanySurvey/Index?type=soft&code=SZ002572","external","索菲亚家居股份有限公司 002572.SZ（深交所）"),
  ev("https://www.sfygroup.com/","external","上市公司官网域名为 sfygroup.com / suofeiya.com；本站使用 sofeyiahome.com + Sofeyia/Suofeiya 混用")],
  "站外可核验的上市主体与站内品牌/域名/邮箱不一致，实体映射不清；建议在「关于我们」/「联系我们」页面明确上市主体与品牌关系并链接公告",
  "Externally verifiable listed entity differs from on-site brand/domain/email; clarify entity mapping and link disclosures",{}),
R("CLN-11","fail","S3","medium","R+LLM",[
  ev(U+"/","meta[name=generator]","Elementor 3.13.1; features: e_dom_optimization, …"),
  ev(U+"/pabriz-header/","url","pabriz-header - sofeyia（202，且在 sitemap）"),
  ev(U+"/","h1","Create. Enhance. and Sustain.（Template Kit Demo 文案）")],
  "高度疑似基于 Elementor + Hello 主题 + Pabriz 类 Template Kit 二次开发，且未清理 Demo 内容与演示页",
  "Highly likely built from Elementor + Hello + a Pabriz-like Template Kit without cleaning demo content/pages",{}),
R("ENT-08","pass","S2","medium","R+LLM",[
  ev(U+"/_privacy-policy/","body","隐私政策正文（WordPress 默认模板，但内容匹配页名）"),
  ev(U+"/_term-of-use/","body","真实条款正文；Contact/About 内容匹配")],
  "信任页内容与页名匹配（隐私页质量为模板问题，由 CLN-05 处理）",
  "Trust pages match their purpose (privacy quality is covered by CLN-05)",{}),
R("CIT-01","na","S3","high","R",[ev(U,"main content","authority outbound links = 0")],
  "正文权威外链为 0（已由 KG-04 记录，避免重复计分）","No authoritative outbound links (covered by KG-04)",{}),
R("SCH-07","fail","S2","high","R",[ev(U,"script[type=application/ld+json]","Organization contactPoint missing; emails split across sofeyiahome.com / suofeiyahome.com")],
  "组织信息缺联系方式（contactPoint），且公开邮箱域名不一致","Organization lacks contactPoint; public email domains inconsistent",{}),
R("SCH-05","pass","S3","high","R",[ev(U,"Organization.logo","HTTP 200 (image/webp)")],"logo URL 可解析","Logo URL resolves",{}),
R("CLN-07","pass","S3","high","R",[],"内容页未见软 404","No soft-404 on content pages",{}),
R("TRU-03","pass","S2","medium","R+LLM",[ev(U+"/_term-of-use/","body","real terms text")],"隐私/条款/联系页存在且可用","Privacy/terms/contact pages present",{}),
R("ABS-01","fail","S2","high","R",[ev(U+"/","p","正文缺少自包含答案块：0 段可独立成段（含事实/数据的完整回答），大量为短句/占位"),ev(U+"/services/","p","段落多为短句/拉丁占位，无法整块被 AI 引用")],
  "正文缺少可独立引用的自包含答案块（含事实/数据），AI 难以整块抽取",
  "Body lacks self-contained answer blocks with verifiable facts",
  {"self_contained_blocks":0}),
R("ABS-02","fail","S2","high","R",[ev(U+"/","p","首页抽样：定义块 1 / 数据块 0 / 对比块 0 / 步骤块 1（首页级覆盖不足，作为站点级参照）")],
  "定义/数据/对比/步骤四类证据块覆盖不足（以首页抽样为参照）",
  "Insufficient evidence-block coverage (definition/data/comparison/step; homepage sample)",{}),
R("ABS-04","fail","S3","high","R",[ev(U+"/","h1","Create. Enhance. and Sustain.（首屏无直接答案）")],
  "首屏缺少直接回答","No direct answer above the fold",{}),
R("ABS-05","pass","S3","medium","R",[ev(U+"/about-us/","lists","存在时间线/要点列表结构")],"存在可抽取列表结构","Extractable list structures present",{}),
]
merged={r["rule_id"]:r for r in results}
for r in llm: merged[r["rule_id"]]=r
all_results=sorted(merged.values(), key=lambda r:r["rule_id"])
# ---- issues 重建 ----
DIM={"ACC":"access","CLN":"quality","OGP":"ogp","SCH":"schema","ENT":"entity","ONP":"on_page","RCH":"richness","KG":"knowledge_graph","ABS":"absorption","TRU":"trust","CIT":"knowledge_graph","QLT":"quality","TEC":"on_page"}
issues=[]
for r in all_results:
    if r["verdict"]!="fail" or r["rule_id"] in REJECTED: continue
    sev=r["severity"]
    issues.append({"issue_id":r["rule_id"]+"-s1","rule_id":r["rule_id"],"rule_ids":[r["rule_id"]],"source":"llm" if r["method"]=="LLM" else "rule",
        "dimension":DIM.get(r["rule_domain"],"other"),"title":r["recommendation"],
        "description":{"zh-CN":f"命中规则 {r['rule_id']}","en-US":f"Rule {r['rule_id']} failed"},
        "recommendation":r["recommendation"],"severity":sev,"priority":SEV2PRI[sev],
        "priority_label":{"zh-CN":PRI[SEV2PRI[sev]],"en-US":SEV2PRI[sev].capitalize()},
        "priority_weight":{"S1":9,"S2":4,"S3":2,"S4":1}[sev],"impact":{"S1":40,"S2":8,"S3":5,"S4":3}[sev],
        "confidence":r["confidence"],"evidence":r["evidence"],
        "affected_urls":sorted({e["url"] for e in r["evidence"] if e.get("url","").startswith("http")})[:10],
        "code_needed":False,"code_snippet":None,"owner_role":{"zh-CN":"内容 / 品牌","en-US":"Content"}})
for i in issues: i["sort_key"]=f"{i['priority_weight']}-{i['impact']}"
issues.sort(key=lambda x:(-x["priority_weight"],-x["impact"]))
# ---- 评分映射（v2026.11 整数化口径） ----
# 全部扣分/上限/下限/惩罚均为整数，不再出现小数。
DEDUCT={
 "SCH-02":("schema",2),"SCH-04":("schema",1),"SCH-07":("schema",1),
 "ENT-01":("entity",4),"ENT-02":("entity",4),"ENT-03":("entity",1),"ENT-04":("entity",3),"ENT-05":("entity",2),"ENT-06":("entity",3),"ENT-07":("entity",3),"ENT-08":("entity",1),
 "OGP-01":("ogp",2),"OGP-02":("ogp",1),
 "RCH-01":("richness",1),"RCH-02":("richness",2),"RCH-03":("richness",2),"RCH-04":("richness",2),
 "KG-01":("knowledge_graph",2),"KG-02":("knowledge_graph",2),"KG-03":("knowledge_graph",1),"KG-04":("knowledge_graph",2),"KG-05":("knowledge_graph",1),"KG-06":("knowledge_graph",1),
 "ABS-01":("absorption",4),"ABS-02":("absorption",3),"ABS-03":("absorption",2),"ABS-04":("absorption",2),"ABS-05":("absorption",2),"ABS-06":("absorption",1),
 "TRU-01":("trust",2),"TRU-02":("trust",3),"TRU-03":("trust",2),"TRU-04":("trust",2),"TRU-05":("trust",2),"TRU-06":("trust",2),
 "ONP-01":("on_page",1),"ONP-02":("on_page",2),"ONP-03":("on_page",2),"ONP-04":("on_page",1),"ONP-05":("on_page",1),"ONP-06":("on_page",1),
 "TEC-01":("on_page",2),"TEC-03":("on_page",1),
 "QLT-01":("quality",2),"QLT-03":("quality",2),
 "CLN-04":("quality",1),"CLN-05":("trust",1),"CLN-06":("quality",1),
 # P0-3 去重：治理扣分并入维度——CLN-03（模板占位）→ 质量 -5；CLN-09（索引膨胀）→ 丰富度 -2；QLT-02 与 CLN-03 同根因已移除
 "CLN-03":("quality",5),"CLN-09":("richness",2),
 "CLN-08":("richness",1),"SCH-01":("schema",1),"SCH-10":("schema",1),
 "TRU-07":("trust",0),
}
MAX={"schema":15,"entity":15,"ogp":5,"richness":15,"knowledge_graph":10,"absorption":15,"trust":15,"on_page":5,"quality":5}
# v2026.10 口径（权重/FAQPage/信任上限），已在 2026-09-13 复评中落地：
# ① Schema 权重 20→15，实体一致性 10→15（结构化数据不是通用排名因子，实体一致性是本次最主要问题）；
# ② FAQPage 降为辅助项（Google 已于 2026-05-07 停止展示 FAQ 富结果，HowTo 于 2023 年退役；FAQPage 仍供大模型读取）→ SCH-01 移入 W 类不计分，RCH-01 降为 1 分；
# ③ 信任上限触发条件由“存在多种品牌写法”改为“未声明实体映射”（缺 sameAs / alternateName 等实体声明）。
# v2026.11 整数化：所有扣分取整数，取消比例换算（SCALE 已移除）；SCH-04/SCH-07 因与 ENT-01/ENT-02/SCH-02 重叠降为 1 分；
# 上限/下限改为绝对整数（trust ≤7、entity ≤4；entity ≥4、quality ≥1、on_page ≥2），CLN-02 惩罚 -1.5 → -1（从宽）。
# 警告/建议项：列出但不计分（真实性无法当场考证 / 品牌策略差异 / FAQPage 辅助项）
ADVISORY={"ABS-03","CIT-02","CIT-03","TRU-04","ENT-05","QLT-03","SCH-01"}
raw={k:MAX[k] for k in MAX}; applied=[]
for r in all_results:
    if r["verdict"]=="fail" and r["rule_id"] in DEDUCT and r["rule_id"] not in ADVISORY and r["rule_id"] not in REJECTED:
        dim,pts=DEDUCT[r["rule_id"]]
        raw[dim]-=pts; applied.append({"rule_id":r["rule_id"],"dimension":dim,"points":-pts})
raw_pre={k:int(v) for k,v in raw.items()}   # 约束前原始分（供口径披露）
ceiling={"applied":True,"type":"entity_mapping_undeclared","triggers":["ENT-01","ENT-02","SCH-02"],
         "reason":{"zh-CN":"未声明实体映射：品牌写法与邮箱域名不一致，且 Organization 缺少 sameAs / alternateName 等实体关联声明","en-US":"Entity mapping undeclared"},
         "caps":{"trust_max_pct":50,"entity_max_pct":30,"overall_max":70,
                  "trust_max":MAX["trust"]*50//100,"entity_max":MAX["entity"]*30//100}}
# 上限（信任上限，整数）：信任度 ≤ 7、品牌与实体 ≤ 4、总分 ≤ 70
raw["trust"]=min(raw["trust"], MAX["trust"]*50//100)
raw["entity"]=min(raw["entity"], MAX["entity"]*30//100)
# 校准下限（从宽，整数）：entity ≥4、quality ≥1、on_page ≥2
floors={"entity":4,"quality":1,"on_page":2}
for k,v in floors.items(): raw[k]=max(raw[k],v)
raw={k:max(0,int(v)) for k,v in raw.items()}
base=sum(raw.values())
# 治理扣分已并入维度扣分（P0-3 同因去重），总分＝基础分，不再单列扣分项
penalties=[]
bonus=[]; pen=0; overall=base
grade="A+" if overall>=90 else "A" if overall>=80 else "B" if overall>=70 else "C" if overall>=60 else "D"
advisory_issues=[]
for r in all_results:
    if r["verdict"]=="fail" and r["rule_id"] in ADVISORY and r["rule_id"] not in REJECTED:
        advisory_issues.append({"rule_id":r["rule_id"],"severity":"W","advisory":True,"title":r["recommendation"],
            "recommendation":r["recommendation"],"evidence":r["evidence"],"metrics":r.get("metrics",{})})
for x in run.get("extra_findings",[]):
    advisory_issues.append({"rule_id":x.get("id","EXTRA"),"severity":"W","advisory":True,
        "title":{"zh-CN":x.get("detail",""),"en-US":x.get("detail","")},
        "recommendation":{"zh-CN":x.get("detail",""),"en-US":x.get("detail","")},
        "evidence":[],"metrics":{}})
supplemental_issues=[]  # 本轮 11 条补充发现已并入评分，不再单列
scores={"category_scores":{},"overall_score":overall,"grade":grade,"scoring_status":"calibrated_v3_1_needs_signoff",
 "score_adjustments":{"base_score":base,"penalty":pen,"bonus":0,"bonus_cap":10,"adjustments":penalties+bonus},
 "trust_ceiling":ceiling,
 "template_residue":run["scores"]["template_residue"],
 "dimension_coverage":{},"advisory_count":len(advisory_issues)}
for k,m in MAX.items():
    s=raw[k]; pct=int(round(s/m*100))
    scores["category_scores"][k]={"score":s,"max":m,"percentage":pct,
        "grade":"A+" if pct>=90 else "A" if pct>=80 else "B" if pct>=70 else "C" if pct>=60 else "D","category_name":None}
run["rule_results"]=all_results; run["issues"]=issues; run["scores"]=scores; run["status"]="scoring_calibrated"
run["versions"]["methodology_version"]="v2026.10"; run["versions"]["scoring_version"]="v1.1"; run["versions"]["rules_version"]="v1.1"
run["advisory_issues"]=advisory_issues; run["supplemental_issues"]=supplemental_issues
run["promoted_rules"]=sorted({r["rule_id"] for r in all_results if r["verdict"]=="fail" and r["rule_id"] in SUPP}); run["expert_rejected"]=sorted(REJECTED)
run["updated_at"]=datetime.datetime.now().astimezone().isoformat()
run["pending_rules"]=[r for r in run["pending_rules"] if r not in {x["rule_id"] for x in all_results}]
W("run.json",run); W("rule_results.json",all_results)
W("llm_checks.json",{"prompt_version":"agent-manual-1.0","rule_results":llm,"aggregate":{"helpfulness":"fail","ai_bulk_ratio":"high","marketing_fluff_ratio":"medium"}})
W("scoring_map.json",{"status":"calibrated_v3_1","calibration_version":"v3.1","weights":MAX,"advisory":sorted(ADVISORY),"floors":floors,"deductions":applied,"penalties":penalties,"raw_dimension_scores":raw,"raw_before_ceiling":raw_pre,"max":MAX,
  "base_score":base,"overall_score":overall,"grade":grade,"trust_ceiling":ceiling})
print("llm rules:",len(llm),"| total rules:",len(all_results),"| issues:",len(issues))
print("dims:",raw,"| base:",base,"penalty:",pen,"overall:",overall,grade)
