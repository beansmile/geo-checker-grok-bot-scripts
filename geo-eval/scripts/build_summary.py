#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 2/3a 摘要：读取 site.json / scope.json / run.json / pages/*.json，输出 report/evidence_summary.md"""
import json, os, glob
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: json.load(open(os.path.join(ROOT,n),encoding="utf-8"))
site=L("site.json"); scope=L("scope.json"); run=L("run.json")
pages={os.path.basename(f)[:-5]: json.load(open(f,encoding="utf-8")) for f in glob.glob(os.path.join(ROOT,"pages","*.json"))}
issues=run["issues"]; bysev={s:[i["rule_id"] for i in issues if i["severity"]==s] for s in ("S1","S2","S3","S4")}
gen=pages["home"].get("generator") or "n/a"
missing_meta=[p for p,v in pages.items() if v["meta_description"]["length"]==0]
h1bad=[p for p,v in pages.items() if len(v["h1"])!=1]
auth=sum(1 for p in pages.values() for x in p["external_links"] if x["authority"])

md=[]
md.append("# 索菲亚评测证据包摘要（Step 2 / 3）\n")
md.append(f"- run_id：`{run['run_id']}`；analyze_id：`{run['analyze_id']}`")
md.append(f"- 站点：{site['url']}（{site['site_type']['type']}，{site['tech']['cms_hint']}）")
md.append(f"- sitemap：{site['sitemap']['url_count']} URL（content ratio {site['sitemap']['content_ratio']}）；page-sitemap {site['sitemap']['page_sitemap_total']} URL（content ratio {site['sitemap']['page_sitemap_content_ratio']}）")
md.append(f"- 抽样页：{len(pages)}（content/trust/legal/system/demo 均有覆盖）")
md.append(f"- 规则：已跑 {len(run['rule_results'])} 条（确定性 33 + LLM/补充 24），待跑 {len(run['pending_rules'])} 条；issues {len(issues)} 条")
md.append(f"- 模板残留：score **{run['scores']['template_residue']['score']}**（{run['scores']['template_residue']['level']}）")
md.append(f"- Trust Ceiling：**{'已触发' if run['scores']['trust_ceiling']['applied'] else '未触发'}**（triggers: {', '.join(run['scores']['trust_ceiling']['triggers'])}；caps {run['scores']['trust_ceiling']['caps']}）\n")

md.append("## 一、站点级事实\n")
md.append("| 项 | 证据 |")
md.append("|---|---|")
md.append(f"| CMS/插件 | generator=`{gen}`；robots 为 Yoast 生成；模板标记 elementor={pages['home']['template_markers']['elementor']}，pabriz={pages['home']['template_markers']['pabriz']} |")
md.append(f"| AI 爬虫 | robots 未屏蔽；OAI-SearchBot/GPTBot/ClaudeBot/PerplexityBot 实抓均 **200** |")
md.append(f"| llms.txt | `/llms.txt`、`/llms-full.txt` 均 **404**（可选，不扣分） |")
md.append(f"| HTTPS | http://www → 301 https；主链 0 跳；**apex `sofeyiahome.com` 证书主机名不匹配（TLS 失败）** |")
md.append(f"| 品牌写法 | `Sofeyia`（{dict((b['value'],b['count']) for b in site['brand_candidates'])['Sofeyia']} 次）/ `Suofeiya`（{dict((b['value'],b['count']) for b in site['brand_candidates'])['Suofeiya']} 次） |")
md.append(f"| 公司名 | {', '.join(site['company_names'])} |")
md.append(f"| 邮箱 | {', '.join(e['value']+'('+e['domain']+')' for e in site['emails'])} |")
md.append(f"| 社交 | {len(site['socials'])} 个（Facebook `SofeyiaOfficial` vs 其它 `sofeyiahome`） |")
md.append(f"| Schema | Organization.name=`sofeyia`（小写）；**缺 sameAs / description / contactPoint** |")
md.append(f"| OGP | og:title=`homepage`（占位）；og:description 含 lorem/整页拼接；twitter 仅 card |")
md.append(f"| 站点级链接 | 正文权威外链 **{auth}** 条（其余为社交/系统链接） |\n")

