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

    def test_60_to_below_80_is_mid(self):
        self.assertEqual(rm.meter_band(60), "is-mid")
        self.assertEqual(rm.meter_band(79.5), "is-mid")

    def test_80_and_up_is_high(self):
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


if __name__ == "__main__":
    unittest.main()
