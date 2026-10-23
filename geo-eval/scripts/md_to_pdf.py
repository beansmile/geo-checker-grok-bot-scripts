#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown → PDF（A4 文档版式），用于方法论、回信这类长文文档。

流程：pandoc（gfm）把 Markdown 转成 HTML 片段 → 套上文档样式表 → 无头 Chrome
--print-to-pdf。与 export_pdf.py（deck 连续版式）不同，这里走标准 A4 分页。

用法：
    python3 md_to_pdf.py <file.md> [<file2.md> ...] [--out-dir DIR]
产物：与源文件同目录的 <同名>.pdf
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]

CSS = """
:root{
  --ink:#0F172A; --ink-2:#334155; --muted:#64748B;
  --line:#E2E8F0; --accent:#4F46E5; --soft:#F8FAFC;
}
@page{ size:A4; margin:17mm 16mm 17mm 16mm; }
*{ box-sizing:border-box; }
html{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body{
  margin:0;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,"Helvetica Neue",
              Arial,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:10.5pt; line-height:1.62; color:var(--ink);
}
article{ max-width:100%; }
h1{ font-size:19.5pt; line-height:1.25; margin:0 0 9pt; padding-bottom:7pt;
    border-bottom:2px solid var(--ink); letter-spacing:-.01em; }
h2{ font-size:13.8pt; margin:19pt 0 7pt; padding-top:5pt;
    border-top:1px solid var(--line); break-after:avoid; letter-spacing:-.005em; }
h3{ font-size:11.4pt; margin:13pt 0 5pt; color:var(--accent); break-after:avoid; }
h4{ font-size:10.6pt; margin:11pt 0 4pt; break-after:avoid; }
p{ margin:0 0 6.5pt; }
strong{ font-weight:650; }
em{ color:var(--muted); }
a{ color:var(--accent); text-decoration:none; word-break:break-word; }
code{
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:9pt; background:#EEF2FF; color:#312E81;
  padding:1px 3.5px; border-radius:3px; word-break:break-word;
}
pre{
  background:#0F172A; color:#E2E8F0; padding:8pt 10pt; border-radius:6pt;
  font-size:8.6pt; line-height:1.5; white-space:pre-wrap; word-break:break-word;
  break-inside:avoid; margin:7pt 0 10pt;
}
pre code{ background:none; color:inherit; padding:0; font-size:inherit; }
blockquote{
  margin:7pt 0 10pt; padding:6pt 10pt; border-left:3px solid var(--accent);
  background:var(--soft); color:var(--ink-2); break-inside:avoid;
}
blockquote p:last-child{ margin-bottom:0; }
table{
  width:100%; border-collapse:collapse; margin:7pt 0 11pt;
  font-size:9.2pt; break-inside:auto;
}
thead{ display:table-header-group; }
tr{ break-inside:avoid; }
th,td{ border:1px solid var(--line); padding:3.5pt 5.5pt; text-align:left; vertical-align:top; }
th{ background:#F1F5F9; font-weight:650; }
tbody tr:nth-child(even){ background:#FBFCFD; }
ul,ol{ margin:0 0 7pt; padding-left:15pt; }
li{ margin:0 0 2.5pt; }
li>p{ margin-bottom:2.5pt; }
hr{ border:0; border-top:1px solid var(--line); margin:13pt 0; }
"""

HTML_TMPL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head><body><article>
{body}
</article></body></html>
"""


def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    for name in ("google-chrome", "chromium", "chromium-browser"):
        f = shutil.which(name)
        if f:
            return f
    return None


def md_to_html(md_path):
    """pandoc gfm → HTML 片段。"""
    res = subprocess.run(
        ["pandoc", md_path, "-f", "gfm", "-t", "html5", "--wrap=none"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"[md_to_pdf] pandoc 失败：{res.stderr.strip()[:400]}")
        sys.exit(1)
    return res.stdout


def html_to_pdf(html_path, pdf_path, title):
    chrome = find_chrome()
    if not chrome:
        print("[md_to_pdf] 找不到 Chrome/Chromium")
        sys.exit(1)
    tmp_profile = tempfile.mkdtemp(prefix="md-pdf-")
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=8000",
        f"--user-data-dir={tmp_profile}",
        f"--print-to-pdf={pdf_path}",
        "file://" + os.path.abspath(html_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    finally:
        shutil.rmtree(tmp_profile, ignore_errors=True)
    if not os.path.exists(pdf_path):
        print(f"[md_to_pdf] 打印失败（exit={r.returncode}）\n{(r.stderr or '')[-1200:]}")
        sys.exit(1)


def convert(md_path, out_dir=None):
    base = os.path.splitext(os.path.basename(md_path))[0]
    out_dir = out_dir or os.path.dirname(os.path.abspath(md_path))
    pdf_path = os.path.join(out_dir, base + ".pdf")
    html_path = os.path.join(tempfile.mkdtemp(prefix="md-html-"), base + ".html")

    body = md_to_html(md_path)
    title = base
    for line in body.splitlines():
        if line.startswith("<h1"):
            title = line.split(">", 1)[-1].rsplit("<", 1)[0].strip() or base
            break
    open(html_path, "w", encoding="utf-8").write(
        HTML_TMPL.format(title=title, css=CSS, body=body)
    )
    html_to_pdf(html_path, pdf_path, title)
    size = os.path.getsize(pdf_path)
    print(f"  {os.path.basename(md_path):40s} -> {os.path.basename(pdf_path)}  ({size:,} bytes)")
    return pdf_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    for f in args.files:
        if not os.path.exists(f):
            print(f"[md_to_pdf] 找不到 {f}")
            sys.exit(1)
    print("[md_to_pdf] Markdown → A4 PDF")
    for f in args.files:
        convert(f, args.out_dir)


if __name__ == "__main__":
    main()
