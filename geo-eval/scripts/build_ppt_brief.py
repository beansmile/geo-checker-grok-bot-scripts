#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""客户面谈用 GEO 简报（主报告同款卡片式，每节一页，8 页，15–20 分钟）。
叙事：先让客户看到低分惊讶 → 一句“大部分是模板遗留”把心放回。
输出 report/sofeyia_geo_ppt_brief.html + report/sofeyia_geo_ppt_outline.md。
"""
import os, json, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
run = json.load(open(os.path.join(ROOT, "run.json"), encoding="utf-8"))
sc = run["scores"]; score = sc["overall_score"]; grade = sc["grade"]
date = datetime.date.today().isoformat()
DOMAIN = run["site"]["domain"].replace("https://", "").replace("http://", "").rstrip("/")

MARK = '<svg class="mark" viewBox="0 0 28 28" aria-hidden="true"><rect width="28" height="28" rx="7" fill="var(--mark-bg)"/><rect x="7" y="15.4" width="3.4" height="5.6" rx="1" fill="var(--mark-fg)"/><rect x="12.3" y="11.4" width="3.4" height="9.6" rx="1" fill="var(--mark-fg)" opacity=".82"/><rect x="17.6" y="7.4" width="3.4" height="13.6" rx="1" fill="var(--mark-fg)" opacity=".62"/></svg>'
def E(x): return __import__("html").escape(str(x if x is not None else ""))

# (样式, section, kicker, 标题, 正文HTML)
P = [
 ("cover", None, None, f"""<div class="cover-top"><span class="brand"><span>{MARK.replace('var(--mark-bg)','#fff').replace('var(--mark-fg)','#312E81')}</span><b>GEO SCORING</b></span><span class="cover-no mono">客户面谈材料</span></div>
   <div class="cover-mid">
     <div class="pkicker light">AI 搜索可见性（GEO）· 约 15–20 分钟</div>
     <h1>索菲亚官网<br>AI 搜索可见性简报</h1>
     <div class="cover-score"><div class="cbig">{score}<small>/100</small><em>站内准备度 · {grade}</em></div><div class="csub">分数看着低——但先说结论：<b>大部分是“建站模板没清干净”的一次性遗留问题，集中清理一轮就能解决大半。</b></div></div>
   </div>
   <div class="cover-sign"><span>站点：{E(DOMAIN)}</span><span>报告日期：{date}</span><span>共 8 页</span></div>"""),
 ("normal", "01 · 我们查了什么", "现在，买家在直接问 AI",
   """<p class="lead">买家找供应商，正从“用搜索引擎”转向“<b>直接问 ChatGPT、豆包、Kimi 等</b>”。</p>
   <div class="box">这份简报检查的是：当买家问「<b>中国有哪些靠谱的全屋定制厂家</b>」这类问题时，AI ——<br>① <b>能不能找到你</b>；② <b>会不会认错你</b>；③ <b>敢不敢引用你网站上的话</b>。</div>