md.append("## 二、页面级覆盖（抽样 24 页）\n")
md.append(f"- Meta Description 缺失：**{len(missing_meta)}/24**")
md.append(f"- H1 数量 ≠1：**{len(h1bad)}/24**（{', '.join(h1bad)}）")
md.append(f"- canonical 覆盖：**{sum(1 for v in pages.values() if v['canonical'])}/24**")
md.append(f"- 可引用段落（100–200 词）：**0**（首页 13 段/About 31 段均为短句或占位）")
md.append(f"- 模板残留页：lorem 类 {len([p for p,v in pages.items() if any(x['kind']=='lorem' for x in v['placeholders'])])}，0 值计数器 {len([p for p,v in pages.items() if any(x['kind']=='zero_counter' for x in v['placeholders'])])}，默认合规模板 {len([p for p,v in pages.items() if any(x['kind']=='default_legal' for x in v['placeholders'])])}")
md.append(f"- FAQ 页 schema：{pages['faq']['schema_types']}（**无 FAQPage**）")
md.append(f"- sitemap 中的演示/系统/合规页：demo {scope['by_role'].get('demo',0)}、system {scope['by_role'].get('system',0)}、legal {scope['by_role'].get('legal',0)}（共 {scope['by_role'].get('demo',0)+scope['by_role'].get('system',0)+scope['by_role'].get('legal',0)}/{scope['pages_total']}）\n")

md.append("## 三、确定性规则结果（首轮）\n")
md.append("| 严重度 | 规则 |")
md.append("|---|---|")
for s in ("S1","S2","S3","S4"):
    if bysev[s]: md.append(f"| {s} | {', '.join(bysev[s])} |")
md.append("")
md.append("## 三b、维度分（草案，待专家校准）\n")
sc=run["scores"]; cs=sc["category_scores"]
md.append("| 维度 | 得分/满分 |")
md.append("|---|---|")
for k,v in cs.items(): md.append(f"| {k} | {v['score']}/{v['max']}（{v['percentage']}%）|")
md.append(f"| **Base 合计** | **{sc['score_adjustments']['base_score']}** |")
md.append(f"| 惩罚 | {sc['score_adjustments']['penalty']}（lorem -8 / 模板残留 -5 / 索引膨胀 -3 / 演示页 -2） |")
md.append(f"| **总分** | **{sc['overall_score']} / {sc['grade']}**（scoring_status={sc.get('scoring_status')}） |\n")
md.append("代表性证据：")
for rid in ("CLN-03","ENT-01","ENT-02","CLN-04","CLN-05","CLN-02","SCH-02","OGP-01","RCH-01","KG-04"):
    r=next((x for x in run["rule_results"] if x["rule_id"]==rid and x["verdict"]=="fail"), None)
    if r and r["evidence"]:
        e=r["evidence"][0]; md.append(f"- **{rid}**：{e.get('quote','')[:140]}（{e.get('locator')} @ {e.get('url')}）")
md.append("\n## 四、状态与后续\n")
md.append(f"- 规则进度：已跑 **{len(run['rule_results'])}** 条（确定性 33 + LLM/补充 24），待跑 **{len(run['pending_rules'])}** 条（{'、'.join(run['pending_rules'][:12])} 等）")
md.append(f"- 评分状态：`{run['scores'].get('scoring_status')}`（总分 {run['scores']['overall_score']}/{run['scores']['grade']}；警告/建议项 {run['scores'].get('advisory_count',0)} 条不计分）")
md.append("- 截图证据未采集（当前环境无浏览器）：建议专家评测阶段用 Playwright 或人工补图")
md.append("- 后续：Step 4 专家逐条核验（Accept/Edit/Reject + 客户定制结论）→ Step 5 线下报告交付\n")
md.append("## 五、文件清单与复现\n")
md.append("```")
md.append("run.json                  # eval-1.1 根对象（site/scope/rule_results/issues/scores 骨架）")
md.append("site.json                 # SiteProfile")
md.append("scope.json                # 117 URL 角色分布与抽样清单")
md.append("rule_results.json         # 57 条规则结果（确定性 + LLM）")
md.append("llm_checks.json           # LLM 类规则判定（主模型完成）")
md.append("scoring_map.json          # 规则→维度扣分映射与草案分数")
md.append("pages/*.json              # 24 页 PageEvidence")
md.append("evidence/*.html|xml|txt   # 原始 HTML / robots / sitemap")
md.append("scripts/build_evidence.py # 解析 HTML → PageEvidence/SiteProfile")
md.append("scripts/run_rules.py      # 确定性规则（33 条）")
md.append("scripts/merge_llm.py      # LLM 判定 + 评分映射（草案）")
md.append("scripts/build_summary.py  # 生成本摘要")
md.append("```")
md.append("复现：`python3 scripts/build_evidence.py && python3 scripts/run_rules.py && python3 scripts/merge_llm.py && python3 scripts/build_summary.py`")
open(os.path.join(ROOT,"report","evidence_summary.md"),"w",encoding="utf-8").write("\n".join(md))
print("written report/evidence_summary.md")
