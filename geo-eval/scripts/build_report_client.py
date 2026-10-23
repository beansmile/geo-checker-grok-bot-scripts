#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户版正式报告 v2：叙事结构 + 问题内容原文清单 + 修复代码示例（仅供参考）。
输出 report/sofeyia_geo_report_for_client_v3.1_compact.html / .md（精简版）。"""
import json, os, re, html, datetime
from html import unescape
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=lambda n: json.load(open(os.path.join(ROOT,n),encoding="utf-8"))
run=L("run.json"); site=L("site.json"); scope=L("scope.json"); sc=run["scores"]; cs=sc["category_scores"]
pages={os.path.basename(f)[:-5]:json.load(open(f,encoding="utf-8")) for f in __import__("glob").glob(os.path.join(ROOT,"pages","*.json"))}
issues=[i for i in run["issues"] if i["rule_id"]!="TRU-07"]
ADV={a["rule_id"] for a in run.get("advisory_issues",[])}
# 客户版措辞覆盖：内部经验规则不写成搜索引擎官方要求；避免过度定性
TITLE_OVERRIDE={"QLT-02":"模板残留与低价值索引页，可能稀释站点质量信号"}
for _i in issues:
    if _i["rule_id"] in TITLE_OVERRIDE: _i["title"]["zh-CN"]=TITLE_OVERRIDE[_i["rule_id"]]
def E(x): return html.escape(str(x if x is not None else ""))
SEVZH={"S1":"严重","S2":"高","S3":"中","S4":"低"}
def color(g): return {"A+":"#16a34a","A":"#0d9488","B":"#2563eb","C":"#d97706","D":"#dc2626"}.get(g,"#64748b")
date=datetime.date.today().isoformat()
def raw(pid): return open(os.path.join(ROOT,"evidence","pages",pid+".html"),encoding="utf-8",errors="replace").read()
def clean(s): return re.sub(r"\s+"," ",unescape(re.sub(r"<[^>]+>","",s))).strip()
def paras(pid):
    return [clean(x) for x in re.findall(r"<p[^>]*>(.*?)</p>",raw(pid),re.S|re.I) if len(clean(x).split())>=6]
# ---------- 问题内容原文清单 ----------
S={}
S["ENT-01"]=[(pages["about"]["url"],"About Suofeiya（About 页 H1）"),(pages["home"]["url"],"Copyright © 2025 Sofeyia Home Collection Co., Ltd.（页脚）"),(pages["home"]["url"],"Suofeiya Group boasts strong sales performance…（首页正文）")]
S["ENT-02"]=[(pages["contact"]["url"],"sales@sofeyiahome.com（mailto，出现在全站页脚）"),(pages["contact"]["url"],"sales@suofeiyahome.com（Contact 页公司块）")]
S["ENT-04"]=[(pages["contact"]["url"],x) for x in ["Sofeyia Home Collection Co., Ltd.","Suofeiya Home Collection Co., Ltd","Sofeyia Group","Suofeiya Group","Sofeyia Huahe Door Industry Co., Ltd."]]
S["TRU-02"]=[(pages["article_hq"]["url"],'文章 schema 作者：{"@type":"Person","name":"ehaitech"}（默认/建站方账号）')]
S["CLN-04"]=[(pages[p]["url"],ph["quote"]) for p,v in pages.items() for ph in v["placeholders"] if ph["kind"]=="zero_counter"]
S["CLN-05"]=[(pages["privacy"]["url"],"When visitors leave comments on the site we collect the data shown in the comments form…（WordPress 默认隐私模板原文）")]
S["OGP-01"]=[(pages["home"]["url"],"og:title = \"homepage\""),(pages["home"]["url"],"og:description = \"Create. Enhance. and Sustain. Primis non dignissim hac ac iaculis…\u2026\ufeff\"（模板文案+整页拼接）")]
S["SCH-02"]=[(pages["home"]["url"],"Organization 现有属性：name=\"sofeyia\"、url、logo；缺失：sameAs、description、contactPoint")]
S["SCH-04"]=[(pages["home"]["url"],'schema 名称 = "sofeyia"（小写）vs 页面展示品牌 "Sofeyia" / "Suofeiya"')]
S["SCH-01"]=[(pages["home"]["url"],"缺失核心类型：FAQPage、ItemList（现有：Organization/WebSite/Article/BreadcrumbList）")]
S["RCH-01"]=[(pages["faq"]["url"],"FAQ 页 schema 类型："+", ".join(pages["faq"]["schema_types"])+"（无 FAQPage）")]
S["CLN-08"]=[(pages["news"]["url"],"News 列表页与 Company News 列表页正文高度相似（去模板后相似度 0.578）")]
S["KG-04"]=[(pages["home"]["url"],"正文权威外链：0 条；现有外链均为社交图标/系统链接")]
# CLN-03 / ABS-01：正文级样本
lat=[clean(m.group(0)) for m in re.finditer(r"(Massa volutpat[^<]{20,220}?\.)",raw("services"))]
lat+= [clean(m.group(0)) for m in re.finditer(r"(Nisi arcu auctor[^<]{10,180}?\.)",raw("services"))]
lorem=[]
for pid in ["home","about","team","faq","contact","services"]:
    for m in re.finditer(r"(Lorem ipsum[^<]{0,160}?leo\.)",raw(pid)): lorem.append((pages[pid]["url"],clean(m.group(1))))
S["CLN-03"]=[]  # 由下方 cln 统一构造
cln=[]
for x in list(dict.fromkeys(lat))[:3]: cln.append((pages["services"]["url"],x))
cln+=lorem[:5]
S["CLN-03"]=cln
short=[]
for pid in ["services","home","about"]:
    for p in paras(pid):
        if 8<=len(p.split())<=40 and not p.lower().startswith(("kindly","suofeiya home collection","tel/")): short.append((pages[pid]["url"],p))
S["ABS-01"]=short[:6]
S["ONP-02"]=[(pages[p]["url"],pages[p]["title"]["text"]) for p,v in pages.items() if v["role"]=="content" and v["meta_description"]["length"]==0]
S["ONP-03"]=[(pages[p]["url"],f"H1 数量：{len(pages[p]['h1'])}") for p,v in pages.items() if len(v["h1"])!=1]
def headskip(pid):
    seq=[int(m.group(1)) for m in re.finditer(r"<h([1-4])[^>]*>",raw(pid),re.I)]; seen2=False; n=0
    for i,l in enumerate(seq):
        if l==3 and not seen2: n+=1
        if i and l>seq[i-1]+1: n+=1
        if l==2: seen2=True
    return n
S["ONP-04"]=[(pages[p]["url"],f"标题层级跳跃 {headskip(p)} 处") for p,v in pages.items() if v["role"]=="content" and headskip(p)]
# ---------- 修复代码示例（仅供参考） ----------
socials=["https://www.facebook.com/SofeyiaOfficial","https://www.instagram.com/sofeyiahome","https://www.youtube.com/@sofeyiahome","https://www.linkedin.com/company/sofeyiahome","http://www.pinterest.com/sofeyiahome"]
CODE={
"ENT-01":("""<!-- 用结构化数据声明实体关系：让每个名称都指向同一实体（示例；名称与关系请以贵司官方表述为准） -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Sofeyia",
  "legalName": "[法定主体全称，例：索菲亚家居股份有限公司]",
  "alternateName": ["Suofeiya", "Sofeyia Home Collection Co., Ltd.", "索菲亚家居"],
  "url": "https://www.sofeyiahome.com/",
  "sameAs": [
    "https://www.facebook.com/SofeyiaOfficial",
    "https://www.instagram.com/sofeyiahome",
    "https://www.youtube.com/@sofeyiahome",
    "https://www.linkedin.com/company/sofeyiahome",
    "http://www.pinterest.com/sofeyiahome"
  ],
  "parentOrganization": {
    "@type": "Organization",
    "name": "[集团/母公司名称]",
    "sameAs": "https://www.sfygroup.com/"
  }
}
</script>
<!-- 同时在 About / Contact 用同一口径说明各名称关系；不必强制只保留一种拼写 -->""","html"),
"SCH-02":(f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Sofeyia",
  "url": "https://www.sofeyiahome.com/",
  "logo": "https://www.sofeyiahome.com/wp-content/uploads/2023/09/Sofeyia1.png",
  "description": "[请填写公司简介，建议 1–2 句、含行业与业务范围]",
  "foundingDate": "[YYYY-MM-DD，请以官方表述为准]",
  "sameAs": {json.dumps(socials,ensure_ascii=False)},
  "contactPoint": {{
    "@type": "ContactPoint",
    "telephone": "[官方联系电话]",
    "email": "sales@sofeyiahome.com",
    "contactType": "customer service",
    "areaServed": "[服务市场，如 Worldwide]"
  }},
  "address": {{
    "@type": "PostalAddress",
    "streetAddress": "[公司注册地址，以工商/披露为准]",
    "addressLocality": "Guangzhou",
    "addressRegion": "Guangdong",
    "addressCountry": "CN"
  }}
}}
</script>""","html"),
"SCH-01":("""<!-- ItemList 示例（放在产品/项目列表页）；FAQPage 为推荐项、不计分（Google 已于 2026-05-07 停止展示 FAQ 富结果，HowTo 富结果已于 2023 年退役，故可加可不加 -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "What products does Sofeyia provide?",
    "acceptedAnswer": {"@type": "Answer", "text": "[填写权威、可核验的回答]"}
  }]
}
</script>

<!-- ItemList 示例（放在产品/项目列表页） -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "itemListElement": [
    {"@type": "ListItem", "position": 1, "url": "https://www.sofeyiahome.com/category/product-kitchen-cabinet/"},
    {"@type": "ListItem", "position": 2, "url": "https://www.sofeyiahome.com/category/product-closet-wardrobe/"}
  ]
}
</script>""","html"),
"RCH-01":("""<!-- FAQ 页优先重写答案（见「答案可吸收性」）；FAQPage 结构化数据为推荐项、不计分，可不加 -->""","html"),
"ONP-01":("""<!-- 标题标签示例（每页唯一；10–60 字符为我们的评测标准推荐区间，非搜索引擎硬性要求） -->
<title>Sofeyia | Whole-House Custom Cabinetry & Interior Solutions</title>""","html"),
"ONP-02":("""<!-- 元描述示例（我们的评测标准推荐 50–155 字符；Google 官方说明：描述无固定长度限制，过长只会在结果展示时被截断） -->
<meta name="description" content="Sofeyia offers whole-house custom cabinetry and interior solutions, with global project experience and intelligent manufacturing." />""","html"),
"ONP-03":("""<!-- 每页保留唯一 H1，与页面主题一致 -->
<h1>Whole-House Custom Cabinetry Solutions</h1>""","html"),
"OGP-01":("""<!-- Open Graph / Twitter 示例（替换占位与拼接文本） -->
<meta property="og:title" content="Sofeyia | Whole-House Custom Cabinetry" />
<meta property="og:description" content="Global whole-house customization with French design heritage and intelligent manufacturing." />
<meta property="og:url" content="https://www.sofeyiahome.com/" />
<meta property="og:image" content="https://www.sofeyiahome.com/wp-content/uploads/2025/07/home-2.jpg" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Sofeyia | Whole-House Custom Cabinetry" />
<meta name="twitter:description" content="Global whole-house customization with French design heritage and intelligent manufacturing." />""","html"),
"CLN-03":("""<!-- 把占位文本替换为真实内容（示例；请按贵司实际信息修改并核实出处） -->
<h2>Whole-House Custom Cabinetry &amp; Interior Solutions</h2>
<p>Sofeyia 提供橱柜、衣柜与整装定制，覆盖住宅、酒店与公寓等场景；总部位于广州，并已在马来西亚槟城（酒店项目，134 间客房）与伊拉克埃尔比勒（公寓项目，745 套）等市场完成整装交付。</p>
<p>[此处补充并核实：成立年份、产能规模、认证编号、交付周期等具体事实，并标注来源]</p>""","html"),
}
NARR={
 "schema":"基础结构化数据已具备（组织信息 / 网站 / 文章 / 面包屑），但关键属性不完整：缺列表结构化数据（ItemList），组织信息缺官方账号、简介、联系方式，且结构化数据里的名称为 sofeyia（小写），与页面展示的品牌写法不一致。结构化数据是机器理解实体与主题的辅助信号——Google 明确它不是排名因子，我们的评测据此把它定位为“实体消歧与可理解性”的辅助项；优先顺序应低于实体口径与内容本身。",
 "entity":"网站同时使用 Sofeyia 与 Suofeiya 两种品牌写法、公司名多种拼写、公开邮箱两个域名，且缺少与上市主体（索菲亚家居股份有限公司 002572.SZ）的关联说明。实体不一致会削弱搜索引擎与 AI 建立“同一品牌”的信心，是本次影响最大的问题。注：多种写法可以并存（集团/上市主体/国际品牌），关键是关系要声明清楚，而非强制统一。",
 "ogp":"分享标签形式存在，但首页 og:title 为占位值 homepage、og:description 为页面拼接文本并含模板文案，Twitter 卡片缺标题与描述。这类字段主要影响分享与摘要时的呈现，对 AI 引用属次要卫生项，故本维度权重较低。",
 "richness":"内容以 6 篇文章与 1 个 FAQ 页为主，但更缺的是能回答买家问题的页面（交付周期、材料标准、与 Sogal / Schmidt 等品牌的关系、某市场的整装怎么做），而不是单纯“再发几篇新闻”。FAQ 页未用结构化数据；News 与 Company News 两个列表页正文高度相似。",
 "knowledge_graph":"本维度实为“站内实体信号”（原名“实体权威与知识图谱”，改名以明确范围）：组织信息缺官方账号、业务范围、成立日期等声明，正文也缺指向权威来源的引用。需要说明：实体权威的更主要证据在站外（集团官网互链、交易所披露、行业名录、媒体提及），本报告为站内检测，站外部分不在计分范围。",
 "absorption":"正文普遍是短句与占位，缺少“离开页面也能独立成立、且带可核验事实”的自包含答案块；定义、数据、对比、步骤四类证据块覆盖不足；首页主标题仍是模板文案。AI 引用的是能整块抽取的事实与回答，这决定内容能否进入 AI 答案。",
 "trust":"具备关于、项目案例、条款与联系页，项目案例含房间数等细节（数字需有出处，暂不作加分项）；但文章署名使用默认账号 ehaitech、团队页存在占位内容、资质表述缺少可验证出处。综合一致性问题，本维度已触达评分上限。",
 "on_page":"抽样 24 页中 22 页缺少元描述、部分标题超长；H1 与标题层级问题主要出现在演示页与系统页（本就该移除）。页面主题与元数据属卫生项，本维度权重较低，不作为 AI 引用主因。",
 "quality":"多个页面存在模板占位（Lorem ipsum 与拉丁填充）、重复段落，以及缺少事实支撑的绝对化表述（China’s No.1、The ONLY 等）。这些既影响模型可信度，也带来广告法合规风险，是内容治理最需优先处理的部分。",
}
IMPROVE={
 "schema":"补全组织信息的官方账号、简介、联系方式，并新增列表结构化数据（ItemList）；FAQ 结构化数据为推荐项、不计分（Google 已于 2026-05-07 停止展示 FAQ 富结果，HowTo 已于 2023 年退役；FAQPage 仍有价值，但主要供大模型读取）。",
 "entity":"先建立实体映射（法定主体→集团→品牌→国际品牌→域名→社交/邮箱），再用「关于我们」页与组织信息结构化数据声明关联；不必强制统一拼写，但每个名称都要指向同一实体。",
 "ogp":"为重要页面单独撰写 og:title / og:description 与 Twitter 标题/描述，避免复用页面拼接文本（次要卫生项，优先度低于内容与实体）。",
 "richness":"围绕买家真实问题建立内容矩阵：交付周期、材料/认证、与子品牌关系、项目案例；而非机械增加文章数量。",
 "knowledge_graph":"站内补全官方账号、业务范围、成立日期等声明，并在正文引用权威来源；实体权威的站外证据（集团官网互链、行业名录、媒体提及）建议作为后续动作单独推进。",
 "absorption":"把关键内容改写成自包含答案块（先答后述 + 事实/数据），定义、数据、对比、步骤四类证据块组织内容。",
 "trust":"建立真实作者与资质页、补全团队信息，为数据与资质标注来源；优先解决一致性问题。",
 "on_page":"为页面补齐标题与元描述、修正 H1 与层级（优先清理演示/系统页，而非在将被移除的页面上改 H1）。",
 "quality":"清理模板与占位内容，删除或标注绝对化表述的出处，建立发布前质量检查流程。",
}
CLIENT_FIX={
 "CLN-03":"删除页面中的 Lorem ipsum 与拉丁占位段落，替换为真实产品/公司介绍，并在发布前加入占位文本检查。",
 "CLN-04":"计数器其实有真实数值，但依赖滚动动画由 JS 显示，初始 HTML 是 0——AI 爬虫读到的就是 0，等于向 AI 暴露“0 年经验”。请在初始 HTML 直接输出真实数字（服务端渲染或加静态兜底），让 AI 能读到真实值。",
 "CLN-05":"由法务确认后，将 WordPress 默认隐私模板替换为符合业务与目标市场法规的版本。",
 "CLN-06":"将“Discover more / Read more”等占位按钮替换为有明确去向的按钮，并清理空链接。",
 "CLN-02":"从站点地图与索引中移除模板演示页（pabriz-*、elementor-* 等），避免稀释正文页面。",
 "CLN-09":"将购物车、结算、我的账户等系统页设为禁止索引（noindex），并从站点地图移除。",
 "CLN-08":"合并或差异化 News 与 Company News 两个列表页的内容，减少重复。",
 "CLN-10":"集中清理模板残留（占位文案、0 值数据、默认模板），这是当前最影响可信度的问题。",
 "ENT-01":"建立实体映射（法定主体→集团→品牌→国际品牌→域名→社交/邮箱），用「关于我们」页与组织信息结构化数据声明各名称同属一个实体。建议：域名是 sofeyiahome.com，对外主名用 Sofeyia；Suofeiya 为中文名拼音，保留为别名即可。若存在历史主体英文名改动，请以官方口径为准。",
 "ENT-02":"统一企业邮箱域名（建议使用与官网一致的 @sofeyiahome.com），并在结构化数据的联系方式中列明主用邮箱；如确有历史域名，应在实体映射中说明其归属。",
 "ENT-04":"用实体映射表固定各层级名称的写法与关系，明确与上市主体（索菲亚家居股份有限公司 002572.SZ）的关联，而不是只做文本替换。",
 "ENT-06":"在「关于我们」页说明 Sofeyia 与 Suofeiya / Sogal / Schmidt / Milanna 的关系，并在结构化数据中用别名、母公司属性声明。",
 "ENT-07":"核对成立/引入/上市时间线，以官方披露口径统一表述，删除互相冲突的数字与年份。",
 "ONP-01":"将超长标题精简到我们的评测标准推荐区间内，把核心关键词前置。",
 "ONP-02":"为缺失元描述的页面逐页撰写描述，突出页面价值；Google 官方并未规定固定长度。",
 "ONP-03":"确保每个页面仅保留一个表达主题的 H1。",
 "ONP-04":"按 H1 → H2 → H3 顺序整理标题层级，避免跳级。",
 "ONP-05":"首屏用一句话直接陈述页面主题，避免使用模板文案。",
 "ONP-06":"为产品页补充参数、适用场景与对比内容，使其能直接回答用户问题。",
 "SCH-01":"补充列表结构化数据（ItemList）；FAQ 结构化数据为推荐项、不计分（Google 已于 2026-05-07 停止展示 FAQ 富结果，HowTo 已于 2023 年退役；FAQPage 仍有价值，但主要供大模型读取）。",
 "SCH-02":"补全组织信息的官方账号、简介、联系方式，用机器可读的方式声明品牌归属。",
 "SCH-04":"统一结构化数据名称与对外品牌写法，避免大小写与拼写不一致。",
 "SCH-07":"补全联系方式并统一邮箱域名，使其与站点域名一致。",
 "SCH-10":"改用真实作者署名并建立作者页，使结构化数据作者与页面署名一致。",
 "RCH-01":"先把 FAQ 页的占位问答改写为可独立成段的真实答案；FAQ 结构化数据为推荐项、不计分。",
 "RCH-02":"围绕客户常见问题与选型场景补充内容，数量为内部参考、非硬性要求。",
 "RCH-03":"补充交付周期、材料/认证、安装保养等买家真正关心的问题页面。",
 "ABS-01":"把关键短段落改写为能整块被引用的自包含答案块（先答后述 + 含事实或数据）。",
 "ABS-02":"按定义、数据、对比、步骤四类组织内容，提升被 AI 抽取的概率。",
 "ABS-04":"在首屏用一句话直接回答页面主题，再展开细节。",
 "OGP-01":"为首页与重要页面撰写独立的分享标题与描述，替换占位与拼接文本。",
 "OGP-02":"补齐 Twitter 卡片的标题与描述。",
 "KG-01":"在组织信息结构化数据中填写官方账号（sameAs），指向已核实的社交账号与集团官网。",
 "KG-02":"在组织信息中声明业务范围（knowsAbout），说明主营产品与服务。",
 "KG-03":"在组织信息中补全成立日期（foundingDate），以官方工商/披露口径为准。",
 "KG-04":"在正文引用权威来源（交易所公告、集团官网、认证机构、行业报告）并附链接。",
 "KG-06":"在组织信息中补全地址与服务区域（location / areaServed），明确服务市场。",
 "TRU-02":"将默认账号 ehaitech 替换为真实作者，并补充作者简介与资质。",
 "QLT-01":"补充一手经验内容（谁写的、怎么做的、为什么可信），替换通用营销文案。",
 "QLT-02":"清理重复段落与占位内容，逐步补齐一手内容；对低价值索引页建议禁止索引或删除。",
}
def dim_issues(d): return [i for i in issues if i["dimension"]==d and i["rule_id"] not in ADV]
# ---------- 附加说明块（按规则挂载，客户版不做“强制统一拼写”，改为实体映射） ----------
ENTITY_MAP=[
 ("法定主体","索菲亚家居股份有限公司（002572.SZ，深交所）—— 在「关于我们」/「联系我们」页面明确其为品牌所属上市主体，并链接公告"),
 ("集团 / 母公司","Suofeiya Group / Sofeyia Group（站内两种写法）—— 用组织信息（Organization）的母公司属性（parentOrganization）关联，名称二选一并登记在映射表"),
 ("品牌（中文）","索菲亚 —— 保持现有表述"),
 ("品牌（英文 / 国际）","Sofeyia / Suofeiya / Sogal / Schmidt / Milanna —— 确定主名称，其余写入组织信息的别名（alternateName），并说明相互关系"),
 ("官网域名","sofeyiahome.com（本站）；sfygroup.com、suofeiya.com（集团）—— 在组织信息的官方账号（sameAs）中关联，并说明域名归属"),
 ("企业邮箱","sales@sofeyiahome.com / sales@suofeiyahome.com —— 确定主用域名，并在联系方式（contactPoint）中列明"),
 ("社交账号","Facebook / Instagram / YouTube / LinkedIn / Pinterest（命名不一）—— 全部写入组织信息的官方账号（sameAs）"),
]
EXTRA={"ENT-01":'<ul class="plain">'+"".join(f"<li><b>{E(k)}</b>：{E(v)}</li>" for k,v in ENTITY_MAP)+
 '<li><b>说明</b>：关键不是消除所有差异，而是让每个名称与账号都能被机器归到同一个实体（Google 支持组织信息的别名 alternateName）。</li></ul>',
 "ENT-04":'<ul class="plain">'+"".join(f"<li><b>{E(k)}</b>：{E(v)}</li>" for k,v in ENTITY_MAP)+'</ul>',
}
def block(i):
    smp=S.get(i["rule_id"]) or []
    rec=CLIENT_FIX.get(i["rule_id"]) or i["recommendation"]["zh-CN"]
    smp_html=('<div class="samples"><b>问题内容：</b><ul>'+"".join(f'<li><span class="where">{E(u)}</span>{E(t)}</li>' for u,t in smp)+"</ul></div>") if smp else ""
    code=CODE.get(i["rule_id"])
    code_html=(f'<details class="code"><summary>修复示例（仅供参考，请替换占位信息）</summary><pre>{E(code[0])}</pre></details>') if code else ""
    extra=(f'<h3>建议的实体映射</h3>{EXTRA[i["rule_id"]]}') if i["rule_id"] in EXTRA else ""
    ev="".join(f'<div class="quote"><a href="{E(e.get("url"))}" target="_blank">{E(e.get("url"))}</a><p>{E(e.get("quote"))}</p></div>' for e in (i.get("evidence") or [])[:2])
    return f'''<div class="find"><div class="fh"><span class="tag" style="background:{color("D") if i["severity"]=="S1" else "#f59e0b"}">{SEVZH[i["severity"]]}</span><b>{E(i["title"]["zh-CN"])}</b></div>
    <p class="rec">{E(rec)}</p>{smp_html}{extra}{code_html}<details class="src"><summary>来源</summary>{ev}</details></div>'''
