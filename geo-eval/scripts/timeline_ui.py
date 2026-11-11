#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared remediation checklist + effort-based schedule UI for GEO Checker HTML reports.

Used by build_report.py, build_content_report.py, and build_combined_report.py.
Durations are calendar-day effort defaults derived from item kind — never a fixed
W0–W16 cookie-cutter. Skip kinds that do not appear in this run's findings/actions.
"""

from __future__ import annotations

import html as html_mod
import re
from typing import Any, Iterable


def esc(s: Any) -> str:
    return html_mod.escape("" if s is None else str(s), quote=True)


# ---------------------------------------------------------------------------
# Effort defaults (calendar days). Ranges from product brief; midpoints used
# when enrichment does not supply effort_days.
# ---------------------------------------------------------------------------

KIND_EFFORT = {
    "https": 1.0,           # 0.5–1; restore HTTPS / TLS / 500
    "robots_sitemap": 1.0,  # 0.5–1
    "bot_allowlist": 1.0,   # 1
    "title_meta": 3.0,      # 2–5 (scaled by page hints when available)
    "thin_pages": 5.0,      # 3–10
    "schema_og": 2.0,       # 1–3
    "canonical": 1.0,
    "h1_onpage": 2.0,
    "answer_blocks": 3.0,
    "evergreen": 3.0,       # 2–4 per page; caller may multiply
    "proof_hub": 7.0,       # 5–10
    "case_narratives": 5.0,
    "en_export": 7.0,       # 5–10
    "entity_brand": 2.0,
    "freshness": 1.5,
    "retest": 1.0,
    "default": 2.0,
}

KIND_LABELS = {
    "en": {
        "https": "HTTPS / TLS / HTTP restore",
        "robots_sitemap": "robots.txt & sitemap reachability",
        "bot_allowlist": "Bot allowlist & GSC check",
        "title_meta": "Unique title / H1 / meta",
        "thin_pages": "Thin page upgrade",
        "schema_og": "Schema / Open Graph / machine signals",
        "canonical": "Canonical tags",
        "h1_onpage": "H1 & on-page topic",
        "answer_blocks": "Answer-first content blocks",
        "evergreen": "Evergreen answer pages",
        "proof_hub": "Proof hub / qualifications",
        "case_narratives": "Case narratives",
        "en_export": "EN / export intent pages",
        "entity_brand": "Brand & entity consistency",
        "freshness": "Publish / freshness signals",
        "retest": "Re-test against same rubric",
        "default": "Remediation item",
    },
    "zh": {
        "https": "HTTPS / TLS / 访问恢复",
        "robots_sitemap": "robots.txt 与 sitemap 可达",
        "bot_allowlist": "爬虫放行与 GSC 核验",
        "title_meta": "独立 title / H1 / meta",
        "thin_pages": "薄页升级",
        "schema_og": "结构化数据 / Open Graph",
        "canonical": "Canonical 标签",
        "h1_onpage": "H1 与页面主题",
        "answer_blocks": "答案优先内容块",
        "evergreen": "常青答案页",
        "proof_hub": "证明中心 / 资质",
        "case_narratives": "案例叙事升级",
        "en_export": "英文 / 外销意图页",
        "entity_brand": "品牌与实体口径",
        "freshness": "发布 / 新鲜度信号",
        "retest": "同口径复测",
        "default": "整改项",
    },
}

KIND_OWNERS = {
    "https": {"en": "eng / ops", "zh": "工程 / 运维"},
    "robots_sitemap": {"en": "eng / ops", "zh": "工程 / 运维"},
    "bot_allowlist": {"en": "eng / ops", "zh": "工程 / 运维"},
    "title_meta": {"en": "content / eng", "zh": "内容 / 工程"},
    "thin_pages": {"en": "content", "zh": "内容"},
    "schema_og": {"en": "eng", "zh": "工程"},
    "canonical": {"en": "eng", "zh": "工程"},
    "h1_onpage": {"en": "content / eng", "zh": "内容 / 工程"},
    "answer_blocks": {"en": "content", "zh": "内容"},
    "evergreen": {"en": "content", "zh": "内容"},
    "proof_hub": {"en": "content / PR", "zh": "内容 / 公关"},
    "case_narratives": {"en": "content", "zh": "内容"},
    "en_export": {"en": "content", "zh": "内容"},
    "entity_brand": {"en": "client + content", "zh": "贵司确认 + 内容"},
    "freshness": {"en": "content / eng", "zh": "内容 / 工程"},
    "retest": {"en": "GEO lead", "zh": "GEO 负责人"},
    "default": {"en": "content / eng", "zh": "内容 / 工程"},
}

# Keyword → kind (first match wins; order matters — more specific first)
KIND_RULES: list[tuple[str, list[str]]] = [
    ("https", [
        "https", "http(s)", "http ", "tls", "ssl", "500", "pingora", "waf",
        "unreachable", "access failure", "抓取失败", "无法访问", "证书", "宕机",
        "restore stable", "稳定 http",
    ]),
    ("bot_allowlist", [
        "allowlist", "oai-searchbot", "googlebot", "bingbot", "gptbot",
        "crawler access", "爬虫放行", "robots 屏蔽", "blocked crawler", "gsc",
    ]),
    ("robots_sitemap", [
        "robots.txt", "sitemap", "站点地图",
    ]),
    ("en_export", [
        "english", "export", "外销", "国际买家", "en intent", "英文意图",
    ]),
    ("proof_hub", [
        "proof hub", "patent", "award", "qualification", "证明中心", "专利",
        "资质", "奖项",
    ]),
    ("case_narratives", [
        "case narrative", "project case", "案例叙事", "案例升级", "top project",
    ]),
    ("evergreen", [
        "evergreen", "answer page", "buyer question", "procurement question",
        "常青", "答案页", "采购问题", "geo page", "losing quer",
    ]),
    ("thin_pages", [
        "thin page", "thin product", "薄页", "薄内容", "consolidate", "upgrade or consolidat",
    ]),
    ("schema_og", [
        "open graph", "og:", "ogp", "json-ld", "schema.org", "structured data",
        "结构化数据", "开放图谱", "twitter card",
    ]),
    ("canonical", ["canonical"]),
    ("title_meta", [
        "title / h1", "unique title", "meta description", "独立 title", "元描述",
        "title and meta", "titles and h1",
    ]),
    ("h1_onpage", ["h1", "主标题", "heading hierarchy"]),
    ("answer_blocks", [
        "answer block", "answer-first", "可吸收", "答案块", "证据块", "absorb",
        "citation block",
    ]),
    ("entity_brand", [
        "entity", "brand consistency", "实体", "品牌口径", "naming",
    ]),
    ("freshness", [
        "freshness", "publish date", "发布时间", "dateModified", "新鲜度",
    ]),
    ("retest", [
        "re-test", "retest", "复测", "re-run", "re-score",
    ]),
]

STRINGS = {
    "en": {
        "checklist_title": "Action checklist",
        "schedule_title": "Suggested schedule",
        "schedule_intro": (
            "Durations are effort estimates for a focused remediation team, "
            "derived from this run’s findings — not a fixed multi-week calendar. "
            "Adjust owners and overlap to your capacity; finish with a same-rubric re-test."
        ),
        "day": "Day",
        "days": "days",
        "day_unit": "d",
        "owner": "Owner",
        "outcome": "Outcome",
        "sample": "Sample",
        "total_span": "Estimated span",
        "parallel_note": "Items with the same band may run in parallel when owners differ.",
        "no_items": "No remediation items derived from this run.",
        "retest_title": "Re-test technical + Content GEO on the same question set",
        "retest_detail": "Compare scores and AI/search visibility checks against this baseline.",
        "band_day0": "Day 0",
        "band_prefix": "Day",
        "week_prefix": "Week",
    },
    "zh": {
        "checklist_title": "行动清单",
        "schedule_title": "建议跟进时间表",
        "schedule_intro": (
            "工期按本轮发现的工作量估算（聚焦整改团队），不是固定多周日历。"
            "可按实际产能调整负责人与并行；收尾用同一口径复测。"
        ),
        "day": "第",
        "days": "天",
        "day_unit": "天",
        "owner": "负责人",
        "outcome": "预期结果",
        "sample": "样例",
        "total_span": "预估周期",
        "parallel_note": "同一时间带且负责人不同的事项可并行。",
        "no_items": "本轮未推导出整改项。",
        "retest_title": "用同一问题集复测技术 + 内容 GEO",
        "retest_detail": "对照本次基线比较分数与 AI/搜索可见性检查。",
        "band_day0": "第 0 天",
        "band_prefix": "第",
        "week_prefix": "第",
    },
}


def classify_kind(text: str) -> str:
    blob = (text or "").lower()
    for kind, kws in KIND_RULES:
        for kw in kws:
            if kw.lower() in blob:
                return kind
    return "default"


def _as_item(raw: Any, lang: str, page_count: int | None = None) -> dict | None:
    """Normalize finding/action dict or string into a timeline item."""
    if raw is None:
        return None
    if isinstance(raw, str):
        title = raw.strip()
        if not title:
            return None
        detail = ""
        owner = ""
        sample = ""
        effort = None
        outcome = ""
        sev = ""
    else:
        title = (
            raw.get("title")
            or raw.get("action")
            or raw.get("problem")
            or ""
        ).strip()
        detail = (
            raw.get("detail")
            or raw.get("solution")
            or raw.get("body")
            or ""
        ).strip()
        owner = (raw.get("owner") or "").strip()
        sample = (raw.get("sample") or raw.get("example") or "").strip()
        effort = raw.get("effort_days")
        outcome = (raw.get("outcome") or raw.get("expected_outcome") or "").strip()
        sev = str(raw.get("sev") or raw.get("severity") or "").strip()
        if not title and not detail:
            return None

    blob = f"{title} {detail} {sample}"
    kind = classify_kind(blob)
    days = None
    if effort is not None:
        try:
            days = float(effort)
        except (TypeError, ValueError):
            days = None
    if days is None or days <= 0:
        days = KIND_EFFORT.get(kind, KIND_EFFORT["default"])
        if kind == "title_meta" and page_count:
            # scale 2–5 by sampled page count
            days = max(2.0, min(5.0, 1.5 + page_count / 8.0))
        if kind == "thin_pages" and page_count:
            days = max(3.0, min(10.0, 2.0 + page_count / 4.0))
        if kind == "evergreen":
            # detect "3 pages" / "3+" style multipliers
            m = re.search(r"(\d+)\s*\+?\s*(?:evergreen|pages|页|篇)", blob, re.I)
            if m:
                days = KIND_EFFORT["evergreen"] * max(1, int(m.group(1)))

    if not owner:
        owner = KIND_OWNERS.get(kind, KIND_OWNERS["default"]).get(lang, "eng")

    labels = KIND_LABELS[lang if lang in KIND_LABELS else "en"]
    focus = labels.get(kind, labels["default"])
    if not outcome:
        outcome = focus

    return {
        "kind": kind,
        "title": title or focus,
        "detail": detail,
        "owner": owner,
        "sample": sample,
        "effort_days": round(days, 1),
        "outcome": outcome,
        "sev": sev,
        "focus": focus,
    }


def collect_items(
    sources: Iterable[Any],
    lang: str = "en",
    page_count: int | None = None,
    include_retest: bool = True,
    limit: int = 14,
) -> list[dict]:
    """Build deduped timeline items from mixed findings/actions."""
    items: list[dict] = []
    seen: set[str] = set()
    kinds_seen: set[str] = set()

    for raw in sources or []:
        item = _as_item(raw, lang=lang, page_count=page_count)
        if not item:
            continue
        root = str((raw or {}).get("root_cause_id") or "") if isinstance(raw, dict) else ""
        key = root or re.sub(r"\s+", " ", item["title"].lower())[:80]
        # Prefer keeping distinct titles; also collapse identical kinds / root causes
        # so the same hours are not stacked twice in the timeline.
        kind_collapse = item["kind"] in ("https", "robots_sitemap", "bot_allowlist", "retest", "schema_og")
        if key in seen:
            for existing in items:
                if (existing.get("root_cause_id") or re.sub(r"\s+", " ", existing["title"].lower())[:80]) == key:
                    existing["effort_days"] = max(existing["effort_days"], item["effort_days"])
                    if item["detail"] and item["detail"] not in (existing.get("detail") or ""):
                        existing["detail"] = ((existing.get("detail") or "") + " · " + item["detail"]).strip(" ·")
                    break
            continue
        if kind_collapse and item["kind"] in kinds_seen:
            # merge detail into existing
            for existing in items:
                if existing["kind"] == item["kind"]:
                    if item["detail"] and item["detail"] not in existing["detail"]:
                        existing["detail"] = (existing["detail"] + " · " + item["detail"]).strip(" ·")
                    existing["effort_days"] = max(existing["effort_days"], item["effort_days"])
                    break
            continue
        item["root_cause_id"] = root
        seen.add(key)
        kinds_seen.add(item["kind"])
        items.append(item)
        if len(items) >= limit:
            break

    if include_retest and "retest" not in kinds_seen:
        S = STRINGS[lang if lang in STRINGS else "en"]
        items.append({
            "kind": "retest",
            "title": S["retest_title"],
            "detail": S["retest_detail"],
            "owner": KIND_OWNERS["retest"][lang if lang in KIND_OWNERS["retest"] else "en"],
            "sample": "",
            "effort_days": KIND_EFFORT["retest"],
            "outcome": S["retest_title"],
            "sev": "",
            "focus": KIND_LABELS[lang if lang in KIND_LABELS else "en"]["retest"],
        })

    # Priority order: infra first, then on-page, then content depth, then retest
    order = {
        "https": 0, "bot_allowlist": 1, "robots_sitemap": 2,
        "canonical": 3, "schema_og": 4, "h1_onpage": 5, "title_meta": 6,
        "entity_brand": 7, "freshness": 8, "answer_blocks": 9,
        "thin_pages": 10, "evergreen": 11, "case_narratives": 12,
        "proof_hub": 13, "en_export": 14, "default": 15, "retest": 99,
    }
    items.sort(key=lambda x: (order.get(x["kind"], 50), -{"P0": 3, "critical": 3, "P1": 2, "high": 2, "P2": 1, "medium": 1}.get(str(x.get("sev")).lower(), 0)))
    return items


def _band_label(start: float, end: float, lang: str) -> str:
    """Human band for a [start, end) day window."""
    S = STRINGS[lang if lang in STRINGS else "en"]
    # Round to half-days for display
    s = int(start) if start == int(start) else round(start, 1)
    e = int(end) if end == int(end) else round(end, 1)
    span = max(0.5, end - start)

    if lang == "zh":
        if end <= 1.0:
            return "第 0–1 天"
        if end <= 3.0:
            return f"第 {s:g}–{e:g} 天"
        if span <= 7 and end <= 14:
            return f"第 {s:g}–{e:g} 天"
        # week bands only when work truly spans weeks
        w0 = int(start // 7) + 1
        w1 = max(w0, int((end - 0.01) // 7) + 1)
        if w0 == w1:
            return f"第 {w0} 周"
        return f"第 {w0}–{w1} 周"

    if end <= 1.0:
        return "Day 0–1"
    if end <= 3.0 or (span <= 7 and end <= 14):
        return f"Day {s:g}–{e:g}"
    w0 = int(start // 7) + 1
    w1 = max(w0, int((end - 0.01) // 7) + 1)
    if w0 == w1:
        return f"Week {w0}"
    return f"Week {w0}–{w1}"


def schedule_items(items: list[dict], lang: str = "en") -> list[dict]:
    """Assign start/end day offsets. Light parallelism: infra kinds sequential;
    content kinds with different owners may share a band start.
    """
    cursor = 0.0
    scheduled = []
    # Track last end per owner for light parallelism
    owner_end: dict[str, float] = {}

    infra = {"https", "bot_allowlist", "robots_sitemap", "canonical", "retest"}

    for item in items:
        days = float(item.get("effort_days") or 1)
        owner = item.get("owner") or "eng"
        kind = item.get("kind") or "default"

        if kind in infra or kind == "retest":
            start = cursor
        else:
            # can start when this owner is free, but not before prior infra cursor - 0
            start = max(owner_end.get(owner, 0.0), min(cursor, owner_end.get(owner, 0.0)))
            # keep overall progress sensible: don't start too far behind the frontier
            start = max(start, max(0.0, cursor - 2.0))

        end = start + days
        band = _band_label(start, end, lang)
        row = dict(item)
        row["start"] = round(start, 1)
        row["end"] = round(end, 1)
        row["band"] = band
        row["pct_start"] = 0  # filled after total known
        row["pct_width"] = 0
        scheduled.append(row)
        owner_end[owner] = end
        cursor = max(cursor, end)

    total = max((r["end"] for r in scheduled), default=1.0) or 1.0
    for r in scheduled:
        r["pct_start"] = round(r["start"] / total * 100, 1)
        r["pct_width"] = max(2.0, round((r["end"] - r["start"]) / total * 100, 1))
        r["total_days"] = round(total, 1)
    return scheduled


def format_duration(days: float, lang: str) -> str:
    d = round(float(days), 1)
    if lang == "zh":
        if d <= 1:
            return "≤1 天"
        return f"{d:g} 天"
    if d <= 1:
        return "≤1 day"
    return f"{d:g} days"


def render_checklist(items: list[dict], lang: str = "en", show_samples: bool = False) -> str:
    S = STRINGS[lang if lang in STRINGS else "en"]
    if not items:
        return f'<p class="note">{esc(S["no_items"])}</p>'
    rows = []
    for i, it in enumerate(items, 1):
        sample_html = ""
        if show_samples and it.get("sample"):
            sample_html = (
                f'<div class="sample-block"><span class="sample-label mono">'
                f'{esc(S["sample"])}</span><pre>{esc(it["sample"])}</pre></div>'
            )
        elif show_samples and it.get("detail"):
            # no enrichment sample — still show detail prominently
            sample_html = ""
        detail = it.get("detail") or ""
        sev = it.get("sev") or ""
        sev_html = f'<span class="sev sev-info">{esc(sev)}</span> ' if sev else ""
        rows.append(
            f'<div class="tl-check-row">'
            f'<span class="tl-num mono">{i:02d}</span>'
            f'<div class="tl-check-body">{sev_html}<b>{esc(it.get("title") or "")}</b>'
            f'{f"<p>{esc(detail)}</p>" if detail else ""}'
            f'{sample_html}</div>'
            f'<span class="owner owner-info">{esc(it.get("owner") or "")}</span>'
            f'<span class="tl-dur mono">{esc(format_duration(it.get("effort_days") or 1, lang))}</span>'
            f'</div>'
        )
    return (
        f'<div class="sublab">{esc(S["checklist_title"])}</div>'
        f'<div class="tl-checklist">{"".join(rows)}</div>'
    )


def render_schedule(items: list[dict], lang: str = "en") -> str:
    S = STRINGS[lang if lang in STRINGS else "en"]
    if not items:
        return ""
    scheduled = schedule_items(items, lang=lang)
    total = scheduled[0]["total_days"] if scheduled else 1

    # Axis ticks: Day 0, then every ~25% of span (or weekly if long)
    ticks = []
    if total <= 7:
        step = 1
    elif total <= 21:
        step = 3
    else:
        step = 7
    t = 0.0
    while t <= total + 0.01:
        label = f"{S['band_prefix']} {t:g}{S['day_unit']}" if lang == "zh" else f"D{t:g}"
        if lang == "zh":
            label = f"D{t:g}"
        ticks.append((round(t / total * 100, 1), label))
        t += step
    if ticks[-1][0] < 99:
        ticks.append((100, f"D{total:g}"))

    axis = "".join(
        f'<span class="tl-tick" style="left:{pct}%"><i></i><em class="mono">{esc(lab)}</em></span>'
        for pct, lab in ticks
    )

    bars = []
    for it in scheduled:
        bars.append(
            f'<div class="tl-row">'
            f'<div class="tl-meta"><span class="tl-band mono">{esc(it["band"])}</span>'
            f'<b>{esc(it.get("title") or it.get("focus") or "")}</b>'
            f'<span class="tl-owner-chip">{esc(it.get("owner") or "")}</span>'
            f'<span class="tl-dur-badge mono">{esc(format_duration(it["effort_days"], lang))}</span></div>'
            f'<div class="tl-track"><span class="tl-bar" style="left:{it["pct_start"]}%;width:{it["pct_width"]}%"'
            f' title="{esc(it.get("title") or "")}"></span></div>'
            f'</div>'
        )

    span_label = format_duration(total, lang)
    return (
        f'<div class="sublab">{esc(S["schedule_title"])}</div>'
        f'<p class="note">{esc(S["schedule_intro"])} '
        f'<b>{esc(S["total_span"])}: {esc(span_label)}</b>. {esc(S["parallel_note"])}</p>'
        f'<div class="tl-schedule">'
        f'<div class="tl-axis">{axis}</div>'
        f'{"".join(bars)}'
        f'</div>'
    )


def render_timeline_block(
    sources: Iterable[Any],
    lang: str = "en",
    page_count: int | None = None,
    include_retest: bool = True,
    show_samples: bool = False,
    limit: int = 12,
) -> str:
    """Full checklist + schedule HTML fragment."""
    items = collect_items(
        sources,
        lang=lang,
        page_count=page_count,
        include_retest=include_retest,
        limit=limit,
    )
    return render_checklist(items, lang=lang, show_samples=show_samples) + render_schedule(items, lang=lang)


def css() -> str:
    """Optional extra CSS (also mirrored into report_templates/style.css)."""
    return """
