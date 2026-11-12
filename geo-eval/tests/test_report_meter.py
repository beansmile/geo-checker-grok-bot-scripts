#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cover score meter: bands, aligned scale marks, no 0.1-level widths."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import report_meter as rm  # noqa: E402


class MeterBandTests(unittest.TestCase):
    def test_below_60_is_low(self):
        self.assertEqual(rm.meter_band(0), "is-low")
        self.assertEqual(rm.meter_band(54.5), "is-low")
        self.assertEqual(rm.meter_band(59.5), "is-low")

    def test_60_to_below_75_is_mid(self):
        self.assertEqual(rm.meter_band(60), "is-mid")
        self.assertEqual(rm.meter_band(74.5), "is-mid")

    def test_75_and_up_is_high(self):
        self.assertEqual(rm.meter_band(75), "is-high")
        self.assertEqual(rm.meter_band(79.5), "is-high")
        self.assertEqual(rm.meter_band(80), "is-high")
        self.assertEqual(rm.meter_band(100), "is-high")

    def test_missing_is_low(self):
        self.assertEqual(rm.meter_band(None), "is-low")
        self.assertEqual(rm.meter_band(""), "is-low")


class MeterWidthTests(unittest.TestCase):
    def test_display(self):
        self.assertEqual(rm.meter_width(55), "55")
        self.assertEqual(rm.meter_width(54.5), "54.5")
        self.assertEqual(rm.meter_width(55.0), "55")
        self.assertEqual(rm.meter_width(-1), "0")
        self.assertEqual(rm.meter_width(110), "100")


class MeterHtmlTests(unittest.TestCase):
    def test_aligned_marks_and_band(self):
        html = rm.meter_html(54.5, "及格 60", "良好 80")
        self.assertIn('class="cm-fill is-low"', html)
        self.assertIn('style="width:54.5%"', html)
        self.assertIn('class="cm-k cm-k-0"', html)
        self.assertIn('class="cm-k cm-k-60"', html)
        self.assertIn('class="cm-k cm-k-80"', html)
        self.assertIn('class="cm-k cm-k-100"', html)
        self.assertIn("及格 60", html)
        self.assertIn("良好 80", html)
        # must not use equally spaced unlabeled spans
        self.assertNotIn("<div class=\"cm-scale\"><span>0</span>", html)

    def test_labels_are_escaped(self):
        html = rm.meter_html(80, "<Pass>", 'Good "80"')
        self.assertIn("&lt;Pass&gt;", html)
        self.assertNotIn("<Pass>", html)

    def test_high_band_integer_width(self):
        html = rm.meter_html(88, "Pass 60", "Good 80")
        self.assertIn('class="cm-fill is-high"', html)
        self.assertIn('style="width:88%"', html)


class SharedCssTests(unittest.TestCase):
    def setUp(self):
        self.css = (ROOT / "report_templates" / "style.css").read_text(encoding="utf-8")

    def test_scale_marks_at_true_percentages(self):
        self.assertIn(".cm-k-60{left:60%}", self.css)
        self.assertIn(".cm-k-80{left:80%}", self.css)
        self.assertIn(".cm-k-0{left:0;transform:none}", self.css)
        self.assertIn(".cm-k-100{left:100%;transform:translateX(-100%)}", self.css)
        self.assertNotIn("justify-content:space-between;margin-top:8px;font-size:11.5px;color:#A5B4FC", self.css)

    def test_band_colors(self):
        self.assertIn(".cm-fill.is-low{background:#F87171}", self.css)
        self.assertIn(".cm-fill.is-mid{background:#FBBF24}", self.css)
        self.assertIn(".cm-fill.is-high{background:#34D399}", self.css)

    def test_print_keeps_band_colors(self):
        # print must not force a single dark fill over the band classes
        print_block = self.css.split("@media print")[1]
        self.assertIn(".cm-fill.is-low{background:#DC2626}", print_block)
        self.assertIn(".cm-fill.is-mid{background:#D97706}", print_block)
        self.assertIn(".cm-fill.is-high{background:#15803D}", print_block)
        # the unclassed fallback may remain, but band rules must come first
        low_at = print_block.find(".cm-fill.is-low")
        fallback_at = print_block.find(".cm-fill{background:#0F172A}")
        self.assertGreater(low_at, 0)
        self.assertGreater(fallback_at, low_at)