def clist(items): return "".join(block(i) for i in items)
dims=""
for key,name in [("schema","结构化数据"),("entity","品牌与实体一致性"),("ogp","开放图谱与分享"),("richness","内容覆盖与新鲜度"),("knowledge_graph","站内实体信号"),("absorption","答案可吸收性"),("trust","信任度"),("on_page","页面主题与元数据"),("quality","内容质量")]:
    v=cs[key]; items=dim_issues(key)
    dims+=f'''<section class="chap"><div class="chap-head"><div><div class="kicker">评分维度</div><h2>{E(name)}</h2></div>
    <div class="score"><b style="color:{color(v["grade"])}">{v["score"]}</b><span>/{v["max"]}</span><i style="background:{color(v["grade"])};width:{v["percentage"]}%"></i></div></div>
    <p class="narr">{E(NARR[key])}</p>{('<h3>本维度主要发现</h3>'+clist(items)) if items else ''}<div class="imp"><b>提升建议：</b>{E(IMPROVE[key])}</div></section>'''
sevc={s:sum(1 for i in issues if i["severity"]==s) for s in ("S1","S2","S3","S4")}
strengths=["带 www 的官网可正常打开且自动加密（不带 www 的地址请网管另看）；","主流 AI 检索爬虫（OAI-SearchBot / GPTBot / ClaudeBot / PerplexityBot）均可访问，robots.txt 未屏蔽；","关于、项目案例、条款与联系页齐备，项目案例含房间数等细节（数字需有出处）；","已具备 Organization / WebSite / Article / BreadcrumbList 等基础结构化数据；","栏目与站点结构清晰（产品/项目/新闻/合作/关于），站点地图完整。"]
# 第三列改为“可恢复空间”：= 该维度满分 − 当前得分，可从报告内的维度表逐项核对；不逐条叠加
actions=[("清理模板与占位内容","删除占位段落，让计数器数字直接输出到初始 HTML，移除演示/系统页，补齐缺失的标题与元描述","建站商执行","第 1 周","前台再也看不到 Lorem / 拉丁文，演示页与系统页不可访问或从站点地图移除"),
 ("统一品牌与邮箱口径","建立“法定主体→集团→品牌→国际品牌→域名→社交/邮箱”映射，用组织信息结构化数据声明关联","贵司确认 + 建站商执行","第 1 周（贵司拍板半天）","全站页脚、联系页、关于页使用同一品牌写法与同一邮箱；关于页写明与上市主体的关系"),
 ("补全结构化数据","补齐组织信息属性与列表结构化数据；FAQ 结构化数据为推荐项、不计分","建站商执行","第 2–3 周","组织信息名片补齐官方账号/简介/联系方式（口径以贵司确认为准）"),
 ("元数据与标题结构批修","为重要页面配置独立标题与元描述，修正标题层级","建站商执行","第 2–3 周","重要页面标题与元描述独立撰写；演示/系统页已下线"),
 ("升级内容架构","按定义/数据/对比/步骤重组重点内容，标注来源，建立作者与资质页","贵司 + 可自行改文案","持续","写好 4 类页：我们是谁、如何交付、材料认证、2–3 个可核对的案例")]
