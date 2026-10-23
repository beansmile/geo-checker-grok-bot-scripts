#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户版 v3.0：幻灯式（一页一节）正式报告。
- 品牌页眉（Logo + 报告名 + 站点 + 页码），不做“模板原版 vs 当前页”对比
- 每个 section 一张独立卡片，向下滚动 / ← → 翻页，ESC 打开索引
- 封面为深色封套，含文件编号；末页为结论与签核栏
- 内容沿用 v1.1/v2.0：问题内容原文 + 修复示例（仅供参考）+ 无工期无工作量
输出 report/sofeyia_geo_report_for_client_v3.1.html（主报告·卡片式）。
"""
import os, sys, json, html, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_report_official as O          # 复用 v2.0 组件与文案（会同时刷新 v1.1 / v2.0）
B = O.B
ROOT = B.ROOT
run, site, scope, sc, cs = B.run, B.site, B.scope, B.sc, B.cs
issues, ADV, S, CODE = B.issues, B.ADV, B.S, B.CODE
NARR, IMPROVE, CLIENT_FIX = B.NARR, B.IMPROVE, B.CLIENT_FIX
strengths, actions, dim_issues = B.strengths, B.actions, B.dim_issues
EXTRA = B.EXTRA
DIMS = O.DIMS
SEV = O.SEV
SEVZH = {"S1":"严重","S2":"高","S3":"中","S4":"低"}
# 执行方（客户可派工的四类）
OWNER = {
 "ENT-01":"贵司确认","ENT-02":"贵司确认","ENT-04":"贵司确认","ENT-06":"贵司确认","ENT-07":"贵司确认",
 "CIT-03":"贵司确认","CIT-02":"贵司确认","TRU-04":"贵司确认","ABS-03":"贵司确认",
 "KG-01":"贵司确认","KG-02":"贵司确认","KG-03":"贵司确认","KG-06":"贵司确认",
 "CLN-02":"建站商执行","CLN-03":"建站商执行","CLN-04":"建站商执行","CLN-06":"建站商执行",
 "CLN-08":"建站商执行","CLN-09":"建站商执行","CLN-10":"建站商执行","CLN-11":"建站商执行",
 "SCH-01":"建站商执行","SCH-02":"建站商执行","SCH-04":"建站商执行","SCH-07":"建站商执行","SCH-10":"建站商执行",
 "OGP-01":"建站商执行","OGP-02":"建站商执行",
 "ONP-01":"建站商执行","ONP-02":"建站商执行","ONP-03":"建站商执行","ONP-04":"建站商执行","ONP-05":"建站商执行","ONP-06":"建站商执行",
 "TLS-APEX":"建站商执行",
 "CLN-05":"法务确认","QLT-03":"法务确认",
 "ABS-01":"可自行改文案","ABS-02":"可自行改文案","ABS-04":"可自行改文案","ABS-06":"可自行改文案",
 "RCH-01":"可自行改文案","RCH-02":"可自行改文案","RCH-03":"可自行改文案",
 "QLT-01":"可自行改文案","QLT-02":"可自行改文案","TRU-02":"可自行改文案","TRU-05":"可自行改文案","KG-04":"可自行改文案",
}
OWNER_COLOR = {"贵司确认":"primary","建站商执行":"info","法务确认":"warning","可自行改文案":"success"}
# 关键发现“这对您意味着什么”（业务后果人话）
IMPACT_ZH = {
 "CLN-03":"网站多页残留乱码般的假文字，像没装修完就开业，客户和 AI 都会觉得这网站还没做完。",
 "ENT-01":"Sofeyia 和 Suofeiya 看起来像两家公司，多年积累的品牌认知会被分流。",
 "ENT-02":"官网用 A 域名、留的邮箱却是 B 域名，像名片印错，客户会怕是钓鱼。",
 "ENT-04":"公司名几种写法并存，AI 难以确定是不是同一家。",
 "ENT-06":"子品牌关系没讲清，AI 和客户都分不清谁是谁。",
 "ENT-07":"成立/上市年份互相冲突，可信度打折。",
 "ABS-01":"网站上没有一段“干货”值得 AI 引用，等于在 AI 时代隐形。",
 "ABS-02":"缺定义/数据/对比/步骤四类干货，AI 想引也没得引。",
 "CIT-03":"最大的信任资产（上市公司背景）在官网上没用起来。",
 "CLN-02":"交给搜索引擎的目录里混着样板间页面，稀释正式内容。",
 "CLN-04":"首页数字其实有真实值，但靠滚动动画才显示——AI 读到的是初始值 0，等于在 AI 眼里这是一家“0 年经验、0 员工”的公司。",
 "CLN-05":"法律页面是建站系统自带的范文，有合规风险。",
 "CLN-06":"多个按钮点了没反应或去向不明，客户会以为网站坏了。",
 "CLN-08":"两个新闻栏目内容重复，浪费权重。",
 "CLN-09":"目录里混入大量没内容的页面，拉低整体印象。",
 "CLN-10":"模板残留明显，像没拆完的样板间。",
 "ONP-03":"部分页面没有主标题，机器难以判断页面主题。",
 "QLT-01":"内容像通用营销文案，没有“谁写的、怎么做的、为什么可信”。",
 "QLT-02":"批量重复/占位内容，稀释质量信号。",
 "SCH-07":"联系方式缺失且邮箱不一致，机器无法确认对外窗口。",
 "TRU-02":"文章作者是建站账号，没有真人署名，难以建立信任。",
 "RCH-01":"FAQ 是占位问答，等于没答。",
 "KG-04":"正文没有引用权威来源，AI 不敢把内容当事实。",
 "SCH-02":"机器名片缺官方账号、简介、联系方式，AI 认不出你是谁。",
 "ONP-02":"多数页面在搜索结果里没有摘要，白白浪费曝光位。",
}

date = datetime.date.today().isoformat()
def E(x): return html.escape(str(x if x is not None else ""))
GRADE_VAR = O.GRADE_VAR
sevc = O.sevc
total_issues = sum(sevc.values()) or 1
DOMAIN = site["domain"].replace("https://", "").replace("http://", "").rstrip("/")
RUN_ID = run["run_id"]
DOC_NO = "GEO-" + date.replace("-", "") + "-" + RUN_ID.split("-run")[-1].zfill(2)

# ---------- 评分口径（一律从 scoring_map.json 读取，保证可复现） ----------
sm = json.load(open(os.path.join(ROOT, "scoring_map.json"), encoding="utf-8"))
def num(v):
    s = ("%.1f" % float(v)).rstrip("0").rstrip(".")
    return s or "0"
def weight_chip(i):
    """逐条问题只给可核对的“影响权重”，不再给不可叠加的 +N 分。"""
    lab = (i.get("priority_label") or {}).get("zh-CN") or SEV[i["severity"]][1]
    return f'<span class="wchip">影响权重 · {E(lab)}</span>'

# ---------- 组件 ----------
MARK = '<svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><rect width="28" height="28" rx="7" fill="var(--mark-bg)"/><rect x="7" y="15.4" width="3.4" height="5.6" rx="1" fill="var(--mark-fg)"/><rect x="12.3" y="11.4" width="3.4" height="9.6" rx="1" fill="var(--mark-fg)" opacity=".82"/><rect x="17.6" y="7.4" width="3.4" height="13.6" rx="1" fill="var(--mark-fg)" opacity=".62"/></svg>'

def page_header(pno, total, section=None):
    mid = f'<span class="ph-sec">{E(section)}</span>' if section else ""
    return f'''<header class="ph"><span class="brand">{MARK}<b>GEO SCORING</b></span>
      <span class="ph-url mono">{E(DOMAIN)}</span>{mid}
      <span class="ph-right"><span class="mono">{date}</span><span class="pgnum mono">{pno:02d} / {total:02d}</span></span></header>'''

def page_footer():
    return f'<footer class="pf"><span>GEO SCORING · 评测报告（待审核）</span><span class="mono">报告编号 {E(DOC_NO)}</span></footer>'

def cover_meter():
    v = sc["overall_score"]
    return f'''<div class="cmeter"><div class="cm-track"><span class="cm-fill" style="width:{v}%"></span></div>
      <div class="cm-scale"><span>0</span><span>及格 60</span><span>良好 80</span><span>100</span></div></div>'''

def sev_strip():
    order = [("S1", "danger", "严重"), ("S2", "warning", "高"), ("S3", "info", "中"), ("S4", "muted", "低")]
    segs = "".join(f'<span class="ss ss-{k}" style="width:{sevc[s]/total_issues*100:.1f}%"></span>' for s, k, _ in order)
    leg = "".join(f'<span><i class="dot d-{k}"></i>{lab} <b>{sevc[s]}</b></span>' for s, k, lab in order)
    return f'<div class="sevstrip"><div class="ss-track">{segs}</div><div class="ss-legend">{leg}<span class="dim">共 {total_issues} 项</span></div></div>'

def dim_rows(items, compact=False):
    """维度页内的问题行（扁平列表，用细线分隔，不嵌套卡片）。"""
    out = []
    for i in items:
        sev = SEV[i["severity"]]
        fix = CLIENT_FIX.get(i["rule_id"]) or i["recommendation"]["zh-CN"]
        code = CODE.get(i["rule_id"])
        ev = (i.get("evidence") or [])[:3]
        body = ""
        if ev and not compact:
            body += '<div class="evrow"><span class="evlab">问题内容原文</span><ul>' + "".join(
                f'<li><code class="mono">{E(e.get("url"))}</code><span>{E(e.get("quote"))}</span>{annote(e.get("quote",""))}</li>' for e in ev) + '</ul></div>'
        if code:
            body += code_block(code[0], "给建站商的参考代码")
        if i["rule_id"] in EXTRA:
            body += '<div class="sublab">建议的实体映射</div>' + EXTRA[i["rule_id"]]
        out.append(f'''<div class="frow"><div class="frow-h"><span class="sev sev-{sev[0]}">{SEVZH[i["severity"]]}</span>
          <h4>{E(i["title"]["zh-CN"])}</h4></div>
          <p class="fix">{E(fix)}</p>{body}</div>''')
    return "".join(out)

def annote(t):
    low = str(t).lower()
    if any(k in low for k in ["lorem","massa volutpat","nisi arcu","himenaeos","dolor sit amet","pulvinar"]):
        return '<em class="ann">→ 这是模板自带的拉丁占位假文字</em>'
    if "og:title" in low or "og:description" in low:
        return '<em class="ann">→ 这是分享时的标题/摘要，现在是占位或拼接文本</em>'
    if "placeholder/empty" in low or "empty links" in low:
        return '<em class="ann">→ 这些按钮点了没去处</em>'
    if "0 years" in low or "0 staff" in low or "0 + years" in low or "0 + projects" in low or "0 + countries" in low or "0 total" in low:
        return '<em class="ann">→ 这是数字动画的初始值 0，滚动后由 JS 显示真实数字；AI 爬虫读到的是 0</em>'
    return ''

def code_block(code, lang="HTML"):
    return f'''<div class="codewrap"><div class="codebar"><span class="mono">{E(lang)}</span>
      <button class="copy" type="button">复制代码</button></div><pre class="mono">{E(code)}</pre></div>'''

def finding_page(i, idx, pno, total, section):
    sev = SEV[i["severity"]]
    owner = OWNER.get(i["rule_id"], "贵司确认")
    ocol = OWNER_COLOR.get(owner, "primary")
    fix = CLIENT_FIX.get(i["rule_id"]) or i["recommendation"]["zh-CN"]
    imp = IMPACT_ZH.get(i["rule_id"], "")
    code = CODE.get(i["rule_id"])
    ev = i.get("evidence") or []
    inner = f'''<div class="ptitle"><div><div class="pkicker">关键发现 · {idx:02d}</div><h2>{E(i["title"]["zh-CN"])}</h2>
      <div class="pmeta-line"><span class="owner owner-{ocol}">执行方 · {E(owner)}</span><span>检测证据 {len(ev)} 条</span></div></div>
      <div class="pmeta"><span class="sev sev-{sev[0]}">{sev[1]}</span></div></div>
      {(f'<div class="impact"><b>这对您意味着什么</b><p>{E(imp)}</p></div>') if imp else ''}
      <p class="fix lead-fix">{E(fix)}</p>'''
    if ev:
        inner += '<div class="evrow"><span class="evlab">问题内容原文（典型样本）</span><ul>' + "".join(
            f'<li><code class="mono">{E(e.get("url"))}</code><span>{E(e.get("quote"))}</span>{annote(e.get("quote",""))}</li>' for e in ev[:3]) + '</ul></div>'
    if code:
        inner += '<div class="sublab">给建站商的参考代码<span class="hint">以下代码给技术人员看，可转发建站公司，不必阅读</span></div>' + code_block(code[0], "给建站商的参考代码")
    if i["rule_id"] in EXTRA:
        inner += '<div class="sublab">建议的实体映射</div>' + EXTRA[i["rule_id"]]
    if ev:
        inner += f'<details class="src"><summary>查看全部检测证据（{len(ev)} 条）</summary><ul>' + "".join(
            f'<li><code class="mono">{E(e.get("url"))}</code><span>{E(e.get("quote"))}</span></li>' for e in ev) + '</ul></details>'
    return inner, True

def dim_page(k, name, idx, pno, total):
    v = cs[k]; gv = GRADE_VAR[v["grade"]]; items = dim_issues(k)
    body = dim_rows(items)
    inner = f'''<div class="ptitle"><div><div class="pkicker">分维度评估 · {idx:02d} / 09</div><h2>{E(name)}</h2></div>
      <div class="pmeta"><span class="scorechip c-{gv}"><b>{v["score"]}</b><span>/{v["max"]}</span><em class="g g-{gv}">{E(v["grade"])}</em></span></div></div>
      <div class="mini"><i style="width:{v["percentage"]}%;background:var(--{gv})"></i></div>
      <p class="narr">{E(NARR[k])}</p>
      {('<div class="sublab">本维度主要发现</div>' + body) if body else '<p class="dim-note">本维度本轮未发现需要单独说明的问题。</p>'}
      <div class="callout"><b>提升建议</b><p>{E(IMPROVE[k])}</p></div>'''
    return inner

# ---------- 页面清单 ----------
PAGES = []   # 每项：{"nav": (章号, 标题) | None, "section": str | None, "dark": bool, "render": fn(pno,total)->html}
def add(nav, section, render, dark=False, cls=""):
    PAGES.append({"nav": nav, "section": section, "render": render, "dark": dark, "cls": cls})

top = [i for i in issues if i["severity"] in ("S1", "S2")][:10]

# 01 封面
def r_cover(pno, total):
    return f'''<div class="cover-top"><span class="brand"><span class="mark-slot">{MARK.replace('var(--mark-bg)','#fff').replace('var(--mark-fg)','#312E81')}</span><b>GEO SCORING</b></span>
      <span class="cover-no mono">文件编号 {E(DOC_NO)}</span></div>
      <div class="cover-mid">
        <div class="pkicker light">生成式引擎优化 · 技术与内容准备度评测报告</div>
        <h1>索菲亚官网<br>GEO 评测报告</h1>
        <p class="cover-sub">检查官网有没有把「我们是谁、卖什么、数字从哪来」写清楚——这是 AI 能否读懂、信任并推荐你的基础。</p>
        <div class="cover-score"><div class="cbig">{sc["overall_score"]}<small>/100</small><em>站内准备度 {E(sc["grade"])}</em></div><div>{cover_meter()}<p class="cover-score-note">60 分以下＝准备不足；它不是搜索排名，也不代表 AI 实际提到你的次数。</p></div></div>
      </div>
      <dl class="cover-facts">
        <div class="wide"><dt>站点</dt><dd class="mono">{E(site["url"])}</dd></div>
        <div><dt>报告日期</dt><dd class="mono">{date}</dd></div>
        <div><dt>检测范围</dt><dd>发现 {scope["pages_total"]} 个页面，抽查了 {len(scope["sampled_pages"])} 个重点页</dd></div>
        <div><dt>报告版本</dt><dd class="mono">{E(run["versions"]["methodology_version"])} · 规则 {E(run["versions"]["rules_version"])}</dd></div>
      </dl>
      <div class="cover-sev">{sev_strip()}</div>
      <div class="cover-sign"><span>编制：GEO 评测组</span><span>审核：待签署</span><span>签发：待签署</span><span class="mono">共 {total} 页</span></div><p class="cover-read">只有 5 分钟？看「三分钟看懂」「优先改进建议」「结论与签核」三页即可。</p>'''


# 导读页
def r_guide(pno, total):
    return f'''{page_header(pno, total, "导读")}
      <div class="ptitle"><div><div class="pkicker">导读</div><h2>三分钟看懂这份报告</h2></div></div>
      <div class="nextgrid">
        <div><span class="dimcell-n mono">1 · 查了什么</span><p>检查你的网站在 ChatGPT、豆包、Kimi 等 AI 搜索 / 问答里“能不能被读懂、被信任、被引用”。</p></div>
        <div><span class="dimcell-n mono">2 · {sc["overall_score"]} 分（{E(sc["grade"])}）是什么意思</span><p>不是考试评分、也不是搜索排名——它说的是：网站技术上是通的，但 AI 目前认不准“你是谁”（品牌名、公司名、邮箱各说各话），也不敢信你的内容（页面上还有建站模板留下的假文字）。像一家资质齐全的店，招牌没挂对、橱窗还贴着装修样板。</p></div>
        <div><span class="dimcell-n mono">3 · 为什么要现在管</span><p>买家找供应商，正在从搜索引擎转向直接问 AI。AI 推荐谁，取决于它能不能读懂并信任谁的网站。</p></div>
        <div><span class="dimcell-n mono">4 · 你需要做什么</span><p>大部分问题是一次性遗留问题，集中清一轮就能解决大半。第一件事——统一品牌与邮箱口径——只需贵司内部拍板，其余多数由建站商执行。</p></div>
      </div>
      <div class="sublab">阅读建议</div>
      <div class="readguide">
        <div><b>快速浏览</b><span class="mono">约 3 分钟</span><p>本页 → 总体评价 → 行动清单 → 结论。</p></div>
        <div><b>通读全篇</b><span class="mono">约 30 分钟</span><p>总体评价 → 关键发现 → 待确认内容 → 行动清单。</p></div>
        <div><b>技术落地参考</b><span class="mono">按需</span><p>评分方法、分维度评估、给建站商的参考代码。</p></div>
      </div>'''

# 需要您回答的 8 个问题
def r_questions(pno, total):
    rows = "".join(
        f'<tr><td>{n+1}</td><td><b>{E(ADVISORY_ZH.get(a["rule_id"], a["rule_id"]))}</b><p class="qsub">{E(ADVISORY_Q.get(a["rule_id"], ("","",""))[0])}</p></td><td>{E(ADVISORY_Q.get(a["rule_id"], ("","",""))[1])}</td><td><span class="owner owner-primary">{E(ADVISORY_Q.get(a["rule_id"], ("","",""))[2])}</span></td></tr>'
        for n, a in enumerate(run.get("advisory_issues", [])))
    return f'''{page_header(pno, total, "待确认内容")}
      <div class="ptitle"><div><div class="pkicker">待确认内容</div><h2>待确认内容</h2></div></div>
      <p class="narr">以下信息不影响本次评分，但直接关系到修复能不能落地、结论是否成立。逐条确认后，建站商即可执行。</p>
      <table class="mtable"><thead><tr><th style="width:34px">#</th><th>需要确认的事项</th><th>为什么要确认</th><th>找谁</th></tr></thead><tbody>{rows}</tbody></table>
      <p class="note">其中与上市主体关系相关的事项是本次评分的立论前提，建议优先确认后再实施对外改动。</p>'''

# 术语表
def r_glossary(pno, total):
    rows = "".join(f'<tr><td><b>{E(k)}</b></td><td>{E(v)}</td></tr>' for k, v in GLOSSARY)
    return f'''{page_header(pno, total, "附录 · 术语表")}
      <div class="ptitle"><div><div class="pkicker">附录 · 术语表</div><h2>术语人话对照表</h2></div></div>
      <table class="mtable"><thead><tr><th style="width:30%">报告用词</th><th>人话</th></tr></thead><tbody>{rows}</tbody></table>'''

# Before / After
def r_beforeafter(pno, total):
    return f'''{page_header(pno, total, "附录 · 改完长什么样")}
      <div class="ptitle"><div><div class="pkicker">附录 · 改完长什么样</div><h2>首页首屏 · 改前 / 改后示意</h2></div></div>
      <div class="babx">
        <div class="bab bab-before"><b>改前（现状）</b><p class="mono">Create. Enhance. and Sustain.</p><p>Massa volutpat ridiculus consetetur euismod lobortis potenti…（拉丁占位）</p></div>
        <div class="bab bab-after"><b>改后（示意）</b><p class="mono">Whole-House Custom Cabinetry</p><p>Sofeyia 提供橱柜、衣柜与整装定制，覆盖住宅、酒店与公寓；总部位于广州，并已在槟城、埃尔比勒等市场交付整装项目（数字需核实出处）。</p></div>
      </div>
      <p class="note">以上为排版示意，不构成对具体文案的承诺；实际以贵司确认的口径为准。</p>'''
add(None, None, r_cover, dark=True, cls="cover")
add(None, "三分钟看懂", r_guide)

# 02 目录
def r_index(pno, total):
    rows = ""
    for n, p in enumerate(PAGES[2:], start=3):
        if not p["nav"]: continue
        chap, title = p["nav"]
        rows += f'<li><span class="n mono">{n:02d}</span><a href="#p{n}">{E(title)}</a><span class="dots"></span><span class="c mono">{E(chap)}</span></li>'
    return f'''{page_header(pno, total, "报告索引")}
      <div class="ptitle"><div><div class="pkicker">报告索引</div><h2>目录</h2></div>
      <div class="pmeta mono dim">共 {total} 页</div></div>
      <ol class="toc">{rows}</ol>
      <p class="note">阅读方式：向下滚动或按 ← / → 翻页，按 ESC 打开索引。每页对应一个独立小节。</p>'''
add(None, "报告索引", r_index)

# 03 总体评价
def r_summary(pno, total):
    return f'''{page_header(pno, total, "01 总体评价")}
      <div class="ptitle"><div><div class="pkicker">01 总体评价</div><h2>站内 GEO 准备度：{sc["overall_score"]} 分（{E(sc["grade"])}）</h2></div>
      <div class="pmeta"><span class="scorechip c-danger"><b>{sc["overall_score"]}</b><span>/100</span></span></div></div>
      <p class="narr lead">本站 <b>GEO 站内准备度</b>为 <b>{sc["overall_score"]} 分（{E(sc["grade"])}）</b>：网站在技术基础与信息架构上具备良好起点，但在 <span class="hl">品牌与实体一致性</span>（AI 认不准你是谁）、<span class="hl">内容可信度</span>（AI 不敢把你的话当事实）、<span class="hl">内容可吸收性</span>（内容难被 AI 整段引用）三方面存在明显短板。</p>
      <div class="sublab">本轮问题分布</div>
      <div class="statlist">
        <div><span class="statn">严重级问题 {sevc["S1"]} 项</span>
          <p>全部 {total_issues} 项问题的构成：严重 <b>{sevc["S1"]}</b> · 高 <b>{sevc["S2"]}</b> · 中 <b>{sevc["S3"]}</b> · 低 <b>{sevc["S4"]}</b>。多数问题由同一批模板遗留所致，集中清理一轮即可消除大部分。</p></div>
        <div><span class="statn">集中在两处</span>
          <ul class="bullets">
            <li><b>品牌与实体一致性</b> —— 品牌写法与邮箱域名混用（<span class="mono">Sofeyia / Suofeiya</span>、两个邮箱域名），对外可核验的上市主体未在站内说明。</li>
            <li><b>内容可信度与治理</b> —— 页面残留模板占位文案与演示内容，且缺少可被 AI 独立引用的证据型段落。</li>
          </ul></div>
        <div><span class="statn">影响</span>
          <p>这两类问题会让 AI 与搜索引擎更难确认“<b>品牌是谁、这段话能不能当事实</b>”。至于是否会因此减少被 ChatGPT、豆包、Kimi 等点名，本轮未做引用实测，属于需要后续验证的推断。</p></div>
      </div>
      <div class="callout"><b>一句话结论</b><p>先做内容卫生（清占位、删演示/系统页、统一品牌与邮箱口径），再补真实内容与实体声明；结构化数据是“人话的机器副本”，不应排在最前。</p></div>
      <p class="note">本报告采用新版检测口径，在原有“信号是否存在”的基础上增加了“内容是否正确、建议是否可用”的判定，因此分数与旧版报告不可直接比较。分数衡量的是网站在生成式搜索中被正确理解、信任与引用的准备度，而非排名或流量结果。</p>'''
add(("01", "总体评价"), "01 总体评价", r_summary)

# 04 表现良好
def r_strengths(pno, total):
    items = "".join(f"<li>{E(s)}</li>" for s in strengths)
    return f'''{page_header(pno, total, "02 表现良好")}
      <div class="ptitle"><div><div class="pkicker">02 表现良好的部分</div><h2>已有基础</h2></div></div>
      <ul class="plain">{items}</ul>
      <p class="note">以上为检测中确认可用的既有基础，建议在后续改动中保持。</p>'''
add(("02", "表现良好的部分"), "02 表现良好", r_strengths)

# 04 评分方法（可复现）
def r_method(pno, total):
    raw = sm["raw_dimension_scores"]; mx = sm["max"]; ceil = sm["trust_ceiling"]; caps = ceil["caps"]
    pre = sm.get("raw_before_ceiling", raw)
    dim_rows_ = "".join(
        f'<tr><td>{E(name)}</td><td class="num mono">{num(raw[k])}</td><td class="dim mono">/{mx[k]}</td><td class="dim mono r">{E(cs[k]["grade"])}</td></tr>'
        for k, name in DIMS)
    base = sm["base_score"]; ov = sm["overall_score"]
    trig = "、".join(ceil["triggers"])
    # 约束前 → 约束后 对照（P0-2 可复算）
    adj_rows = ""
    for k, label, note in [
        ("trust", "信任度", "上限生效：原始分高于上限 7，压至 7"),
        ("entity", "品牌与实体", "下限生效：原始分已低于上限 4，按从宽下限计 4"),
        ("quality", "内容质量", "下限生效：按从宽下限计 1"),
        ("on_page", "页面主题", "下限生效：按从宽下限计 2")]:
        p = pre.get(k, raw[k]); r = raw[k]
        if p == r:
            continue
        adj_rows += f'<tr><td>{E(label)}</td><td class="num mono">{num(p)}</td><td class="num mono">{num(r)}</td><td>{E(note)}</td></tr>'
    return f'''{page_header(pno, total, "01 总体评价 · 评分方法")}
      <div class="ptitle"><div><div class="pkicker">01 总体评价 · 评分方法</div><h2>站内准备度 {ov} 分是怎么算出来的</h2>
        <div class="pmeta-line"><span>口径 {E(sm.get("calibration_version", "v2026.09"))}</span><span>全部数值取自本次评分记录，可逐项核对</span></div></div>
        <div class="pmeta"><span class="scorechip c-danger"><b>{ov}</b><span>/100</span></span></div></div>
      <div class="method">
        <div>
          <span class="statn">第 1 步 · 九个维度得分（上限内计分）</span>
          <table class="mtable"><thead><tr><th>维度</th><th>得分</th><th>满分</th><th class="r">等级</th></tr></thead>
          <tbody>{dim_rows_}<tr class="total"><td>维度合计（＝基础分）</td><td class="num mono">{num(base)}</td><td class="dim mono">/100</td><td class="r"></td></tr></tbody></table>
          <p class="note">维度得分可回看第 04 节；合计 {num(base)} 分即评分记录中的基础分。</p>
        </div>
        <div>
          <div class="stepbox"><span class="statn">第 2 步 · 上限与下限约束</span>
            <p>触发条件（{E(sm.get("calibration_version", "v2026.09"))} 口径）：<b>未声明实体映射</b> —— 品牌写法与邮箱域名不一致，且组织信息（Organization）缺少官方账号（sameAs）/ 别名（alternateName）等实体关联声明（<span class="mono">{E(trig)}</span>）。</p>
            <p>约束：信任度 ≤ {num(mx["trust"]*caps["trust_max_pct"]//100)} 分、品牌与实体 ≤ {num(mx["entity"]*caps["entity_max_pct"]//100)} 分、总分 ≤ {caps["overall_max"]} 分；从宽下限：品牌与实体 ≥ 4、内容质量 ≥ 1、页面主题 ≥ 2。</p>
            <table class="mtable"><thead><tr><th>维度</th><th>约束前</th><th>约束后</th><th>说明</th></tr></thead><tbody>{adj_rows}</tbody></table>
            <p>完成实体映射声明（名称 / 别名 / 官方账号 / 母公司）后，信任上限解除，信任度可回补至约束前的 {num(pre.get("trust", raw["trust"]))} 分。</p></div>
          <div class="stepbox"><span class="statn">第 3 步 · 计算</span>
            <p class="calc mono">九个维度合计 = <b>{ov}</b> / 100（{E(sm["grade"])}）</p>
            <p>治理扣分已并入各维度得分（同一根因只计一次），总分即九个维度之和，不再单列扣分项。</p></div>
        </div>
      </div>
      <p class="note">等级映射：A+ 90 分以上 · A 80–89 · B 70–79 · C 60–69 · D 60 分以下。分数用于定位短板与排序修复优先级，不用于横向比较其它站点。</p>
      <div class="sublab">口径边界与阈值来源</div>
      <ul class="plain">
        <li>本分数是<b>站内 GEO 准备度（技术与内容准备度）</b>：衡量站点被生成式搜索正确理解、信任与引用的准备情况，</li>
        <li>标题/元描述长度、每页标题数量等为<b>卫生项</b>，用作统一检查口径，不是搜索引擎硬性要求；内容是否“能整块被引用、且带可核验事实”才是关键。</li>
        <li>官方口径核对：Google 说明元描述无固定长度限制（超出仅在展示时截断）；结构化数据不是通用排名因子；FAQ 富媒体结果已于 2026-05-07 停止展示（HowTo 于 2023 年退役）；FAQPage 标记仍然有效，但主要供大模型读取而非争取富结果；组织信息（Organization）的官方账号（sameAs）/ 联系方式（contactPoint）属“适用时推荐”而非必填。</li>
        <li>本报告口径为 <b>v1.1</b>：可吸收性按 <b>Citability 五子项</b>衡量（可引用块率 + 证据块覆盖 + 直接回答 + 结构化答案资产 + 对题度，20 分制 ×0.75 折算到 15 分）——既要段落自包含、可整段摘走，也要有定义 / 数据 / 对比 / 步骤这类可核验的事实；<b>模板占位 / 索引膨胀等治理问题已并入对应维度扣分，同一根因只计一次</b>；FAQ 结构化数据列为推荐项、不计分。因口径调整，分数与历史版本不可直接比较。</li>
      </ul>'''
add(("01", "评分方法（可复现）"), "01 总体评价 · 评分方法", r_method)

# 05 关键发现（章首）
def r_findings_head(pno, total):
    rows = ""
    for n, i in enumerate(top, start=1):
        sev = SEV[i["severity"]]
        rows += f'''<li><span class="n mono">{n:02d}</span><span class="sev sev-{sev[0]}">{SEVZH[i["severity"]]}</span>
          <a href="#p{pno + n}">{E(i["title"]["zh-CN"])}</a><span class="dots"></span></li>'''
    return f'''{page_header(pno, total, "03 关键发现")}
      <div class="ptitle"><div><div class="pkicker">03 关键发现</div><h2>本轮最需要优先处理的 {len(top)} 项问题</h2></div>
      <div class="pmeta mono dim">按影响程度排序</div></div>
      <ol class="toc">{rows}</ol>
      <p class="note">每条问题单独成页，含问题原文与修复建议，部分附可直接套用的示例（示例仅供参考，请替换占位信息）。</p>'''
add(("03", "关键发现"), "03 关键发现", r_findings_head)

# 06-15 每条关键发现一页
for n, i in enumerate(top, start=1):
    def mk(i=i, n=n):
        def r(pno, total):
            inner, _ = finding_page(i, n, pno, total, "")
            return page_header(pno, total, f"03 关键发现 · {n:02d}") + inner
        return r
    add(("03", f'关键发现 {n:02d} · {i["title"]["zh-CN"]}'), f"03 关键发现 · {n:02d}", mk())

# 16 分维度总览
def r_dims_head(pno, total):
    return f'''{page_header(pno, total, "04 分维度评估")}
      <div class="ptitle"><div><div class="pkicker">04 分维度评估</div><h2>9 个维度得分与提升空间</h2></div>
      <div class="pmeta mono dim">满分 {sum(v["max"] for v in cs.values())} 分</div></div>
      {O.dim_chart()}
      <div class="dimgrid">{"".join(f'<a class="dimcell" href="#p{pno + n}"><span class="dimcell-n mono">{n:02d}</span><b>{E(name)}</b><span class="dimcell-s c-{GRADE_VAR[cs[k]["grade"]]}">{cs[k]["score"]}/{cs[k]["max"]} · {E(cs[k]["grade"])}</span></a>' for n, (k, name) in enumerate(DIMS, start=1))}</div>'''
add(("04", "分维度评估"), "04 分维度评估", r_dims_head)

# 17-25 每个维度一页
for n, (k, name) in enumerate(DIMS, start=1):
    def mk(k=k, name=name, n=n):
        def r(pno, total):
            return page_header(pno, total, f"04 分维度 · {n:02d} / 09") + dim_page(k, name, n, pno, total)
        return r
    add(("04", f'维度 {n:02d} · {name}'), f"04 分维度 · {n:02d}", mk())

# 26 优先改进建议
def r_actions(pno, total):
    rows = "".join(
        f'<div class="arow"><div><h4>{E(a)}</h4><p>{E(b)}</p></div>'
        f'<span class="owner owner-{OWNER_COLOR.get(c.split(" + ")[0], "primary")}">{E(c)}</span>'
        f'<span class="cycle">{E(dd)}</span>'
        f'<span class="done">{E(ee)}</span></div>' for a, b, c, dd, ee in actions)
    return f'''{page_header(pno, total, "06 优先改进建议")}
      <div class="ptitle"><div><div class="pkicker">06 优先改进建议</div><h2>按优先级排列的行动清单</h2></div></div>
      <p class="narr">预期：完成第 1–2 步后，本报告口径的分数约可到 60 分以上；全部完成后约 80 分左右。<b>此为方向性预估，仅反映本量表的扣分项消失，不保证 AI 实际引用增加。</b></p>
      <div class="actions">{rows}</div>
      <p class="note">“完成标准”即改完后的样子，用于验收；分数留给内部复测。建立实体映射是解除评分上限的前提。</p>'''
add(("05", "待确认内容"), "05 待确认内容", r_questions)
add(("06", "优先改进建议"), "06 优先改进建议", r_actions)

# 8 个问题的“后果 / 找谁”
ADVISORY_Q = {
 "ABS-03":("关键数据（营收/净利/项目等）能否对外公开、出处是什么？","否则 AI 不敢把这些数字当事实引用","贵司 / 财务"),
 "CIT-02":("关键声明与数字的出处在哪里？","标注来源才能让 AI 敢引用","贵司 / 品牌"),
 "CIT-03":("贵司与上市公司（002572.SZ）及子品牌的关系是什么？","讲清楚才能把上市背景这笔资产用起来","贵司 / 法务"),
 "ENT-05":("社交账号的命名是否统一、归属是谁？","账号不一致会让 AI 认不准","贵司 / 品牌"),
 "QLT-03":("“China's No.1 / The ONLY”等表述能否保留、依据是什么？","无依据的绝对化用语有广告法风险","法务"),
 "SCH-01":("FAQ 结构化数据是否要做？（推荐项、不计分）","可不做；做了只是锦上添花","建站商"),
 "TLS-APEX":("不带 www 的网址打不开（证书不匹配），是否要修复？","客户输入不带 www 会打不开，可能以为网站关闭","建站商（10 分钟）"),
 "TRU-04":("CNAS 认证、20 年外贸经验等资质能否提供出处？","无出处的资质表述 AI 不敢信","贵司 / 品牌"),
}
GLOSSARY = [
 ("GEO / 生成式引擎优化","让 ChatGPT、豆包、Kimi 这类 AI 在回答问题时能找到你、说对你、引用你"),
 ("站内准备度 / D 等级","网站在 AI 眼里“读不读得懂、敢不敢信”；60 分以下＝准备不足，不是搜索排名"),
 ("实体 / 实体映射","“你这家公司到底是谁”；映射＝把各种名字/域名/账号都指向同一家"),
 ("结构化数据 / schema","写在网页里、专门给机器看的“公司名片”，人看不见、AI 会读"),
 ("答案可吸收性 / 证据块","网站上有没有“一整段能当答案的干货”（带事实，不靠空口号）"),
 ("开放图谱 / 元描述","链接转发到微信/WhatsApp 时显示的卡片；搜索结果标题下那两行小字"),
 ("H1 / 站点地图 / 索引膨胀","每页最大的标题（一页一个）；交给搜索引擎的“全书目录”；目录里混进了没内容的模板页"),
 ("Lorem ipsum","建站模板自带的占位假文字，等于空招牌"),
 ("canonical / robots.txt","告诉机器“正式地址是哪个”“谁可以进来读”"),
 ("扣分项可恢复","这些扣分项消失后，我们这份量表上的分会上去；不保证 AI 更常提到你"),
]

ADVISORY_ZH = {
 "ABS-03":"关键数据缺少来源标注（营收/净利/项目数据等）",
 "CIT-02":"关键声明与数字未标注来源",
 "CIT-03":"站内品牌与外部可核验上市主体（002572.SZ）的关系待贵司确认",
 "ENT-05":"社交账号命名不一致（属运营策略，可保留并写入官方账号声明）",
 "QLT-03":"无出处的绝对化表述（China's No.1 / The ONLY 等，有广告法风险）",
 "SCH-01":"FAQ 结构化数据（推荐项，不计分）",
 "TLS-APEX":"顶级域名证书主机名不匹配（仅 www 可用）",
 "TRU-04":"资质/经验表述缺少可验证出处（CNAS 认证、20 年外贸经验等）",
}
def r_scope(pno, total):
    return f'''{page_header(pno, total, "07 检测范围")}
      <div class="ptitle"><div><div class="pkicker">07 检测范围</div><h2>抓取范围与页面构成</h2></div></div>
      <p class="narr">域名 <span class="mono">{E(site["domain"])}</span> 共发现 {scope["pages_total"]} 个页面；本次抽查了 {len(scope["sampled_pages"])} 个重点页，覆盖首页、关于、联系、FAQ、新闻与文章、产品、项目、条款以及模板演示与系统页。</p>
      {O.scope_bar()}
      <p class="note">检测基于 {date} 的站点快照；页面内容或结构更新后，结论需重新核验。需贵司确认的信息见「待确认内容」页。</p>'''
add(("07", "检测范围"), "07 检测范围", r_scope)

# 28 结论与签核
def r_signoff(pno, total):
    return f'''{page_header(pno, total, "08 结论与签核")}
      <div class="ptitle"><div><div class="pkicker">08 结论与签核</div><h2>结论与后续步骤</h2></div>
      <div class="pmeta"><span class="scorechip c-danger"><b>{sc["overall_score"]}</b><span>/100</span></span></div></div>
      <p class="narr lead">本站当前 <b>GEO 站内准备度 {sc["overall_score"]} 分（{E(sc["grade"])}）</b>。技术可用性良好，主要缺口集中在品牌与实体一致性、内容可信度、内容可吸收性三处；这三项会让 AI 更难确认“品牌是谁、内容能不能当事实”。</p>
      <div class="nextgrid">
        <div><span class="dimcell-n mono">第一步</span><b>确认主体口径</b><p>由贵司书面确认与上市主体（002572.SZ）及子品牌的关系、品牌标准写法与主用邮箱。</p></div>
        <div><span class="dimcell-n mono">第二步</span><b>先清卫生再补内容</b><p>删占位与演示/系统页、统一页脚邮箱，再补充能回答买家问题的真实内容。</p></div>
        <div><span class="dimcell-n mono">第三步</span><b>复测核验</b><p>修复后复测本报告口径，看分数与问题是否改善（复测如何预约见文末）。</p></div>
      </div>
      <div class="callout"><b>改完大概到多少分</b><p>按本报告口径估算：完成第一、二步后约可到 60 分以上，全部完成后约 80 分左右。<b>这是方向性预估，只表示扣分项消失，不保证 AI 实际引用增加。</b></p></div>
      <div class="callout"><b>接下来找谁</b><p>如需修复后的复测，或了解 AI 实际引用情况的专项评测，请联系我们预约。</p></div>
      <div class="signblock">
        <div class="signrow"><span class="signlab">编制</span><span class="signline"></span><span class="signmeta mono">GEO 评测组</span></div>
        <div class="signrow"><span class="signlab">审核</span><span class="signline"></span><span class="signmeta mono">日期：____ / ____ / ____</span></div>
        <div class="signrow"><span class="signlab">客户确认</span><span class="signline"></span><span class="signmeta mono">日期：____ / ____ / ____</span></div>
      </div>
      <p class="note">文件编号 {E(DOC_NO)}　·　报告版本 {E(run["versions"]["methodology_version"])}　·　规则 {E(run["versions"]["rules_version"])}</p>'''
add(("08", "结论与签核"), "08 结论与签核", r_signoff)
add(("附录", "术语人话对照表"), "附录 · 术语表", r_glossary)
add(("附录", "改完长什么样"), "附录 · 改完长什么样", r_beforeafter)


# ---------- 渲染 ----------
N = len(PAGES)
body = []
for n, p in enumerate(PAGES, start=1):
    inner = p["render"](n, N)
    if not p["dark"]:
        inner += page_footer()
    cls = "page" + (" page-dark" if p["dark"] else "") + (" " + p["cls"] if p["cls"] else "")
    body.append(f'<section class="{cls}" id="p{n}" data-page="{n}" aria-label="第 {n} 页，共 {N} 页">{inner}</section>')
index_items = "".join(
    f'<a href="#p{n}"><span class="mono">{n:02d}</span>{E(p["nav"][1])}</a>' for n, p in enumerate(PAGES, start=1) if p["nav"])

CSS = r'''
:root{
 --primary:#4F46E5;--primary-hover:#4338CA;--primary-light:#EEF2FF;--primary-dim:rgba(79,70,229,.08);
 --bg:#E9EDF4;--surface:#FFFFFF;--surface-2:#F7F9FC;--surface-3:#E8EEF5;--border:#E2E8F0;--border-2:#CBD5E1;
 --text:#0F172A;--text-2:#475569;--text-3:#5E6C7F;
 --success:#15803D;--warning:#D97706;--danger:#DC2626;--info:#0284C7;--muted:#64748B;
 --mark-bg:#4F46E5;--mark-fg:#fff;
 --font-sans:Geist,"Geist Sans",-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
 --font-mono:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 --space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:24px;--space-6:32px;--space-7:48px;--space-8:64px;
 --page-w:1080px;--page-pad:40px 44px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-sans);font-size:16px;line-height:1.72;
 letter-spacing:-.003em;-webkit-font-smoothing:antialiased;padding-bottom:var(--space-8)}
h1,h2,h3,h4{font-weight:650;letter-spacing:-.015em}
::selection{background:var(--primary-light);color:var(--text)}
pre::selection,pre *::selection,code::selection,.codebar::selection{background:#475569;color:#fff}
a{color:var(--primary);text-decoration:none}
a:focus-visible,summary:focus-visible,button:focus-visible{outline:2px solid var(--primary);outline-offset:2px;border-radius:3px}
.mono,code,pre,.pgnum,.fnum{font-family:var(--font-mono);font-variant-numeric:tabular-nums}
.dim{color:var(--text-3)}
/* ---------- top bar ---------- */
.docfoot{max-width:var(--page-w);margin:0 auto;padding:18px 22px 0;color:var(--text-3);font-size:12.5px;text-align:center}
.topbar{position:sticky;top:0;z-index:30;background:rgba(233,237,244,.92);backdrop-filter:saturate(1.4) blur(6px);
 border-bottom:1px solid var(--border)}
.topbar-in{max-width:var(--page-w);margin:0 auto;padding:11px 22px;display:flex;align-items:center;gap:var(--space-4)}
.topbar .brand{display:flex;align-items:center;gap:9px;font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--primary);font-weight:700}
.topbar .mark{width:22px;height:22px}
.topbar .doc{font-size:13px;color:var(--text-2)}
.topbar .right{margin-left:auto;display:flex;align-items:center;gap:var(--space-4);font-size:13px;color:var(--text-3)}
.topbar .now b{color:var(--text)}
.btn{font:inherit;font-size:12.5px;color:var(--text-2);background:var(--surface);border:1px solid var(--border-2);
 border-radius:6px;padding:4px 10px;cursor:pointer}
.btn:hover{border-color:var(--primary);color:var(--primary)}
.progress{height:2px;background:transparent}
.progress i{display:block;height:2px;width:0;background:var(--primary)}
/* ---------- deck ---------- */
.deck{max-width:var(--page-w);margin:0 auto;padding:var(--space-6) 22px 0;display:grid;gap:32px}
.page{position:relative;background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:var(--page-pad);
 box-shadow:0 1px 2px rgba(15,23,42,.04),0 22px 44px -36px rgba(15,23,42,.42);min-height:600px;display:flex;flex-direction:column}
.page-dark{background:#1E1B4B;border-color:#1E1B4B;color:#fff;--text:#fff;--text-2:#C7D2FE;--text-3:#A5B4FC;
 --surface:#312E81;--surface-2:#312E81;--surface-3:rgba(255,255,255,.16);--border:rgba(255,255,255,.22);--border-2:rgba(255,255,255,.32);
 --mark-bg:#fff;--mark-fg:#312E81;--primary:#C7D2FE}
/* page header */
.ph{display:flex;align-items:center;gap:10px;padding-bottom:12px;border-bottom:1px solid var(--border);font-size:12.5px;color:var(--text-3)}
.ph .brand{display:flex;align-items:center;gap:7px;color:var(--primary);font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.ph .mark{width:18px;height:18px}
.ph .ph-sec{color:var(--text-2)}
.ph .ph-right{margin-left:auto;display:flex;gap:14px;align-items:center}
.ph .pgnum{color:var(--text)}
.pf{margin-top:auto;padding-top:14px;border-top:1px solid var(--border);display:flex;justify-content:space-between;
 font-size:11.5px;color:var(--text-3)}
/* page titles */
.ptitle{display:flex;justify-content:space-between;align-items:flex-start;gap:var(--space-6);margin:var(--space-5) 0 0}
.pkicker{font-size:11.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--primary);font-weight:600;margin-bottom:8px}
.pkicker.light{color:#C7D2FE}
.ptitle h2{font-size:clamp(22px,2.5vw,29px);line-height:1.32;margin:0;text-wrap:balance}
.pmeta{display:flex;align-items:center;gap:var(--space-3);flex-shrink:0;flex-wrap:wrap;justify-content:flex-end}
.pmeta-line{display:flex;gap:var(--space-4);margin-top:9px;font-size:12.5px;color:var(--text-3);flex-wrap:wrap}
.gain{color:var(--success);font-weight:700;font-size:13.5px;white-space:nowrap;font-family:var(--font-mono)}
.gain.dim{color:var(--text-3);font-weight:500}
.sev{font-size:11px;letter-spacing:.09em;padding:2px 7px;border-radius:3px;color:#fff;font-weight:600;white-space:nowrap}
.sev-danger{background:var(--danger)}.sev-warning{background:var(--warning)}.sev-info{background:var(--info)}.sev-muted{background:var(--muted)}
.scorechip{display:flex;align-items:baseline;gap:3px;font-family:var(--font-mono)}
.scorechip b{font-size:26px;line-height:1}.scorechip span{color:var(--text-3);font-size:13px}
.g{font-style:normal;font-size:11.5px;letter-spacing:.08em;border:1px solid currentColor;border-radius:3px;padding:0 5px;margin-left:6px}
.g-success{color:var(--success)}.g-info{color:var(--info)}.g-warning{color:var(--warning)}.g-danger{color:var(--danger)}
.c-success{color:var(--success)}.c-info{color:var(--info)}.c-warning{color:var(--warning)}.c-danger{color:var(--danger)}
.mini{margin-top:var(--space-4);height:4px;background:var(--surface-3);border-radius:2px;overflow:hidden}
.mini i{display:block;height:100%}
/* text */
.narr{color:var(--text-2);max-width:56em;margin:var(--space-4) 0 0;font-size:16.5px}
.narr.lead{font-size:19px;line-height:1.72;color:var(--text);max-width:48em;margin-top:var(--space-5)}
.narr b{color:var(--text)}
.fix{color:var(--text-2);margin:6px 0 0;max-width:56em}
.lead-fix{font-size:17px;margin-top:var(--space-4)}
.note{color:var(--text-3);font-size:13px;margin-top:var(--space-5)}
.dim-note{color:var(--text-3);margin-top:var(--space-4)}
.sublab{margin:var(--space-6) 0 0;font-size:11.5px;letter-spacing:.18em;text-transform:uppercase;color:var(--text-3);
 padding-bottom:8px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;gap:var(--space-4)}
.sublab .hint{text-transform:none;letter-spacing:0;font-size:12px}
/* toc */
ol.toc{list-style:none;margin:var(--space-5) 0 0;padding:0}
ol.toc li{display:flex;align-items:baseline;gap:var(--space-3);padding:9px 0;border-bottom:1px solid var(--border);font-size:15.5px}
ol.toc .n{font-size:12px;color:var(--text-3);min-width:22px}
ol.toc a{color:inherit;flex:0 1 auto}
ol.toc a:hover{color:var(--primary)}
ol.toc .dots{flex:1;border-bottom:1px dotted var(--border-2);transform:translateY(-4px)}
ol.toc .c{font-size:12px;color:var(--text-3)}
ul.plain{list-style:none;margin:var(--space-5) 0 0;padding:0;max-width:60em}
ul.plain li{position:relative;padding:10px 0 10px 26px;border-top:1px solid var(--border);color:var(--text-2)}
ul.plain li:first-child{border-top:0}
ul.plain li::before{content:"";position:absolute;left:4px;top:19px;width:7px;height:7px;border-radius:50%;background:var(--success)}
/* findings rows */
.frow{padding:var(--space-4) 0;border-top:1px solid var(--border)}
.frow:first-of-type{border-top:0}
.frow-h{display:flex;align-items:baseline;gap:var(--space-3);flex-wrap:wrap}
.frow h4{margin:0;font-size:17px;line-height:1.45}
.frow-h .gain{margin-left:auto}
.evrow{margin-top:var(--space-4)}
.evlab{display:block;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--text-3);margin-bottom:6px}
.evrow ul{margin:0;padding:0;list-style:none;border-top:1px solid var(--border)}
.evrow li{display:grid;grid-template-columns:1fr;gap:2px;padding:8px 0;border-bottom:1px solid var(--border)}
.evrow code{font-size:12px;color:var(--primary);word-break:break-all}
.evrow span{font-size:14.8px;color:var(--text)}
details.src{margin-top:var(--space-4)}
details summary{cursor:pointer;list-style:none;font-size:13.5px;color:var(--primary);display:flex;gap:8px;align-items:baseline}
details summary::-webkit-details-marker{display:none}
details summary::before{content:"▸";font-size:12px;color:var(--text-3)}
details[open] summary::before{content:"▾"}
details.src ul{margin:var(--space-3) 0 0;padding:0;list-style:none}
details.src li{padding:6px 0;border-top:1px dotted var(--border);display:grid;gap:2px}
details.src code{font-size:11.5px;color:var(--primary);word-break:break-all}
details.src span{font-size:14px;color:var(--text-2)}
/* code */
.codewrap{margin:var(--space-4) 0 0;border:1px solid #0F172A;border-radius:10px;overflow:hidden;background:#0F172A}
.codebar{display:flex;align-items:center;justify-content:space-between;gap:var(--space-4);padding:8px 12px;
 border-bottom:1px solid rgba(255,255,255,.12);color:#94A3B8;font-size:11px;letter-spacing:.14em;text-transform:uppercase}
.copy{font:inherit;font-size:11.5px;letter-spacing:.04em;text-transform:none;color:#E2E8F0;background:rgba(255,255,255,.1);
 border:1px solid rgba(255,255,255,.22);border-radius:6px;padding:3px 10px;cursor:pointer}
.copy:hover{background:rgba(255,255,255,.18)}
pre{margin:0;color:#E2E8F0;padding:var(--space-4);overflow:auto;font-size:12.6px;line-height:1.7;white-space:pre-wrap}
.callout{margin-top:var(--space-5);padding:var(--space-4) var(--space-5);background:var(--primary-light);border-radius:10px}
.callout b{display:block;font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--primary-hover);margin-bottom:4px}
.callout p{margin:0;color:var(--text);max-width:56em}
.page-dark .callout{background:rgba(255,255,255,.1)}
/* actions */
.actions{margin-top:var(--space-5);border-top:2px solid var(--text)}
.arow{display:grid;grid-template-columns:minmax(200px,1.5fr) auto auto 1.2fr;gap:var(--space-4);padding:var(--space-4) 0;border-bottom:1px solid var(--border);align-items:start}
.arow h4{margin:0;font-size:16px}
.arow p{margin:4px 0 0;color:var(--text-2);font-size:14px}
.cycle{font-size:13px;color:var(--text-2);white-space:nowrap}
.done{font-size:13px;color:var(--text-2)}
.arow h4{margin:0;font-size:16px}
.arow p{margin:0;color:var(--text-2);font-size:14.5px}
.arow .gain{text-align:right}
/* dim grid */
.dimgrid{margin-top:var(--space-6);display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:0;background:var(--surface);
 border:1px solid var(--border);border-radius:12px;overflow:hidden}
.dimcell{display:flex;flex-direction:column;gap:3px;padding:var(--space-4);background:var(--surface);color:inherit;
 box-shadow:inset -1px -1px 0 var(--border)}
.dimcell:hover{background:var(--surface-2)}
.dimcell-n{font-size:11px;color:var(--text-3);letter-spacing:.1em}
.dimcell b{font-size:15px}
.dimcell-s{font-size:13px;font-family:var(--font-mono)}
/* next steps */
.nextgrid{margin-top:var(--space-6);display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:var(--space-5)}
.nextgrid>div{padding-top:var(--space-4);border-top:2px solid var(--text)}
.nextgrid b{display:block;font-size:16px;margin:4px 0 4px}
.nextgrid p{margin:0;color:var(--text-2);font-size:14.5px}
/* sign block */
.signblock{margin-top:var(--space-7);border-top:1px solid var(--border)}
.signrow{display:grid;grid-template-columns:88px 1fr auto;gap:var(--space-4);align-items:end;padding:var(--space-5) 0;
 border-bottom:1px solid var(--border)}
.signlab{font-size:13.5px;color:var(--text-2)}
.signline{border-bottom:1px solid var(--border-2);height:26px}
.signmeta{font-size:12px;color:var(--text-3)}
/* cover */
.cover{justify-content:space-between;background:#1E1B4B;border-color:#1E1B4B;color:#fff;
 --text:#fff;--text-2:#C7D2FE;--text-3:#A5B4FC;--surface:rgba(255,255,255,.08);--surface-2:rgba(255,255,255,.08);
 --surface-3:rgba(255,255,255,.2);--border:rgba(255,255,255,.2);--border-2:rgba(255,255,255,.34);
 --mark-bg:#fff;--mark-fg:#312E81;--primary:#C7D2FE}
.cover-top{display:flex;align-items:center;justify-content:space-between;gap:var(--space-4)}
.cover-top .brand{display:flex;align-items:center;gap:9px;font-size:13px;letter-spacing:.16em;text-transform:uppercase;font-weight:700}
.cover-top .mark{width:22px;height:22px}
.cover-no{font-size:12px;color:#A5B4FC}
.cover-mid{margin:var(--space-8) 0}
.cover h1{font-size:clamp(34px,5vw,54px);line-height:1.14;letter-spacing:-.03em;margin:0 0 var(--space-3);font-weight:700}
.cover-sub{font-size:17.5px;color:#C7D2FE;margin:0 0 var(--space-7);max-width:32em}
.cover-score{display:grid;grid-template-columns:auto 1fr;gap:var(--space-7);align-items:center;border-top:1px solid rgba(255,255,255,.22);padding-top:var(--space-6)}
.cbig{font-size:78px;line-height:.9;font-weight:700;letter-spacing:-.04em}
.cbig small{font-size:22px;color:#A5B4FC;font-weight:500;letter-spacing:0}
.cbig em{display:block;font-style:normal;font-size:12.5px;letter-spacing:.16em;text-transform:uppercase;color:#A5B4FC;margin-top:8px}
.cmeter{min-width:260px}
.cm-track{height:10px;border-radius:2px;background:rgba(255,255,255,.2);overflow:hidden}
.cm-fill{display:block;height:100%;background:#fff}
.cm-scale{display:flex;justify-content:space-between;margin-top:8px;font-size:11.5px;color:#A5B4FC;font-family:var(--font-mono)}
.cover-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:var(--space-4) var(--space-6);
 border-top:1px solid rgba(255,255,255,.22);padding-top:var(--space-5);margin:0}
.cover-facts dt{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#A5B4FC;margin-bottom:5px}
.cover-facts dd{margin:0;font-size:15px;min-width:0;overflow-wrap:anywhere}
.cover-facts>div{min-width:0}
.cover-facts .wide{grid-column:1/-1}
.cover-facts dd.mono{font-size:13.5px;color:#E0E7FF}
.cover-sev{margin-top:var(--space-5)}
.cover-sign{margin-top:var(--space-6);padding-top:var(--space-4);border-top:1px solid rgba(255,255,255,.22);
 display:flex;gap:var(--space-6);flex-wrap:wrap;font-size:12.5px;color:#C7D2FE}
.cover-sign span:last-child{margin-left:auto}
.cover-score-note{margin:10px 0 0;font-size:13.5px;color:#C7D2FE;max-width:52ch}
.cover-read{margin-top:var(--space-4);font-size:13px;color:#C7D2FE}
/* severity strip (shared) */
.sevstrip{margin-top:var(--space-4)}
.ss-track{display:flex;height:10px;border-radius:2px;overflow:hidden;background:var(--surface-3)}
.ss{display:block;height:100%}
.ss-danger{background:var(--danger)}.ss-warning{background:var(--warning)}.ss-info{background:var(--info)}.ss-muted{background:var(--muted)}
.ss-legend{display:flex;flex-wrap:wrap;gap:var(--space-5);margin-top:10px;font-size:12.5px;color:var(--text-2)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.d-danger{background:var(--danger)}.d-warning{background:var(--warning)}.d-info{background:var(--info)}.d-muted{background:var(--muted)}.d-primary{background:var(--primary)}.d-success{background:var(--success)}
.muted{color:var(--text-3)}
/* charts (from v2) */
.chart{margin:var(--space-6) 0 0}
.lc{display:grid;gap:10px}
.lc-row{display:grid;grid-template-columns:150px 1fr 92px;gap:var(--space-4);align-items:center}
.lc-name{font-size:14px;color:var(--text-2);text-align:right}
.lc-track{display:flex;height:10px;background:var(--surface-3);border-radius:2px;overflow:hidden}
.lc-fill{display:block;height:100%}
.lc-space{display:block;height:100%;background:repeating-linear-gradient(90deg,transparent 0 3px,color-mix(in oklab,var(--border-2) 55%,transparent) 3px 5px)}
.lc-val{font-size:13.5px;color:var(--text-3)}.lc-val b{font-size:15px;color:var(--text)}
figcaption{margin-top:var(--space-4);font-size:13px;color:var(--text-3);max-width:58em}
/* summary stat list */
.statlist{margin-top:var(--space-4);display:grid;gap:var(--space-5);max-width:60em}
.statlist>div{padding-top:var(--space-4);border-top:2px solid var(--text)}
.statn{display:block;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--primary);margin-bottom:6px}
.statlist p{margin:0;color:var(--text-2)}
.statlist b{color:var(--text)}
ul.bullets{margin:4px 0 0;padding:0;list-style:none}
ul.bullets li{position:relative;padding:6px 0 6px 18px;color:var(--text-2)}
ul.bullets li::before{content:"";position:absolute;left:2px;top:16px;width:6px;height:6px;border-radius:50%;background:var(--primary)}
.hl{background:var(--primary-light);border-radius:3px;padding:0 4px;font-weight:650;color:var(--text)}
/* scoring method page */
.wchip{font-size:12.5px;color:var(--text-2);border:1px solid var(--border-2);border-radius:999px;padding:2px 10px;white-space:nowrap}
.method{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-7);margin-top:var(--space-5)}
.stepbox{margin-bottom:var(--space-5)}
.stepbox p{margin:6px 0 0;color:var(--text-2);max-width:52em}
.mtable{width:100%;border-collapse:collapse;margin-top:var(--space-3);font-size:14.5px}
.mtable th{text-align:left;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--text-3);font-weight:600;
 padding:0 10px 7px 0;border-bottom:1px solid var(--border-2)}
.mtable td{padding:8px 10px 8px 0;border-bottom:1px solid var(--border);vertical-align:top}
.mtable td.num{font-weight:650;text-align:right}
.mtable tr.total td{border-top:2px solid var(--text);border-bottom:0;font-weight:650}
.mtable th.r,.mtable td.r{text-align:right;padding-right:0}
.calc{font-size:16.5px;color:var(--text);margin-top:8px}
.calc b{font-size:19px}
.readguide{margin-top:var(--space-4);display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:var(--space-5)}
.readguide>div{padding-top:var(--space-4);border-top:2px solid var(--text)}
.readguide b{display:block;font-size:16px}
.readguide .mono{font-size:12px;color:var(--text-3)}
.readguide p{margin:4px 0 0;color:var(--text-2);font-size:14.5px}
.qsub{margin:2px 0 0;font-size:13px;color:var(--text-3)}
.babx{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-5);margin-top:var(--space-5)}
.bab{border-radius:10px;padding:var(--space-4) var(--space-5);border:1px solid var(--border)}
.bab-before{background:var(--surface-2)}
.bab-after{background:var(--primary-light);border-color:color-mix(in oklab,var(--primary) 25%,#fff)}
.bab b{display:block;font-size:13px;letter-spacing:.12em;margin-bottom:6px}
.bab p{font-size:15px;color:var(--text)}
.owner{font-size:12px;color:var(--text-2);border:1px solid var(--border-2);border-radius:999px;padding:2px 10px;white-space:nowrap}
.owner-primary{color:var(--primary);border-color:color-mix(in oklab,var(--primary) 45%,transparent)}
.owner-info{color:var(--info);border-color:color-mix(in oklab,var(--info) 45%,transparent)}
.owner-warning{color:var(--warning);border-color:color-mix(in oklab,var(--warning) 45%,transparent)}
.owner-success{color:var(--success);border-color:color-mix(in oklab,var(--success) 45%,transparent)}
.impact{margin:var(--space-3) 0 0;padding:var(--space-3) var(--space-4);background:var(--surface-2);border-left:3px solid var(--primary);border-radius:6px}
.impact b{display:block;font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--primary);margin-bottom:3px}
.impact p{margin:0;color:var(--text);font-size:15.5px}
.ann{display:block;font-style:normal;font-size:12.5px;color:var(--warning);margin-top:2px}
.sb-track{display:flex;height:10px;border-radius:2px;overflow:hidden;background:var(--surface-3)}
.sb{display:block;height:100%}
.sb-danger{background:var(--danger)}.sb-warning{background:var(--warning)}.sb-info{background:var(--info)}.sb-muted{background:var(--muted)}
.sb-primary{background:var(--primary)}.sb-success{background:var(--success)}
.sb-legend{display:flex;flex-wrap:wrap;gap:var(--space-5);margin-top:10px;font-size:12.5px;color:var(--text-2)}
.sevbar{margin-top:var(--space-4)}
/* index overlay */
.index{position:fixed;inset:0;z-index:60;background:rgba(15,23,42,.55);display:none;padding:6vh 22px;overflow:auto}
.index[open],.index.show{display:block}
.index-panel{max-width:760px;margin:0 auto;background:var(--surface);border-radius:16px;padding:var(--space-6);
 box-shadow:0 30px 70px -30px rgba(15,23,42,.6)}
.index-panel h2{margin:0 0 var(--space-4);font-size:20px}
.index-panel .close{float:right}
.index-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:2px var(--space-5)}
.index-list a{display:flex;gap:var(--space-3);align-items:baseline;padding:8px 0;border-bottom:1px solid var(--border);color:var(--text-2);font-size:14.5px}
.index-list a:hover{color:var(--primary)}
.index-list .mono{font-size:11.5px;color:var(--text-3)}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@media (max-width:820px){
 :root{--page-pad:26px 22px}
 .deck{padding:var(--space-5) 12px 0}
 .ptitle{flex-direction:column;gap:var(--space-4)}
 .pmeta{justify-content:flex-start}
 .cover-score{grid-template-columns:1fr}
 .arow{grid-template-columns:1fr}
 .arow .owner,.arow .cycle{justify-self:start}
 .signrow{grid-template-columns:74px 1fr;gap:var(--space-3)}
 .signmeta{grid-column:2}
 .lc-row{grid-template-columns:104px 1fr 76px}.lc-name{font-size:12.5px}
 .method{grid-template-columns:1fr;gap:var(--space-6)}
 .topbar .doc{display:none}
}
@media print{
 @page{size:A4;margin:14mm}
 body{background:#fff;padding:0}
 .topbar,.index,.progress{display:none!important}
 .deck{display:block;max-width:none;padding:0}
 .page{break-after:page;page-break-after:always;box-shadow:none;border:0;border-radius:0;min-height:0;padding:0 0 8mm}
 .page:last-child{break-after:auto}
 .page-dark{background:#fff;color:var(--text);--text:#0F172A;--text-2:#475569;--text-3:#5E6C7F;--border:#E2E8F0;
  --border-2:#CBD5E1;--surface:#F7F9FC;--surface-2:#F7F9FC;--surface-3:#E8EEF5;--primary:#4F46E5;--mark-bg:#4F46E5;--mark-fg:#fff}
 .cover h1,.cover-sub,.cbig small,.cover-no,.cover-facts dt,.cover-sign,.cm-scale,.cover .pkicker{color:inherit!important}
 .cover-sub{color:#475569!important}.cm-fill{background:#0F172A}.cm-track{background:#E8EEF5}
 .cover{border-bottom:2px solid var(--text);padding-bottom:6mm}
 .frow,.arow,.callout,.codewrap,.evrow li,.signrow{break-inside:avoid}
 .page{animation:none!important;opacity:1!important;transform:none!important}
 details{display:block}details>summary{display:none}details.src ul{display:block}
 pre{white-space:pre-wrap;font-size:10.5px;background:#0F172A;color:#E2E8F0}
 p,li{orphans:3;widows:3}
}
@media (prefers-reduced-motion:no-preference){
 .page{animation:rise .45s cubic-bezier(.16,1,.3,1) both;animation-timeline:view();animation-range:entry 0% entry 22%}
 @keyframes rise{from{opacity:.35;transform:translateY(8px)}to{opacity:1;transform:none}}
}
'''

JS = r'''
(function(){
  var pages=[].slice.call(document.querySelectorAll('.page'));
  if(!pages.length) return;
  var reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var bar=document.querySelector('.progress i');
  var now=document.getElementById('now-page');
  function cur(){
    var best=1,bd=Infinity;
    pages.forEach(function(p,i){
      var d=Math.abs(p.getBoundingClientRect().top-72);
      if(d<bd){bd=d;best=i;}
    });
    return best;
  }
  function go(i){
    i=Math.max(0,Math.min(pages.length-1,i));
    pages[i].scrollIntoView({behavior:reduce?'auto':'smooth',block:'start'});
    history.replaceState(null,'','#p'+(i+1));
  }
  function sync(){
    var i=cur();
    if(now) now.textContent=String(i+1).padStart(2,'0')+' / '+String(pages.length).padStart(2,'0');
    if(bar){
      var h=document.documentElement.scrollHeight-window.innerHeight;
      bar.style.width=(h>0?Math.min(100,Math.max(0,window.scrollY/h*100)):0)+'%';
    }
  }
  window.addEventListener('scroll',sync,{passive:true});
  window.addEventListener('resize',sync);
  sync();
  document.addEventListener('keydown',function(e){
    if(e.metaKey||e.ctrlKey||e.altKey) return;
    var t=e.target||{};
    if(/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName||'')) return;
    var overlay=document.getElementById('index');
    if(e.key==='Escape'){ if(overlay) overlay.classList.toggle('show'); return; }
    if(overlay&&overlay.classList.contains('show')) return;
    if(e.key==='ArrowRight'||e.key==='ArrowDown'||e.key==='PageDown'||e.key===' '){ e.preventDefault(); go(cur()+1); }
    else if(e.key==='ArrowLeft'||e.key==='ArrowUp'||e.key==='PageUp'){ e.preventDefault(); go(cur()-1); }
    else if(e.key==='Home'){ e.preventDefault(); go(0); }
    else if(e.key==='End'){ e.preventDefault(); go(pages.length-1); }
  });
  var overlay=document.getElementById('index');
  if(overlay){
    overlay.addEventListener('click',function(e){
      if(e.target===overlay||e.target.classList.contains('close')) overlay.classList.remove('show');
      if(e.target.tagName==='A') overlay.classList.remove('show');
    });
  }
  document.addEventListener('click',function(e){
    var btn=e.target.closest&&e.target.closest('.copy');
    if(!btn) return;
    var wrap=btn.closest('.codewrap'); if(!wrap) return;
    var pre=wrap.querySelector('pre'); if(!pre) return;
    var text=pre.innerText;
    var done=function(){ var old=btn.textContent; btn.textContent='已复制'; setTimeout(function(){btn.textContent=old;},1600); };
    if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(text).then(done,function(){}); }
    else{ var ta=document.createElement('textarea'); ta.value=text; document.body.appendChild(ta); ta.select();
      try{document.execCommand('copy');done();}catch(err){} document.body.removeChild(ta); }
  });
})();
'''

HTML = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>索菲亚官网 GEO 评测报告 · {E(DOMAIN)}</title>
<meta name="description" content="GEO 站内准备度评测报告：{E(DOMAIN)}，站内准备度 {sc["overall_score"]}/100（{E(sc["grade"])}），。">
<style>{CSS}</style></head><body>
<div class="topbar"><div class="topbar-in">
  <span class="brand">{MARK}<b>GEO SCORING</b></span>
  <span class="doc">索菲亚官网 GEO 站内准备度评测 · {E(DOMAIN)}</span>
  <span class="right"><span class="mono">报告编号 {E(DOC_NO)}</span><span class="now">第 <b id="now-page">01 / {N:02d}</b> 页</span>
  <button class="btn" type="button" onclick="document.getElementById('index').classList.add('show')">索引</button></span>
</div><div class="progress"><i></i></div></div>

<div class="deck">
{"".join(body)}
</div>
<p class="docfoot">说明：本报告为站内评测，衡量网站能否被 AI 正确读懂、信任与引用；不涉及搜索排名与网站流量，也不包含 AI 实际引用情况（是否被提到）的实测。</p>

<div class="index" id="index" role="dialog" aria-modal="true" aria-label="报告索引">
  <div class="index-panel"><button class="btn close" type="button">关闭 (ESC)</button><h2>报告索引</h2>
  <div class="index-list">{index_items}</div></div>
</div>
<script>{JS}</script>
</body></html>'''

out = os.path.join(ROOT, "report", "sofeyia_geo_report_for_client_v3.1.html")
open(out, "w", encoding="utf-8").write(HTML)
r = json.load(open(os.path.join(ROOT, "run.json"), encoding="utf-8"))
r.setdefault("report_refs", {})["client_deck_html"] = "report/sofeyia_geo_report_for_client_v3.1.html"
json.dump(r, open(os.path.join(ROOT, "run.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("wrote report/sofeyia_geo_report_for_client_v3.1.html", len(HTML), "chars ;", N, "pages ;", len(top), "finding pages")
