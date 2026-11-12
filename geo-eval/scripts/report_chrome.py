#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared report chrome: top-bar index button, overlay, and deck.js."""

from __future__ import annotations

import html as html_mod
import os
import re

_INDEX_UI = {
    "zh": {
        "btn": "索引",
        "title": "报告索引",
        "close": "关闭 (ESC)",
        "now": "节",
        "cover": "封面",
    },
    "en": {
        "btn": "Index",
        "title": "Report index",
        "close": "Close (ESC)",
        "now": "Section",
        "cover": "Cover",
    },
}


def index_ui(lang: str = "zh") -> dict:
    return _INDEX_UI["en"] if lang == "en" else _INDEX_UI["zh"]


def strip_section_number(label: str) -> str:
    """Drop a leading '01 ' / '03 ' so the mono page number is not duplicated."""
    return re.sub(r"^\d+\s+", "", str(label or "")).strip()


def index_overlay(entries, lang: str = "zh") -> str:
    """entries: iterable of (anchor, label)."""
    ui = index_ui(lang)
    links = []
    for i, item in enumerate(entries, 1):
        anchor, label = item[0], item[1]
        links.append(
            f'<a href="#{html_mod.escape(str(anchor))}">'
            f'<span class="mono">{i:02d}</span>'
            f"{html_mod.escape(str(label))}</a>"
        )
    return (
        f'<div class="index" id="index" role="dialog" aria-modal="true" '
        f'aria-label="{html_mod.escape(ui["title"])}">'
        f'<div class="index-panel">'
        f'<button class="btn close" type="button">{html_mod.escape(ui["close"])}</button>'
        f'<h2>{html_mod.escape(ui["title"])}</h2>'
        f'<div class="index-list">{"".join(links)}</div>'
        f"</div></div>"
    )


def topbar_index(total_pages: int, lang: str = "zh") -> str:
    """Section counter + Index button, for the topbar .right group."""
    ui = index_ui(lang)
    pad = f"{int(total_pages):02d}"
    return (
        f'<span class="now">{html_mod.escape(ui["now"])} '
        f'<b id="now-page">01 / {pad}</b></span>'
        f'<button class="btn" type="button" '
        f"onclick=\"document.getElementById('index').classList.add('show')\">"
        f'{html_mod.escape(ui["btn"])}</button>'
    )


def load_deck_js(lang: str = "zh") -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(os.path.dirname(here), "report_templates", "deck.js")
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        js = f.read()
    if lang == "en":
        js = js.replace("已复制", "Copied")
    return js


CONTENT_DIM_NAMES = {
    "en": {
        "information_architecture": "Information architecture",
        "taxonomy_gaps": "Content taxonomy & gaps",
        "writing_quality": "Writing quality",
        "authority_evidence": "Authority & evidence publishing",
        "query_coverage": "Target query coverage",
    },
    "zh": {
        "information_architecture": "信息架构",
        "taxonomy_gaps": "分类与缺口",
        "writing_quality": "写作质量",
        "authority_evidence": "权威与证据",
        "query_coverage": "采购问题覆盖",
    },
}


def content_dim_name(dim: dict, lang: str) -> str:
    """Localized Content GEO dimension name; falls back to dim['name']."""
    key = (dim or {}).get("key") or ""
    if lang == "zh":
        if (dim or {}).get("name_zh"):
            return dim["name_zh"]
        if key in CONTENT_DIM_NAMES["zh"]:
            return CONTENT_DIM_NAMES["zh"][key]
    if key in CONTENT_DIM_NAMES.get(lang, {}):
        return CONTENT_DIM_NAMES[lang][key]
    return (dim or {}).get("name") or key or "—"
