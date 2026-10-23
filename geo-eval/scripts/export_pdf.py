#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把渲染好的 GEO 报告 HTML 导出为 PDF（resun hotel 报告同款「连续版式」导出）。

方法（与 runs/resunhotel.cn/2026-10-10_run02/report/resunhotel_geo_report_client.pdf 一致）：

  1. 中和掉响应式断点与模板自带的 @media print 块——改写成不可能的 min-width 查询。
     原因：Chrome 打印时以约 800px 视口求值媒体查询，若保留 `@media (max-width:820px)`
     会命中，整份 deck 会用移动端版式渲染。
  2. 注入 __pdf_continuous__ 打印样式：@page 设为桌面宽度、零边距（1080px x 1527px，
     即 810pt x 1145pt），并取消强制分页，使 31 页 deck 连续排布而不是一页一张卡。
     同时强制 print-color-adjust:exact 保留配色，隐藏 topbar/索引/进度条。
  3. 用 headless Chrome --print-to-pdf 输出。

用法：
    python3 export_pdf.py <report.html> [--out out.pdf] [--source-only]

产物默认与输入同目录：<同名>.pdf 与 <同名>.pdf-source.html
"""

import argparse
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]

# 与 resun 报告完全一致的连续版式打印样式
CONTINUOUS_CSS = """
<style id="__pdf_continuous__">
@media print{
  @page{ size: 1080px 1527px; margin: 0; }   /* 桌面版式：deck 22px + page 44px → 版心正好 948px */
  html,body{ background:#FFFFFF!important; margin:0!important; padding:0!important; }
  /* 只去卡片外观；边框改透明以保持 1px 盒模型，宽度分毫不变 */
  .page{ border-color:transparent!important; border-radius:0!important; box-shadow:none!important; }
  /* 不再强制分页 */
  .page{ break-after:auto!important; page-break-after:auto!important; break-before:auto!important; }
  .topbar,.index,.progress{ display:none!important; }
  /* 分页完全由内容流决定：不使用任何 break-inside / break-after 约束，
     并关闭 widows/orphans。这样页面边界恒为 1527px 的整数倍，
     目录页码才能由测量精确得出；同时避免大块被整体推到下一页留下大片空白。 */
  *{ break-inside:auto!important; break-before:auto!important; break-after:auto!important;
     orphans:1!important; widows:1!important; }
  /* .codewrap 带 overflow:hidden，跨页片段会被裁切，必须放开 */
  .codewrap{ overflow:visible!important; border-radius:0!important; }
  pre{ font-size:10.5px; white-space:pre-wrap; }   /* 代码字号收紧，减少跨页 */
  *,*::before,*::after{ animation:none!important; transition:none!important; }
  .page{ opacity:1!important; transform:none!important; }
  *{ -webkit-print-color-adjust:exact!important; print-color-adjust:exact!important; }
}
</style>
"""



# ── 目录页码对齐 ────────────────────────────────────────────────
# deck 的目录数字是「节号」，连续版式下物理页数更多，两者对不上。
# 这里先用与打印一致的布局量出每一节的物理页号，再把目录与索引的数字换成真实页码。
PAGE_H_PX = 1527.0

PROBE_JS = """
<script>
window.addEventListener('load', function () {
  var PH = %(ph)s, m = {};
  document.querySelectorAll('section.page').forEach(function (s) {
    if (!s.id) return;
    var top = s.getBoundingClientRect().top + window.scrollY;
    m[s.id] = Math.floor(top / PH) + 1;
  });
  document.title = 'MAP=' + JSON.stringify(m) + '|H=' + document.documentElement.scrollHeight;
});
</script>
""" % {"ph": PAGE_H_PX}


def measure_from_pdf(pdf_path, lang="zh"):
    """从已打印的 PDF 中读取每节实际落在第几页。

    打印时每页底部不足一行的空白会被丢弃，这个损耗逐页累积；
    因此不能按内容高度推算页号，必须直接读 PDF。
    依赖每节页眉里的节号（Section NN / MM），本函数只用于测量。
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import pdf_text
    except Exception:
        return {}, 0
    try:
        pages = pdf_text.page_texts(pdf_path)
    except Exception:
        return {}, 0
    pat = re.compile(r"(?:Section|节)\s*(\d+)\s*/\s*(\d+)")
    mapping = {}
    for i, txt in enumerate(pages, 1):
        for m in pat.finditer(txt):
            n = int(m.group(1))
            mapping.setdefault(f"p{n}", i)
    return mapping, len(pages)


NOTE_ZH_OLD = "阅读方式：向下滚动或按 ← / → 翻节，按 ESC 打开索引。每一节对应一个独立小节。"
NOTE_ZH_NEW = "目录中的数字为 PDF 实际页码。"
NOTE_EN_OLD = ("To navigate: scroll, or press &larr; / &rarr; to move a section, "
               "ESC to open the index. Each section is self-contained.")
NOTE_EN_NEW = "The numbers in this index are PDF page numbers."
HIDE_CHIP = "<style>.pgnum{visibility:hidden!important}</style>"


def apply_note_text(html, lang="zh"):
    """打印前把「滚动/翻页」提示改成页码说明。

    该文案长度会改变 TOC 页的换行，因此必须在打印（含测量那一遍）之前应用，
    否则测量版与成品版的布局会不一致。
    """
    if lang == "en":
        return html.replace(NOTE_EN_OLD, NOTE_EN_NEW)
    return html.replace(NOTE_ZH_OLD, NOTE_ZH_NEW)


def apply_page_numbers(html, mapping, lang="zh"):
    """把目录与索引里的节号换成物理页号，并把「滚动/翻页」提示改成页码说明。"""
    if not mapping:
        return html

    def fix_toc_li(m):
        li = m.group(0)
        ref = re.search(r'href="#(p\d+)"', li)
        if not ref:
            return li
        page = mapping.get(ref.group(1))
        if not page:
            return li
        return re.sub(r'(<span class="n mono">)\d+(</span>)',
                      lambda mm: f'{mm.group(1)}{page:02d}{mm.group(2)}', li, count=1)

    html = re.sub(r"<li>.*?</li>", fix_toc_li, html, flags=re.S)

    def fix_index(m):
        ref = m.group(1)
        page = mapping.get(ref)
        if not page:
            return m.group(0)
        return f'<a href="#{ref}"><span class="mono">{page:02d}</span>'

    html = re.sub(r'<a href="#(p\d+)"><span class="mono">\d+</span>', fix_index, html)

    return html

def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    found = shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    return None


def build_pdf_source(html_path, source_path):
    """生成 .pdf-source.html：中和两个媒体查询 + 注入连续版式打印样式。

    可重复执行：若输入本身已是 pdf-source（含 __pdf_continuous__），
    会先移除旧样式块再注入当前版本，避免用到过期样式。
    """
    html = open(html_path, encoding="utf-8").read()

    had = "__pdf_continuous__" in html
    if had:
        html = re.sub(r'\n?<style id="__pdf_continuous__">.*?</style>\n?', '\n', html, flags=re.S)

    n1 = html.count("@media (max-width:820px){")
    n2 = html.count("@media print{")
    # 距离 99999998/99999999 只差 1，保证两条规则的相对顺序不变
    html = html.replace("@media (max-width:820px){", "@media (min-width:99999998px){")
    html = html.replace("@media print{", "@media (min-width:99999999px){")

    if "</body>" not in html:
        print("[export_pdf] 警告：未找到 </body>，将样式追加到文件末尾")
        html = html + CONTINUOUS_CSS
    else:
        html = html.replace("</body>", CONTINUOUS_CSS + "</body>", 1)

    open(source_path, "w", encoding="utf-8").write(html)
    print(f"[export_pdf] 中和断点：max-width:820px x{n1}，@media print x{n2}"
          + ("（已替换旧版连续样式）" if had else ""))
    print(f"[export_pdf] wrote {source_path}")
    return source_path


def print_to_pdf(source_path, pdf_path):
    chrome = find_chrome()
    if not chrome:
        print("[export_pdf] 找不到 Chrome/Chromium，无法导出 PDF")
        sys.exit(1)

    tmp_profile = tempfile.mkdtemp(prefix="geo-pdf-")
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",
        f"--user-data-dir={tmp_profile}",
        f"--print-to-pdf={pdf_path}",
        "file://" + os.path.abspath(source_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    finally:
        shutil.rmtree(tmp_profile, ignore_errors=True)

    if not os.path.exists(pdf_path):
        print(f"[export_pdf] 导出失败（exit={proc.returncode}）")
        print((proc.stderr or "")[-1500:])
        sys.exit(1)
    print(f"[export_pdf] wrote {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")
    return pdf_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--out", default=None, help="输出 PDF 路径（默认同名 .pdf）")
    ap.add_argument("--source-only", action="store_true", help="只生成 .pdf-source.html，不打印")
    args = ap.parse_args()

    if not os.path.exists(args.html):
        print(f"[export_pdf] 找不到 {args.html}")
        sys.exit(1)

    base = re.sub(r"\.html?$", "", args.html)
    source_path = base + ".pdf-source.html"
    pdf_path = args.out or (base + ".pdf")

    build_pdf_source(args.html, source_path)
    if args.source_only:
        return

    _src = open(source_path, encoding="utf-8").read()
    # 按 <html lang> 判定语言，比匹配页面文字更可靠
    _m = re.search(r'<html[^>]*\blang="([^"]+)"', _src, re.I)
    lang = "en" if (_m and _m.group(1).lower().startswith("en")) else "zh"

    # 测量之前先做所有会改变布局的编辑（提示语换行数变化会影响后续所有页号）
    _edited = apply_note_text(_src, lang)
    if _edited != _src:
        open(source_path, "w", encoding="utf-8").write(_edited)
        print("[export_pdf] 已先把目录提示语改为页码说明（测量前完成，避免布局漂移）")

    # 第一遍：带节号页眉打印，用来从 PDF 里读出每节真实页号
    # 先确保测量版一定带出节号（上一次运行可能已注入隐藏样式）
    _cur = open(source_path, encoding="utf-8").read().replace(HIDE_CHIP, "")
    _cur = _cur.replace("</head>", "<style>.pgnum{visibility:visible!important}</style></head>", 1)
    open(source_path, "w", encoding="utf-8").write(_cur)
    print("[export_pdf] 第一遍打印（测量用）…")
    probe_pdf = os.path.join(os.path.dirname(pdf_path) or ".", "_measure.pdf")
    print_to_pdf(source_path, probe_pdf)
    mapping, page_total = measure_from_pdf(probe_pdf, lang)
    if not mapping:
        print("[export_pdf] 警告：无法从 PDF 读出节号，目录将保留原编号")
        os.remove(probe_pdf) if os.path.exists(probe_pdf) else None
        return
    print(f"[export_pdf] 测得 {len(mapping)} 节 / 共 {page_total} 页")

    # 第二遍：把目录页码改成真实页号，并在打印时隐藏节号页眉（不改变布局）
    html = open(source_path, encoding="utf-8").read()
    html = apply_page_numbers(html, mapping, lang)
    html = html.replace("</head>", HIDE_CHIP + "</head>", 1)
    open(source_path, "w", encoding="utf-8").write(html)

    print_to_pdf(source_path, pdf_path)
    try:
        os.remove(probe_pdf)
    except OSError:
        pass

    # 自检：两遍打印的页数必须一致（隐藏页眉不应改变布局）
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import pdf_text
        final_pages = pdf_text.page_count(pdf_path)
        if page_total and final_pages != page_total:
            print(f"[export_pdf] 警告：测量版 {page_total} 页、成品 {final_pages} 页，页码可能偏移")
        else:
            print(f"[export_pdf] 自检通过：成品 {final_pages} 页，与测量版一致")
    except Exception as exc:  # noqa: BLE001
        print(f"[export_pdf] 跳过自检：{exc}")


if __name__ == "__main__":
    main()
