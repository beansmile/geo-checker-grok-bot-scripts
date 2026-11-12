#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cover-page score meter: 0.5-aligned width, band colors, and exact scale marks.

Color bands (scale ticks stay at 及格 60 / 良好 80):
  < 60  → is-low  (red)
  < 75  → is-mid  (yellow)
  >= 75 → is-high (green)
"""

from __future__ import annotations

import html as html_mod


def meter_band(score) -> str:
    """CSS band class for a 0–100 score."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        s = 0.0
    if s < 60:
        return "is-low"
    if s < 75:
        return "is-mid"
    return "is-high"


def meter_width(score) -> str:
    """CSS width percentage: integers without .0, otherwise one decimal."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        s = 0.0
    s = max(0.0, min(100.0, s))
    if s == int(s):
        return str(int(s))
    return f"{s:.1f}"


def meter_html(score, pass_label: str = "及格 60", good_label: str = "良好 80") -> str:
    """Cover meter markup. Labels are HTML-escaped."""
    band = meter_band(score)
    width = meter_width(score)
    pass_l = html_mod.escape(str(pass_label))
    good_l = html_mod.escape(str(good_label))
    return (
        f'<div class="cmeter">'
        f'<div class="cm-track">'
        f'<span class="cm-fill {band}" style="width:{width}%"></span>'
        f"</div>"
        f'<div class="cm-scale">'
        f'<span class="cm-k cm-k-0">0</span>'
        f'<span class="cm-k cm-k-60">{pass_l}</span>'
        f'<span class="cm-k cm-k-80">{good_l}</span>'
        f'<span class="cm-k cm-k-100">100</span>'
        f"</div></div>"
    )