"""),
 ("normal", "02 · 分数怎么理解", f"{score} 分 = “还没准备好被 AI 推荐”",
   f"""<p class="lead">60 分以下表示准备不足。<b>这个分数不是搜索排名，也不是 AI 提到你的次数。</b></p>
   <p class="body">一句话：网站技术上是通的，但 AI 现在<b>认不准“你是谁”</b>、也<b>不敢信你的内容</b>。</p>
   <div class="metaphor">就像一家资质齐全的店——招牌没挂对，橱窗还贴着装修样板。店面是真的，但第一眼让人不敢进。</div>
   <p class="body">等级说明：A+ 90 以上 · A 80–89 · B 70–79 · C 60–69 · D 60 以下（本报告 {score} 分为 D）。</p>"""),
 ("normal", "03 · 一眼能对上的问题", "打开网站就能看到的三个问题",
   """<ol class="items">
     <li><b>乱码假文字</b>：首页 / 关于 / FAQ 还残留 “Lorem ipsum” 占位文字——模板没拆干净。客户和 AI 看到都会觉得“这网站还没做完”。</li>
     <li><b>两个英文名</b>：Sofeyia / Suofeiya 混用——AI 会当成两家公司，多年积累的品牌认知被分流。</li>
     <li><b>两个邮箱</b>：sales@sofeyiahome.com 与 sales@suofeiyahome.com——像名片印错，客户会怕是钓鱼。</li>
   </ol>
   <p class="note">这三条，打开官网就能对上，不需要任何技术背景。</p>"""),
 ("normal", "04 · 还有几处", "还有几处，客户和 AI 都会看到",
   """<ol class="items">
     <li><b>首页写着“0 年经验”</b>：其实数字是滚动动画，真实值藏在代码里——但 AI 爬虫不执行 JS，读到的就是 0，等于在 AI 眼里这是一家“0 年经验、0 员工”的公司。</li>
     <li><b>隐私政策是默认范文</b>：建站系统自带的英文模板，不针对你的业务和目标市场，法务一看就懂，有合规风险。</li>
     <li><b>文章作者是建站账号</b>：署名 “ehaitech”，不是真人，难以建立“谁写的、谁负责”的信任。</li>
   </ol>"""),
 ("good", "05 · 好消息", "好消息：大部分是“模板遗留”",
   """<p class="lead">上面这些问题，大多来自<b>同一批建站模板</b>：占位文字、演示页、0 值动画、默认隐私政策、默认作者账号。</p>
   <p class="body">一句话：相当于<b>“网站没验收就上线了”</b>——不是内容战略的问题，是一次性收尾没做干净。</p>
   <div class="bigline">集中清理一轮 → 解决大半</div>"""),
 ("normal", "06 · 怎么修", "怎么修：三步",
   """<ol class="steps">
     <li><b>贵司确认口径</b>：品牌名、主邮箱、与上市主体的关系。<span class="dim">（这一步只需贵司拍板，不需要技术）</span></li>
     <li><b>清理收尾</b>：删占位 / 演示页、统一邮箱、换隐私政策、修作者、把计数器数字直接写进初始 HTML。<span class="dim">（建站商执行，约第 1 周）</span></li>
     <li><b>补真实内容</b>：用人话写清“我们是谁 / 怎么交付 / 材料认证 / 案例”。<span class="dim">（持续）</span></li>
   </ol>
   <p class="expect">预期：完成前两步约 <b>60 分以上</b>，全部完成约 <b>80 分左右</b>（方向性预估，不代表 AI 实际引用增加）。</p>"""),
 ("normal", "07 · 需要拍板", "这几件事，需要贵司拍板",
   """<ol class="items">
     <li><b>对外英文名</b>：建议用 Sofeyia（与域名一致），Suofeiya 作拼音别名保留。</li>
     <li><b>主用邮箱</b>：统一用哪一个？</li>
     <li><b>与上市主体（002572.SZ）的关系</b>：能否在官网上对外写明？</li>
     <li><b>关键数字</b>：营收 / 认证 / 年限，能否提供出处？</li>
   </ol>
   <div class="box">接下来：<b>第 1 周</b> 清理收尾 → <b>第 2–3 周</b> 补结构与内容 → 之后可复测看分数变化。大部分收尾由建站商执行，只需贵司先拍板上面这几个口径。</div>"""),
]

CSS = """
:root{--primary:#4F46E5;--primary-light:#EEF2FF;--bg:#EDF1F7;--surface:#FFF;--surface-2:#F7F9FC;--surface-3:#E8EEF5;
 --border:#E2E8F0;--border-2:#CBD5E1;--text:#0F172A;--text-2:#475569;--text-3:#5E6C7F;--good:#15803D;--good-bg:#F0FDF4;
 --mark-bg:#4F46E5;--mark-fg:#fff;
 --sans:Geist,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
 --mono:"Geist Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);font-size:16px;line-height:1.75;-webkit-font-smoothing:antialiased;padding-bottom:64px}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.deck{max-width:1080px;margin:0 auto;padding:24px 22px 0;display:grid;gap:32px}
.page{position:relative;background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:32px 44px 30px;
 box-shadow:0 1px 2px rgba(15,23,42,.04),0 22px 44px -36px rgba(15,23,42,.42);min-height:460px;display:flex;flex-direction:column}
.page-dark{background:#1E1B4B;border-color:#1E1B4B;color:#fff;--text:#fff;--text-2:#C7D2FE;--text-3:#A5B4FC;
 --border:rgba(255,255,255,.22);--border-2:rgba(255,255,255,.34);--mark-bg:#fff;--mark-fg:#312E81;--primary:#C7D2FE}
.good{background:var(--good-bg);border-color:#bbf7d0}
.ph{display:flex;align-items:center;gap:10px;padding-bottom:12px;border-bottom:1px solid var(--border);font-size:12.5px;color:var(--text-3)}
.ph .brand{display:flex;align-items:center;gap:7px;color:var(--primary);font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.ph .mark{width:18px;height:18px}
.ph .ph-sec{color:var(--text-2)}
.ph .ph-right{margin-left:auto;display:flex;gap:14px;align-items:center}
.ph .pgnum{color:var(--text)}
.pf{margin-top:auto;padding-top:12px;border-top:1px solid var(--border);display:flex;justify-content:space-between;font-size:11.5px;color:var(--text-3)}
.ptitle{margin:22px 0 0}
.pkicker{font-size:11.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--primary);font-weight:600;margin-bottom:8px}
.pkicker.light{color:#C7D2FE}
h2{font-size:clamp(23px,2.6vw,30px);line-height:1.32;margin:0;letter-spacing:-.015em}
h1{font-size:clamp(30px,4vw,44px);line-height:1.18;margin:0 0 18px;letter-spacing:-.025em}
.lead{font-size:19px;line-height:1.72;color:var(--text);margin:20px 0 0}
.body{font-size:16.5px;color:var(--text-2);margin:16px 0 0}
.box{background:var(--primary-light);border:1px solid #C7D2FE;border-radius:12px;padding:18px 22px;font-size:16.5px;line-height:1.8;color:var(--text);margin-top:18px}
.metaphor{background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:16px 20px;font-size:16px;color:#7c2d12;margin-top:18px}
.bigline{font-size:clamp(20px,2.6vw,26px);font-weight:700;color:var(--good);margin-top:22px}
.note{font-size:14px;color:var(--text-3);margin-top:18px}
.dim{color:var(--text-3)}
.expect{font-size:16px;color:var(--text-2);margin-top:22px}
.expect b{color:var(--good)}
ol.items{list-style:none;margin:20px 0 0;padding:0;display:grid;gap:14px;counter-reset:item}
ol.items li{position:relative;padding-left:2em;font-size:16.5px;line-height:1.65;color:var(--text)}
ol.items li::before{content:counter(item);counter-increment:item;position:absolute;left:0;top:.1em;width:1.5em;height:1.5em;
 border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.85em;font-family:var(--mono)}
ol.steps{list-style:none;margin:20px 0 0;padding:0;display:grid;gap:16px;counter-reset:st}
ol.steps li{position:relative;padding-left:2.6em;font-size:16.5px;line-height:1.65;color:var(--text)}
ol.steps li::before{content:counter(st);counter-increment:st;position:absolute;left:0;top:.05em;width:1.7em;height:1.7em;
 border-radius:50%;background:var(--primary);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-family:var(--mono)}
ul.foot{margin:20px 0 0;padding:0;list-style:none;color:var(--text-3);font-size:14.5px}
ul.foot li{position:relative;padding:4px 0 4px 18px}
ul.foot li::before{content:"—";position:absolute;left:0;color:var(--text-3)}
.cover-top{display:flex;align-items:center;justify-content:space-between;gap:16px}
.cover-top .brand{display:flex;align-items:center;gap:9px;font-size:13px;letter-spacing:.16em;text-transform:uppercase;font-weight:700}
.cover-top .mark{width:22px;height:22px}
.cover-no{font-size:12px;color:#A5B4FC}
.cover-mid{margin:48px 0 40px}
.cover-score{display:grid;grid-template-columns:auto 1fr;gap:40px;align-items:center;border-top:1px solid rgba(255,255,255,.22);padding-top:30px}
.cbig{font-size:96px;line-height:.9;font-weight:700;letter-spacing:-.04em}
.cbig small{font-size:28px;color:#A5B4FC;font-weight:500;letter-spacing:0}
.cbig em{display:block;font-style:normal;font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:#A5B4FC;margin-top:10px}
.csub{font-size:clamp(16px,2vw,19px);line-height:1.75;color:#E0E7FF}
.csub b{color:#fff;background:rgba(255,255,255,.14);padding:2px 8px;border-radius:6px}
.docfoot{max-width:1080px;margin:0 auto;padding:16px 22px 0;color:var(--text-3);font-size:12.5px;text-align:center}
.cover-sign{margin-top:20px;display:flex;gap:24px;flex-wrap:wrap;font-size:13px;color:#C7D2FE;border-top:1px solid rgba(255,255,255,.22);padding-top:16px}
@media (max-width:760px){.page{padding:26px 22px}.cover-score{grid-template-columns:1fr}}
@media print{@page{size:A4;margin:14mm}body{background:#fff;padding:0}.deck{display:block;max-width:none;padding:0}
 .page{break-after:page;page-break-after:always;box-shadow:none;border:0;border-radius:0;min-height:0;padding:0 0 6mm}
 .page:last-child{break-after:auto}.page-dark{background:#fff;color:var(--text);--text:#0F172A;--text-2:#475569;--text-3:#5E6C7F;--border:#E2E8F0;--mark-bg:#4F46E5;--mark-fg:#fff;--primary:#4F46E5}
 .cover-mid h1,.csub,.csub b{color:#0F172A}.csub b{background:#EEF2FF}}
"""

N = len(P)
def ph(pno, section=None):
    mid = f'<span class="ph-sec">{E(section)}</span>' if section else ""
    return f'<header class="ph"><span class="brand">{MARK}<b>GEO SCORING</b></span><span class="mono">{E(DOMAIN)}</span>{mid}<span class="ph-right"><span class="mono">{date}</span><span class="pgnum mono">{pno:02d} / {N:02d}</span></span></header>'

def pf():
    return '<footer class="pf"><span>GEO SCORING · AI 搜索可见性简报</span><span class="mono">综合准备度 %d/%s</span></footer>' % (score, grade)

body = []
for n, (style, section, title, content) in enumerate(P, start=1):
    if style == "cover":
        body.append(f'<section class="page page-dark">{content}</section>')
    else:
        head = f'<div class="ptitle"><div class="pkicker">{E(section)}</div><h2>{E(title)}</h2></div>'
        body.append(f'<section class="page {style}">{ph(n, section)}{head}{content}{pf()}</section>')

OUT = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>索菲亚官网 · AI 搜索可见性简报</title>
<style>{CSS}</style></head><body>
<div class="deck">{chr(10).join(body)}</div>
<p class="docfoot">说明：本报告为站内评测，衡量网站能否被 AI 正确读懂、信任与引用；不涉及搜索排名与网站流量，也不包含 AI 实际引用情况（是否被提到）的实测。</p>
</body></html>"""
open(os.path.join(ROOT, "report", "sofeyia_geo_ppt_brief.html"), "w", encoding="utf-8").write(OUT)

md = f"""# 索菲亚官网 · AI 搜索可见性（GEO）简报（面谈版）
> 供工作人员转成 PPT · GEO 部分约 15–20 分钟 · 8 页 · 强调“低分源于模板遗留”

## 封面
- 站内准备度：**{score} / 100（{grade}）**
- 定心话：分数看着低——但大部分是“建站模板没清干净”的一次性遗留问题，集中清理一轮就能解决大半。

## 01 我们查了什么
- 买家正从“用搜索引擎”转向“直接问 ChatGPT、豆包、Kimi 等”。
- 查的是：AI 回答“中国有哪些靠谱的全屋定制厂家”时——①能不能找到你 ②会不会认错你 ③敢不敢引用你网站的话。

## 02 {score} 分怎么理解
- 60 分以下 = 准备不足；不是搜索排名，也不是被提到的次数。
- 一句话：网站技术上是通的，但 AI 认不准“你是谁”、也不敢信你的内容。
- 比喻：资质齐全的店，招牌没挂对、橱窗还贴着装修样板。
- 等级：A+ 90 以上 / A 80–89 / B 70–79 / C 60–69 / D 60 以下。

## 03 一眼能对上的三个问题
1. 乱码假文字：首页/关于/FAQ 残留 Lorem ipsum（模板没拆干净）。
2. 两个英文名：Sofeyia / Suofeiya 混用（AI 当两家公司）。
3. 两个邮箱：sales@sofeyiahome.com 与 sales@suofeiyahome.com（像名片印错）。

## 04 还有几处
1. 首页“0 年经验”：滚动动画，AI 读到 0 而非真实值。
2. 隐私政策是默认英文范文（法务一看就懂，合规风险）。
3. 作者是建站账号 ehaitech，不是真人。

## 05 好消息：大部分是“模板遗留”
- 同一批建站模板带来：占位文字、演示页、0 值动画、默认隐私政策、默认作者账号。
- 相当于“网站没验收就上线了”，不是内容战略问题。
- 集中清理一轮 → 解决大半。

## 06 怎么修：三步
1. 贵司确认口径（品牌名、主邮箱、上市主体关系）。
2. 清理收尾（删占位/演示页、统一邮箱、换隐私政策、修作者、计数器数字写进初始 HTML）——建站商执行，约第 1 周。
3. 补真实内容（我们是谁 / 怎么交付 / 材料认证 / 案例）——持续。
- 预期：前两步约 60 分以上，全部完成约 80 分左右（方向性预估）。

## 07 需要拍板 + 接下来
1. 英文名建议 Sofeyia（Suofeiya 作拼音别名）；2. 主邮箱；3. 与 002572.SZ 的关系能否写明；4. 关键数字出处。
- 节奏：第 1 周清理收尾 → 第 2–3 周补结构与内容 → 复测。
"""
open(os.path.join(ROOT, "report", "sofeyia_geo_ppt_outline.md"), "w", encoding="utf-8").write(md)
run["report_refs"] = run.get("report_refs", {})
run["report_refs"]["ppt_brief_html"] = "report/sofeyia_geo_ppt_brief.html"
run["report_refs"]["ppt_brief_outline"] = "report/sofeyia_geo_ppt_outline.md"
json.dump(run, open(os.path.join(ROOT, "run.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"wrote report/sofeyia_geo_ppt_brief.html (deck 卡片式, {N} 页) + outline.md ; score {score}/{grade}")