class IndexChromeTests(unittest.TestCase):
    def test_overlay_and_topbar(self):
        import report_chrome as rc
        html = rc.index_overlay([("cover", "封面"), ("scores", "分数构成")], lang="zh")
        self.assertIn('id="index"', html)
        self.assertIn('href="#cover"', html)
        self.assertIn("报告索引", html)
        self.assertIn("关闭 (ESC)", html)
        self.assertIn("封面", html)
        bar = rc.topbar_index(10, lang="zh")
        self.assertIn("索引", bar)
        self.assertIn("01 / 10", bar)
        self.assertIn('id="now-page"', bar)
        en = rc.index_overlay([("cover", "Cover")], lang="en")
        self.assertIn("Report index", en)
        self.assertIn("Close (ESC)", en)

    def test_strip_section_number(self):
        import report_chrome as rc
        self.assertEqual(rc.strip_section_number("01 综合结论"), "综合结论")
        self.assertEqual(rc.strip_section_number("03 Technical summary"), "Technical summary")
        self.assertEqual(rc.strip_section_number("信息架构"), "信息架构")



class BuiltReportIndexTests(unittest.TestCase):
    """Content and combined HTML include the technical-report index chrome."""

    ZH = Path("/workspace/skills/geo-eval/runs/nanxing.com/2026-11-12_run01")

    def test_content_index_chrome(self):
        import json, sys
        sys.path.insert(0, str(Path("/workspace/skills/geo-eval/scripts")))
        from build_content_report import render_html
        data = json.loads((self.ZH / "content_report.json").read_text(encoding="utf-8"))
        html = render_html(data, "", lang="zh")
        self.assertIn('id="index"', html)
        self.assertIn(">索引</button>", html)
        self.assertIn('id="now-page"', html)
        self.assertIn("报告索引", html)
        self.assertIn("function go(i)", html)
        self.assertIn("Escape", html)
        self.assertIn("keydown", html)
        for a in ("cover", "overall", "method", "strengths", "dim1", "ia",
                  "questions", "actions", "followup", "scope"):
            self.assertIn(f'href="#{a}"', html)
        self.assertIn("信息架构", html)
        self.assertIn("分类与缺口", html)
        self.assertIn("写作质量", html)
        self.assertIn("权威与证据", html)
        self.assertIn("采购问题覆盖", html)
        self.assertNotIn("Information architecture", html)
        self.assertIn('class="cm-fill is-low"', html)
        # progress width is driven by deck.js, not a fixed inline style
        self.assertNotIn('class="progress"><i style="width:', html)
        self.assertIn('history.replaceState(null,\'\',\'#\'+id)', html.replace(" ", ""))

    def test_combined_index_chrome(self):
        import json, sys
        sys.path.insert(0, str(Path("/workspace/skills/geo-eval/scripts")))
        from build_combined_report import render_html, find_tech_report, find_content_report
        tech = find_tech_report(str(self.ZH))
        content = find_content_report(str(self.ZH), "zh")
        html = render_html(tech, content, "", lang="zh", brand="南兴装备中文站")
        self.assertIn('id="index"', html)
        self.assertIn(">索引</button>", html)
        self.assertIn("报告索引", html)
        self.assertIn("function go(i)", html)
        for a in ("cover", "conclusion", "scores", "tech", "content",
                  "shared", "timeline", "scope", "closing", "sources"):
            self.assertIn(f'href="#{a}"', html)
        self.assertIn("综合结论", html)
        self.assertIn("参考来源", html)
        self.assertIn('class="cm-fill is-low"', html)

    def test_english_labels(self):
        import json, sys
        sys.path.insert(0, str(Path("/workspace/skills/geo-eval/scripts")))
        from build_content_report import render_html
        data = json.loads((self.ZH / "content_report.json").read_text(encoding="utf-8"))
        html = render_html(data, "", lang="en")
        self.assertIn(">Index</button>", html)
        self.assertIn("Report index", html)
        self.assertIn("Close (ESC)", html)
        self.assertIn("Cover", html)


if __name__ == "__main__":
    unittest.main()
