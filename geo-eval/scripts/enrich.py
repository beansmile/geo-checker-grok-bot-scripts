#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4 (LLM deep interpretation — required in the pipeline):
Read report.engine.json (rules-engine output), enrich findings / narratives,
write final report.json. build_report.py then renders md+html.

Grok Bot / GEO Checker path (default):
  Do NOT set GEO_EVAL_LLM_API_KEY. Without a key, this script copies
  report.engine.json → report.json (llm_enabled=false). The Agent then
  rewrites report.json itself using the English prompts in ../prompts.md.
  That is the intended enrichment path — no external OpenAI API.

Optional legacy plug-in (local/dev only, not used by GEO Checker):
    GEO_EVAL_LLM_API_KEY    OpenAI-compatible key
    GEO_EVAL_LLM_BASE_URL   default https://api.openai.com/v1
    GEO_EVAL_LLM_MODEL      default gpt-4o-mini

Usage:
    python3 enrich.py <run_dir>
"""

import html as html_lib
import json
import os
import re
import sys
import urllib.request
from urllib.parse import urlparse


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _strip_tags(s):
    s = re.sub(r"<script[^>]*>.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style[^>]*>.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_lib.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _page_excerpts(run_dir, limit=12):
    """从 evidence/pages 抽取 {url,title,text} 供 LLM 写真实证据。"""
    pages_dir = os.path.join(run_dir, "evidence", "pages")
    out = []
    if not os.path.isdir(pages_dir):
        return out
    url_map = {}
    list_file = os.path.join(pages_dir, "pages.list")
    if os.path.isfile(list_file):
        for line in open(list_file, encoding="utf-8"):
            line = line.strip()
            if "|" in line:
                slug, url = line.split("|", 1)
                url_map[slug] = url
    for fname in sorted(os.listdir(pages_dir)):
        if not fname.endswith(".html"):
            continue
        slug = fname[:-5]
        url = url_map.get(slug, slug)
        raw = open(os.path.join(pages_dir, fname), encoding="utf-8", errors="ignore").read()
        title = ""
        m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
        if m:
            title = _strip_tags(m.group(1))[:120]
        text = _strip_tags(raw)[:700]
        out.append({"url": url, "title": title, "text": text})
        if len(out) >= limit:
            break
    return out


def _llm(messages, max_tokens=3000, json_mode=True):
    """OpenAI 兼容 chat/completions；失败返回 None。"""
    api_key = os.environ.get("GEO_EVAL_LLM_API_KEY")
    if not api_key:
        return None
    base = os.environ.get("GEO_EVAL_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("GEO_EVAL_LLM_MODEL", "gpt-4o-mini")
    payload = {"model": model, "temperature": 0.2, "max_tokens": max_tokens, "messages": messages}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            body = json.loads(r.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[enrich] LLM 调用失败：{e}")
        return None


DIM_KEYS = ["schema", "entity", "ogp", "richness", "kg", "absorption", "trust", "on_page", "quality"]

# 「只报不评」的建议项：引擎标了 scored=false，LLM 改写后必须保留，
# 否则报告会把它重新计入严重度分布、读者会误读为已扣分。
ADVISORY_RE = re.compile(
    r"权威外部引用|外部权威引用|建议项|不计分|内页\s*Open Graph|"
    r"external (?:authority )?reference|authority reference|advisory|not scored",
    re.I,
)


def mark_scored(engine_findings, llm_findings):
    """保留 scored 标记：引擎判为建议项的条目，LLM 改写后仍不计分。"""
    engine_advisory = {
        (f.get("title") or "").strip()
        for f in engine_findings
        if f.get("scored") is False
    }
    for f in llm_findings:
        if f.get("scored") is False:
            continue
        if (f.get("title") or "").strip() in engine_advisory:
            f["scored"] = False
            continue
        hay = " ".join(str(f.get(k) or "") for k in ("title", "problem", "impact", "solution"))
        f["scored"] = not bool(ADVISORY_RE.search(hay))
    return llm_findings


def enrich_findings(engine, excerpts):
    """LLM 复核 + 重写 findings。"""
    context = {
        "domain": engine.get("domain", ""),
        "url": engine.get("url", ""),
        "site_type": engine.get("scope", {}).get("role_counts", {}),
        "engine_findings": [
            {k: f.get(k) for k in ("severity", "title", "problem", "impact", "solution", "scored") if k in f}
            for f in engine.get("findings", [])
        ],
        "pages": excerpts,
    }
    sys_prompt = (
        "你是资深 GEO（生成式引擎优化）主笔。基于站点抓取证据，复核并重写规则引擎给出的问题清单，"
        "产出可直接进客户报告的中文内容。要求：\n"
        "1) 剔除误报（证据站不住脚的）、合并重复项；若有证据确凿但清单遗漏的高信号问题，可补充（最多 3 条）。\n"
        "2) 每条必须用站点真实值（品牌名/域名/邮箱/URL/真实数字），不得编造证据里没有的事实；拿不准的用 [请核实] 标注。\n"
        "3) evidence 里的 url 必须是证据页里真实出现的 URL；quote 是原文/现象描述，≤120 字。\n"
        "4) code 写「可直接套用」的修复代码（HTML/JSON-LD/meta），真实品牌与 URL，不写占位 Lorem。\n"
        "5) severity 用 严重/高/中/低。\n"
        "6) 清单里 scored=false 的条目是「只报不评」的建议项：重写后必须保留 scored=false，"
        "其余条目 scored=true；不要给建议项编造扣分或影响分。\n"
        "只输出 JSON：{\"findings\":[{\"severity\":\"…\",\"title\":\"…\",\"problem\":\"…\",\"impact\":\"…\","
        "\"solution\":\"…\",\"evidence\":[{\"url\":\"…\",\"quote\":\"…\"}],\"code\":\"…\",\"scored\":true}]}"
    )
    user_prompt = f"站点证据与引擎初判如下：\n{json.dumps(context, ensure_ascii=False)}"
    raw = _llm([
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ], max_tokens=8000)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data.get("findings") or []
    except (ValueError, TypeError):
        return None


def enrich_narratives(engine, findings):
    """LLM 重写分维度解读 + 总评 + 结语。"""
    context = {
        "domain": engine.get("domain", ""),
        "brand": engine.get("url", ""),
        "dimensions": engine.get("dimensions", []),
        "dimension_details": engine.get("dimension_details", []),
        "strengths": engine.get("strengths", []),
        "findings": [
            {"severity": f.get("severity"), "title": f.get("title"), "solution": f.get("solution")}
            for f in (findings or engine.get("findings", []))
        ],
    }
    sys_prompt = (
        "你是资深 GEO 评测主笔。基于维度得分与问题清单，写客户报告的中文解读。要求：\n"
        "1) dimension_details 覆盖 9 个 key（schema/entity/ogp/richness/kg/absorption/trust/on_page/quality），"
        "每段 2~4 句，先说结论再说证据与数字，点出扣分根因，用站点真实值。\n"
        "2) overall_summary 用 <strong> 强调关键结论、<br> 分段，4~6 段，客观（好/坏都说）。\n"
        "3) closing 是一句话结论 + 下一步优先动作。\n"
        "只输出 JSON：{\"dimension_details\":[{\"key\":\"…\",\"detail\":\"…\"}],"
        "\"overall_summary\":\"…\",\"closing\":\"…\"}"
    )
    raw = _llm([
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ], max_tokens=4000)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def main():
    run_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    engine_path = os.path.join(run_dir, "report.engine.json")
    if not os.path.exists(engine_path):
        # 兼容：没有 engine 快照时，把现有 report.json 当引擎
        engine_path = os.path.join(run_dir, "report.json")
    if not os.path.exists(engine_path):
        print("[enrich] 找不到 report.engine.json / report.json")
        sys.exit(1)

    engine = _load(engine_path)
    engine.setdefault("llm_review", {})

    api_key = os.environ.get("GEO_EVAL_LLM_API_KEY")
    if not api_key:
        # 无 key：引擎结果直接作为 report.json（llm_enabled=false，agent 应按 prompts.md 补做）
        engine["llm_enabled"] = False
        engine["llm_review"] = {"reviewed": False, "note": "No GEO_EVAL_LLM_API_KEY; Agent should enrich per prompts.md (Grok Bot path)"}
        _dump(os.path.join(run_dir, "report.json"), engine)
        print("[enrich] No GEO_EVAL_LLM_API_KEY → report.json = engine copy (Agent must enrich via prompts.md)")
        return

    excerpts = _page_excerpts(run_dir)

    print("[enrich] Step 4a：LLM 复核 findings …")
    llm_findings = enrich_findings(engine, excerpts)
    print("[enrich] Step 4b：LLM 重写分维度/总评/结语 …")
    narr = enrich_narratives(engine, llm_findings)

    # 合并：分数/维度/scope/adjustments 一律沿用引擎（口径可复现），findings/narrative 用 LLM 版
    out = dict(engine)
    if llm_findings:
        out["findings"] = mark_scored(engine.get("findings", []), llm_findings)
    if narr:
        dd_by_key = {d.get("key"): d for d in narr.get("dimension_details", [])}
        out["dimension_details"] = [
            {**d, "detail": (dd_by_key.get(d.get("key"), {}).get("detail") or d.get("detail", ""))}
            for d in engine.get("dimension_details", [])
        ]
        if narr.get("overall_summary"):
            out["overall_summary"] = narr["overall_summary"]
        if narr.get("closing"):
            out["closing"] = narr["closing"]
    out["llm_enabled"] = True
    out["llm_review"] = {
        "reviewed": True,
        "findings_before": len(engine.get("findings", [])),
        "findings_after": len(out.get("findings", [])),
        "source": "enrich.py",
    }
    _dump(os.path.join(run_dir, "report.json"), out)
    print(f"[enrich] wrote report.json（findings {len(engine.get('findings', []))} → {len(out.get('findings', []))}，llm_enabled=true）")


if __name__ == "__main__":
    main()