act_rows="".join(f"<tr><td><b>{E(a)}</b></td><td>{E(b)}</td><td>{E(c)} · {E(d)}</td><td>{E(e)}</td></tr>" for a,b,c,d,e in actions)
dash=2*3.14159*54*(1-sc["overall_score"]/100)
HTML=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>索菲亚官网 GEO 评测报告</title><style>
:root{{--ink:#0f172a;--ink2:#475569;--ink3:#94a3b8;--line:#e6ebf2;--bg:#f7f9fc;--accent:#4f46e5}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15.5px/1.85 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif}}
.wrap{{max-width:960px;margin:0 auto;padding:34px 22px 90px}}
.cover{{background:linear-gradient(140deg,#312e81,#4f46e5 55%,#0ea5e9);color:#fff;border-radius:22px;padding:40px 38px}}
.cover .kicker{{font-size:12px;letter-spacing:.2em;text-transform:uppercase;opacity:.85}}.cover h1{{margin:8px 0 16px;font-size:30px}}
.cover .row{{display:flex;gap:30px;align-items:center;flex-wrap:wrap}}
.ring{{position:relative;width:150px;height:150px;flex:0 0 150px}}.ring svg{{transform:rotate(-90deg)}}
.ring .val{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}}.ring .val b{{font-size:44px;line-height:1}}.ring .val span{{font-size:13px;opacity:.9;margin-top:4px}}
.meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:6px 24px;font-size:13.5px;opacity:.95}}
.chips{{margin-top:14px;display:flex;gap:8px;flex-wrap:wrap}}.chip{{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.32);border-radius:999px;padding:4px 11px;font-size:12.5px}}
section{{margin-top:38px}}h2{{font-size:21px;margin:0}}h3{{font-size:15.5px;color:var(--ink2);margin:20px 0 8px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:22px 24px;box-shadow:0 1px 3px rgba(15,23,42,.05)}}
.lead{{font-size:17px}}.narr{{color:var(--ink2)}}ul.plain{{margin:8px 0 0 20px;color:var(--ink2)}}
.chap{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:24px 26px;margin-top:18px;box-shadow:0 1px 3px rgba(15,23,42,.05)}}
.chap-head{{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:14px}}
.chap-head .kicker{{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);font-weight:700}}
.score{{display:flex;align-items:baseline;gap:4px;min-width:190px;flex-wrap:wrap;justify-content:flex-end}}.score b{{font-size:32px}}.score span{{color:var(--ink3)}}.score i{{display:block;height:8px;border-radius:99px;margin-top:8px;width:100%}}
.find{{border:1px solid var(--line);border-left:3px solid #f59e0b;border-radius:10px;padding:12px 14px;margin:10px 0}}
.fh{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}.tag{{color:#fff;border-radius:999px;padding:1px 9px;font-size:11.5px;font-weight:700}}
.rec{{margin:6px 0;color:var(--ink2);font-size:14.5px}}
.samples{{background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:8px 12px;margin:8px 0;font-size:13.5px}}
.samples ul{{margin:6px 0 0 18px}}.samples li{{margin:4px 0;color:#7c2d12}}.samples .where{{display:block;font-size:11.5px;color:#9a3412;word-break:break-all}}
details.code,details.src{{margin:8px 0}}details summary{{cursor:pointer;color:var(--accent);font-size:13.5px}}
pre{{background:#0f172a;color:#e2e8f0;border-radius:10px;padding:14px;overflow:auto;font:12.5px/1.6 ui-monospace,Menlo,monospace;white-space:pre-wrap}}
.quote{{background:#f8fafc;border:1px dashed var(--line);border-radius:8px;padding:8px 11px;margin:6px 0;font-size:13px}}.quote a{{color:var(--ink3);font-size:12px;word-break:break-all}}.quote p{{margin:3px 0 0;color:var(--ink2)}}
.imp{{margin-top:14px;background:#eef2ff;border:1px solid #c7d2fe;border-radius:10px;padding:12px 14px;font-size:14.5px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}}th,td{{text-align:left;padding:11px 13px;border-bottom:1px solid var(--line);font-size:14px;vertical-align:top}}th{{background:#f1f5f9;color:var(--ink2)}}
.gain{{color:#16a34a;font-weight:700;white-space:nowrap}}footer{{margin-top:40px;text-align:center;color:var(--ink3);font-size:12.5px}}
@media print{{body{{background:#fff}}.cover{{border-radius:0}}.chap,section,.find{{break-inside:avoid}}pre{{white-space:pre-wrap}}}}
</style></head><body><div class="wrap">
<div class="cover"><div class="kicker">生成式引擎优化 · 专家评测报告</div><h1>索菲亚官网 GEO 评测报告</h1>
<div class="row"><div class="ring"><svg width="150" height="150"><circle cx="75" cy="75" r="54" fill="none" stroke="rgba(255,255,255,.25)" stroke-width="13"/>
<circle cx="75" cy="75" r="54" fill="none" stroke="#fff" stroke-width="13" stroke-linecap="round" stroke-dasharray="339.3" stroke-dashoffset="{dash:.1f}"/></svg>
<div class="val"><b>{sc["overall_score"]}</b><span>{E(sc["grade"])} · 站内准备度</span></div></div>
<div style="flex:1;min-width:300px"><div class="meta"><div>站点：{E(site["url"])}</div><div>报告日期：{date}</div>
<div>检测范围：{scope["pages_total"]} 个 URL · 深检 {len(scope["sampled_pages"])} 页</div><div>问题分布：严重 {sevc["S1"]} · 高 {sevc["S2"]} · 中 {sevc["S3"]} · 低 {sevc["S4"]}</div></div>
<div class="chips"><span class="chip">内容可信度与治理</span><span class="chip">品牌与实体一致性</span><span class="chip">结构化数据</span><span class="chip">答案可吸收性</span></div></div></div></div>

<section><div class="card"><h2>一、总体评价</h2>
<p class="lead">本站 <b>GEO 站内准备度为 {sc["overall_score"]} 分（{E(sc["grade"])}）</b>。网站在技术基础与信息架构上具备良好起点，但在<b>品牌与实体一致性、内容可信度、结构化数据完整性</b>三方面存在明显短板，是当前影响 AI 搜索表现的主要因素。</p>
<p class="narr">本次高优先级问题共 {sevc["S1"]} 项，集中在两处：品牌写法与邮箱域名混用（Sofeyia / Suofeiya、两个邮箱域名），以及页面中残留的模板占位文案与演示内容。这两类问题会直接影响 AI 与搜索引擎对“品牌是谁、内容是否可信”的判断。</p>
<p class="narr">本报告采用新版检测口径（在“信号是否存在”的基础上增加“内容是否正确、建议是否可用”），分数与旧版报告不可直接比较；分数衡量的是被生成式搜索正确理解、信任与引用的准备度，而非排名或流量结果。</p></div></section>

<section><div class="card"><h2>二、表现良好的部分</h2><ul class="plain">{"".join(f"<li>{E(s)}</li>" for s in strengths)}</ul></div></section>

<section><div class="card"><h2>三、关键发现</h2><p class="narr">以下为本轮最需要优先处理的问题（含问题内容与修复示例）：</p>{clist([i for i in issues if i["severity"] in ("S1","S2")][:10])}</div></section>

<section><h2 style="margin-bottom:6px">四、分维度评估</h2><p class="narr" style="margin-top:6px">共 9 个维度，满分 100 分。每个维度给出得分、解读、问题内容与提升建议。</p>{dims}</section>

<section><div class="card"><h2>五、优先改进建议</h2><table><thead><tr><th>行动</th><th>问题与建议</th><th>执行方 · 建议周期</th><th>完成标准</th></tr></thead><tbody>{act_rows}</tbody></table>
<p class="narr" style="margin-top:10px">各项不叠加（同一处改动会同时影响多个维度）；总分即九个维度之和，每个根因只计一次。</p></div></section>

<section><div class="card"><h2>六、检测范围</h2><p class="narr">域名：{E(site["domain"])}；sitemap：{scope["pages_total"]} 个 URL；深度检测 {len(scope["sampled_pages"])} 页，覆盖首页、关于、联系、FAQ、新闻/文章、产品、项目、条款以及演示/系统页。</p>
<p class="narr">另有 {len(run.get("advisory_issues",[]))} 项“需确认或补充的信息”（如数据来源、资质出处、社交账号策略等）已单独整理，供贵司核对。</p></div></section>
<footer>索菲亚官网 GEO 评测报告 · {date} · run {E(run["run_id"])}<br>如需进一步解读或定制改进方案，欢迎与我们联系。</footer>
</div></body></html>'''
open(os.path.join(ROOT,"report","sofeyia_geo_report_for_client_v3.1_compact.html"),"w",encoding="utf-8").write(HTML)
# Markdown 版
def md_block(i):
    smp=S.get(i["rule_id"]) or []
    rec=CLIENT_FIX.get(i["rule_id"]) or i["recommendation"]["zh-CN"]
    lines=[f"- **[{SEVZH[i['severity']]}] {i['title']['zh-CN']}**：{rec}"]
    if smp:
        lines.append("  - 问题内容：")
        for u,t in smp: lines.append(f"    - `{u}`：{t}")
    if CODE.get(i["rule_id"]): lines += ["  - 修复示例（仅供参考）：","", "```html", CODE[i["rule_id"]][0], "```",""]
    if i["rule_id"] in EXTRA:
        lines.append("  - 建议的实体映射：")
        for k,v in ENTITY_MAP: lines.append(f"    - **{k}**：{v}")
    return "\n".join(lines)
MD=f"""# 索菲亚官网 GEO 评测报告

- 站点：{site['url']}
- 报告日期：{date}　|　检测范围：sitemap {scope['pages_total']} 个 URL，深检 {len(scope['sampled_pages'])} 页
- 站内准备度：**{sc['overall_score']} / 100（{sc['grade']}）**

## 一、总体评价
本站 GEO 站内准备度为 {sc['overall_score']} 分（{sc['grade']}）。技术基础与信息架构具备良好起点，但品牌与实体一致性、内容可信度、结构化数据完整性存在明显短板。本次严重级问题 {sevc['S1']} 项，集中在品牌/邮箱不一致与模板占位内容。本报告采用新版检测口径，分数与旧版不可直接比较。

## 二、表现良好的部分
"""+"\n".join(f"- {s}" for s in strengths)+"\n\n## 三、关键发现\n"+"\n".join(md_block(i) for i in issues if i["severity"] in ("S1","S2")[:10])+"\n\n## 四、分维度评估\n"+"\n\n".join(f"### {name}（{cs[key]['score']}/{cs[key]['max']}）\n{NARR[key]}\n\n"+"\n".join(md_block(i) for i in dim_issues(key))+"\n\n提升建议："+IMPROVE[key] for key,name in [("schema","结构化数据"),("entity","品牌与实体一致性"),("ogp","开放图谱与分享"),("richness","内容覆盖与新鲜度"),("knowledge_graph","站内实体信号"),("absorption","答案可吸收性"),("trust","信任度"),("on_page","页面主题与元数据"),("quality","内容质量")])+f"""

## 五、优先改进建议
| 行动 | 问题与建议 | 可恢复空间（可从维度表核对） |
|---|---|---|
"""+"\n".join(f"| {a} | {b} | {c} · {d} | {e} |" for a,b,c,d,e in actions)+f"""

## 六、检测范围
- 域名：{site['domain']}；sitemap {scope['pages_total']} 个 URL；深检 {len(scope['sampled_pages'])} 页
- 另有 {len(run.get('advisory_issues',[]))} 项“需确认或补充的信息”另行整理
"""
open(os.path.join(ROOT,"report","sofeyia_geo_report_for_client_v3.1_compact.md"),"w",encoding="utf-8").write(MD)
print("wrote sofeyia_geo_report_for_client_v3.1_compact.html/.md ; samples:",{k:len(v) for k,v in S.items() if v},"; code:",sorted(CODE))