/* ---- remediation timeline (shared) ---- */
.tl-checklist{margin-top:var(--space-3);border-top:2px solid var(--text)}
.tl-check-row{display:grid;grid-template-columns:44px 1fr auto auto;gap:var(--space-3);padding:var(--space-4) 0;border-bottom:1px solid var(--border);align-items:start}
.tl-num{font-size:13px;color:var(--text-3);padding-top:3px}
.tl-check-body b{font-size:15.5px}
.tl-check-body p{margin:4px 0 0;color:var(--text-2);font-size:14px}
.tl-dur{font-size:12.5px;color:var(--text-3);white-space:nowrap;padding-top:4px}
.sample-block{margin-top:10px;background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:10px 12px}
.sample-label{display:inline-block;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--primary);font-weight:600;margin-bottom:6px}
.sample-block pre{margin:0;white-space:pre-wrap;font-family:var(--font-mono);font-size:12.5px;line-height:1.55;color:var(--text);background:transparent;border:0;padding:0}
.tl-schedule{margin-top:var(--space-4);background:var(--surface-2);border:1px solid var(--border);border-radius:14px;padding:18px 18px 12px}
.tl-axis{position:relative;height:28px;margin:0 0 8px 0;border-bottom:1px dashed var(--border-2)}
.tl-tick{position:absolute;top:0;transform:translateX(-50%);text-align:center}
.tl-tick i{display:block;width:1px;height:8px;background:var(--border-2);margin:0 auto 4px}
.tl-tick em{font-style:normal;font-size:10.5px;color:var(--text-3)}
.tl-row{display:grid;grid-template-columns:minmax(180px,1.1fr) 1.4fr;gap:14px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.tl-row:last-child{border-bottom:0}
.tl-meta{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center}
.tl-meta b{font-size:13.5px;flex:1 1 100%}
.tl-band{font-size:11px;letter-spacing:.06em;color:var(--primary);background:var(--primary-light);padding:2px 7px;border-radius:999px;font-weight:600}
.tl-owner-chip{font-size:11.5px;color:var(--text-2);background:var(--surface);border:1px solid var(--border);padding:2px 8px;border-radius:999px}
.tl-dur-badge{font-size:11px;color:var(--text-3);border:1px solid var(--border-2);padding:2px 7px;border-radius:999px}
.tl-track{position:relative;height:16px;background:var(--surface-3);border-radius:999px;overflow:hidden}
.tl-bar{position:absolute;top:0;height:100%;background:linear-gradient(90deg,var(--primary),#818CF8);border-radius:999px;box-shadow:0 0 0 1px rgba(79,70,229,.25)}
.score-preview{margin-top:var(--space-5)}
.score-preview .sp-overall{display:flex;align-items:baseline;gap:12px;margin-bottom:var(--space-4)}
.score-preview .sp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.score-preview .sp-card{background:var(--surface-2);border:1px solid var(--border);border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:8px;text-decoration:none;color:inherit}
.score-preview .sp-card:hover{border-color:var(--primary)}
.score-preview .sp-card .sp-name{font-size:13px;color:var(--text-2);font-weight:600}
.score-preview .sp-card .sp-score{font-family:var(--font-mono);font-size:18px;font-weight:650}
.score-preview .sp-card .sp-score small{font-size:12px;color:var(--text-3);font-weight:500}
.score-preview .sp-bar{height:4px;background:var(--surface-3);border-radius:2px;overflow:hidden}
.score-preview .sp-bar i{display:block;height:100%}
@media (max-width:820px){
 .tl-check-row{grid-template-columns:36px 1fr}
 .tl-check-row .owner,.tl-check-row .tl-dur{justify-self:start}
 .tl-row{grid-template-columns:1fr}
}
"""


if __name__ == "__main__":
    demo = [
        {"title": "Restore HTTPS", "detail": "Fix 500/TLS", "sev": "P0", "owner": "eng/ops"},
        {"title": "Unique titles", "detail": "Per URL", "sev": "P1", "effort_days": 3},
        {"title": "Publish 3 evergreen GEO pages", "detail": "Buyer questions", "sev": "P0", "sample": "H1: How to choose…\nLead: In short…"},
    ]
    print(render_timeline_block(demo, lang="en", show_samples=True)[:500])
