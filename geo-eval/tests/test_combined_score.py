#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Combined GEO score: 40/60 weights, snap_half, access gates, display, sources."""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import combined_score as cs  # noqa: E402
import build_combined_report as bcr  # noqa: E402


def _tech(overall, **kwargs):
    data = {"overall_score": overall, "grade": kwargs.pop("grade", "D")}
    data.update(kwargs)
    return data


def _content(overall, **kwargs):
    data = {"overall_score": overall, "grade": kwargs.pop("grade", "D")}
    data.update(kwargs)
    return data


class CombinedFormulaTests(unittest.TestCase):
    def test_nanxing_zh_site_numbers(self):
        r = cs.compute_combined(48, 58.5, {"cap": None})
        self.assertAlmostEqual(r["raw_weighted"], 54.3, places=9)
        self.assertEqual(r["overall_score"], 54.5)
        self.assertEqual(r["grade"], "D")
        self.assertEqual(cs.format_score(r["overall_score"]), "54.5")

    def test_nanxing_en_site_numbers(self):
        r = cs.compute_combined(59, 52.5, {"cap": None})
        self.assertAlmostEqual(r["raw_weighted"], 55.1, places=9)
        self.assertEqual(r["overall_score"], 55.0)
        self.assertEqual(r["grade"], "D")
        self.assertEqual(cs.format_score(r["overall_score"]), "55")

    def test_snap_half_on_combined(self):
        # Halfway cases move away from zero, same helper as content_analyze.
        self.assertEqual(cs.snap_half(54.3), 54.5)
        self.assertEqual(cs.snap_half(55.1), 55.0)
        self.assertEqual(cs.snap_half(54.25), 54.5)
        self.assertEqual(cs.snap_half(54.24), 54.0)
        self.assertEqual(cs.snap_half(0), 0.0)
        self.assertEqual(cs.compute_combined(0, 0)["overall_score"], 0.0)
        self.assertEqual(cs.compute_combined(100, 100)["overall_score"], 100.0)

    def test_soft_gate_caps_at_50(self):
        # Example from the plan: tech 35 (already includes core access penalty),
        # content 80 → weighted 62.0, capped at 50.
        gate = cs.detect_access_gate({
            "overall_score": 35,
            "core_search_access_penalty": True,
            "googlebot_blocked": False,
            "all_search_crawlers_blocked": False,
        })
        self.assertTrue(gate["core_search_access_penalty"])
        self.assertFalse(gate["googlebot_blocked"])
        self.assertEqual(gate["cap"], 50)
        r = cs.compute_combined(35, 80, gate)
        self.assertAlmostEqual(r["raw_weighted"], 62.0, places=9)
        self.assertEqual(r["overall_score"], 50.0)
        self.assertEqual(r["grade"], "D")
        self.assertEqual(cs.format_score(r["overall_score"]), "50")

    def test_hard_gate_caps_at_30(self):
        gate = cs.detect_access_gate({
            "overall_score": 35,
            "core_search_access_penalty": True,
            "googlebot_blocked": True,
        })
        self.assertEqual(gate["cap"], 30)
        r = cs.compute_combined(35, 80, gate)
        self.assertEqual(r["overall_score"], 30.0)
        self.assertEqual(cs.format_score(r["overall_score"]), "30")

    def test_all_search_crawlers_blocked_is_hard_gate(self):
        gate = cs.detect_access_gate({
            "overall_score": 40,
            "all_search_crawlers_blocked": True,
            "googlebot_blocked": False,
            "core_search_access_penalty": False,
        })
        self.assertEqual(gate["cap"], 30)
        r = cs.compute_combined(40, 90, gate)
        self.assertEqual(r["overall_score"], 30.0)

    def test_training_crawler_block_does_not_trigger_gate(self):
        tech = {
            "overall_score": 59,
            "penalty": 0,
            "scope": {
                "blocked": [],
                "blocked_all": ["GPTBot", "ClaudeBot", "Google-Extended"],
                "blocked_training": ["GPTBot", "ClaudeBot", "Google-Extended"],
                "crawler_access": {
                    "ai_blocked": [],
                    "training_blocked_live": ["GPTBot", "ClaudeBot"],
                    "roles": {
                        "search_index": ["Googlebot", "OAI-SearchBot"],
                        "core_blocked": [],
                        "training_blocked": ["GPTBot", "ClaudeBot"],
                    },
                    "engines": {
                        "chatgpt_search": {
                            "search_token": "OAI-SearchBot",
                            "search_status": "allowed",
                            "training_token": "GPTBot",
                            "training_live": "blocked",
                            "training_robots_blocked": True,
                        }
                    },
                },
            },
        }
        gate = cs.detect_access_gate(tech)
        self.assertFalse(gate["applied"])
        self.assertIsNone(gate["cap"])
        r = cs.compute_combined(59, 52.5, gate)
        self.assertEqual(r["overall_score"], 55.0)

    def test_unverified_search_crawler_does_not_trigger_gate(self):
        tech = {
            "overall_score": 70,
            "scope": {
                "crawler_access": {
                    "roles": {"core_blocked": []},
                    "engines": {
                        "claude_search": {
                            "search_token": "Claude-SearchBot",
                            "search_status": "unverified",
                        }
                    },
                }
            },
        }
        gate = cs.detect_access_gate(tech)
        self.assertFalse(gate["applied"])

    def test_core_penalty_from_adjustments(self):
        tech = {
            "overall_score": 35,
            "penalty": 15,
            "score_adjustments": {
                "adjustments": [
                    {"type": "penalty", "points": -15, "reason": "搜索/按需抓取爬虫不可达"}
                ]
            },
        }
        gate = cs.detect_access_gate(tech)
        self.assertTrue(gate["core_search_access_penalty"])
        self.assertEqual(gate["cap"], 50)

    def test_missing_side_emits_no_score(self):
        self.assertTrue(cs.compute_combined(None, 58.5)["missing"])
        self.assertIsNone(cs.compute_combined(None, 58.5)["overall_score"])
        self.assertIsNone(cs.compute_combined(48, None)["overall_score"])
        self.assertIsNone(cs.compute_combined("", 50)["grade"])

    def test_display_integers_vs_half(self):
        self.assertEqual(cs.format_score(55.0), "55")
        self.assertEqual(cs.format_score(54.5), "54.5")
        self.assertEqual(cs.format_score(4.0), "4")
        self.assertEqual(cs.format_score(18), "18")
        self.assertEqual(cs.format_score(0), "0")
        self.assertEqual(cs.format_score(13.0), "13")
        self.assertEqual(cs.format_score(15.0), "15")
        self.assertEqual(cs.format_score(None), "—")

    def test_grade_bands(self):
        self.assertEqual(cs.grade_for(90), "A+")
        self.assertEqual(cs.grade_for(89.5), "A")
        self.assertEqual(cs.grade_for(80), "A")
        self.assertEqual(cs.grade_for(79.5), "B")
        self.assertEqual(cs.grade_for(60), "C")
        self.assertEqual(cs.grade_for(59.5), "D")
        self.assertEqual(cs.grade_for(0), "D")


class CombinedHtmlTests(unittest.TestCase):
    def _render(self, tech, content, lang="zh"):
        return bcr.render_html(tech, content, style_css="", lang=lang, brand=None)

    def test_missing_side_html_has_no_combined_number(self):
        html = self._render(
            {"overall_score": 48, "grade": "D", "domain": "example.com"},
            {"domain": "example.com"},  # no overall_score
            lang="zh",
        )
        self.assertIn("不发布综合分", html)
        self.assertNotIn("抽样页综合分 54", html)
        # Combined headline should be an em dash, not an invented number.
        self.assertIn("—<small>/100</small>", html)
        self.assertIn("/100", html)
        self.assertNotIn("54.5", html)

    def test_sources_and_disclaimer(self):
        html = self._render(
            _tech(48, domain="example.com", scope={"score_scope": "sampled_pages"}),
            _content(58.5, domain="example.com", overall_summary="这是抽样页得分。"),
            lang="zh",
        )
        self.assertIn("下列资料用于说明评分原则", html)
        self.assertIn("并不表示这些机构发布或认可本报告的具体分数与权重", html)
        for url in (
            "https://developers.google.com/search/docs/appearance/ai-features",
            "https://developers.google.com/search/blog/2025/05/succeeding-in-ai-search",
            "https://developers.google.com/search/docs/fundamentals/ai-optimization-guide",
            "https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
            "https://developers.google.com/search/docs/essentials",
            "https://developers.google.com/search/docs/essentials/technical",
            "https://developers.openai.com/api/docs/bots",
            "https://help.openai.com/en/articles/9237897-searching-the-web-with-chatgpt",
            "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler",
            "https://developers.facebook.com/docs/sharing/webmasters/web-crawlers",
            "https://www.kimi.com/policies/kimi-crawlers",
            "https://doi.org/10.1145/3637528.3671900",
            "https://arxiv.org/abs/2311.09735",
        ):
            self.assertIn(url, html)
        forbidden = (
            "12627856-publishers-and-developers-faq",
            "geotest",
            "searchscore",
            "geoready",
            "geoscore.dev",
            "brandviz",
            "deepseek",
            "豆包",
            "通义",
            "智谱",
        )
        low = html.lower()
        for token in forbidden:
            self.assertNotIn(token, low)
        self.assertNotIn("按 Google / OpenAI 官方权重", html)
        self.assertNotIn("按 Google 或 OpenAI 官方权重", html)
        self.assertIn("不是任何一家厂商或论文公布的比例", html)
        self.assertIn("与本报告 40% 的技术权重不是同一回事", html)
        self.assertIn("抽样页综合分", html)
        self.assertIn("54.5", html)
        self.assertNotIn("54.3", html)
        self.assertNotIn("58.3", html)
        # No customer-facing version strings
        self.assertIsNone(re.search(r"rubric[_\s-]*v?\d", html, re.I))
        self.assertNotIn("v1.2", html)
        self.assertNotIn("v1.3", html)

    def test_integer_display_in_html(self):
        html = self._render(
            _tech(59, domain="example.com", scope={"score_scope": "sampled_pages"}),
            _content(
                52.5,
                domain="example.com",
                overall_summary="抽样页得分。",
                dimensions=[
                    {"key": "information_architecture", "name": "Information architecture", "score": 13.0, "max": 20, "grade": "C"},
                    {"key": "writing_quality", "name": "Writing quality", "score": 15.0, "max": 20, "grade": "B"},
                    {"key": "authority_evidence", "name": "Authority", "score": 0, "max": 20, "grade": "D"},
                ],
            ),
            lang="zh",
        )
        self.assertIn(">55<", html)  # combined integer, no trailing .0
        self.assertNotIn("55.0", html)
        self.assertNotIn("55.1", html)
        self.assertNotIn("52.6", html)
        self.assertIn("信息架构", html)
        self.assertIn(">13<", html)
        self.assertIn(">15<", html)
        self.assertIn(">0<", html)
        self.assertNotIn("13.0", html)
        self.assertNotIn("15.0", html)
        self.assertIn("访问门槛未生效", html)


class CombinedNanxingIntegrationTests(unittest.TestCase):
    """Build from the existing Nanxing runs when present; skip otherwise."""

    ZH = Path("/workspace/skills/geo-eval/runs")

    def _run_dir(self, site: str) -> Path:
        return self.ZH / site / "2026-11-12_run01"

    def test_nanxing_com_from_existing_run(self):
        run = self._run_dir("nanxing.com")
        if not (run / "report.json").is_file():
            self.skipTest("nanxing.com run not present")
        tech = bcr.find_tech_report(str(run))
        content = bcr.find_content_report(str(run), "zh")
        result = cs.score_from_reports(tech, content)
        self.assertEqual(result["tech_overall"], 48)
        self.assertEqual(result["content_overall"], 58.5)
        self.assertEqual(result["overall_score"], 54.5)
        self.assertEqual(result["grade"], "D")
        self.assertTrue(result["sampled"])
        self.assertFalse(result["gate"]["applied"])
        html = bcr.render_html(tech, content, "", lang="zh", brand=None)
        self.assertIn("抽样页综合分", html)
        self.assertIn("54.5", html)
        self.assertIn(">48<", html)
        self.assertIn("58.5", html)
        self.assertIn("访问门槛未生效", html)
        self.assertIn("约 15 个抽样页", html)
        for bad in ("7.3", "15.1", "54.3", "55.1", "58.3", "52.6"):
            # Allow CSS widths like 52.5%; forbid these as standalone score tokens.
            self.assertIsNone(
                re.search(rf"(?<![\d.]){re.escape(bad)}(?![\d%])", html),
                f"{bad} appeared as a score in the Chinese combined HTML",
            )
        self.assertNotIn("12627856-publishers-and-developers-faq", html)
        self.assertNotIn("v1.", html)
        self.assertIn("信息架构", html)
        self.assertIn("17.5", html)
        self.assertIn("11.5", html)
        self.assertIn("7.5", html)
        self.assertIn(">4<", html)
        self.assertIn(">18<", html)

    def test_nanxingmac_com_from_existing_run(self):
        run = self._run_dir("nanxingmac.com")
        if not (run / "report.json").is_file():
            self.skipTest("nanxingmac.com run not present")
        tech = bcr.find_tech_report(str(run))
        content = bcr.find_content_report(str(run), "zh")
        result = cs.score_from_reports(tech, content)
        self.assertEqual(result["tech_overall"], 59)
        self.assertEqual(result["content_overall"], 52.5)
        self.assertEqual(result["overall_score"], 55.0)
        self.assertEqual(cs.format_score(result["overall_score"]), "55")
        self.assertEqual(result["grade"], "D")
        self.assertTrue(result["sampled"])
        self.assertFalse(result["gate"]["applied"])
        html = bcr.render_html(tech, content, "", lang="zh", brand=None)
        self.assertIn("抽样页综合分", html)
        self.assertIn(">55<", html)
        self.assertNotIn("55.0", html)
        self.assertNotIn("55.1", html)
        self.assertIn("访问门槛未生效", html)
        # Training blocks on this site must not be described as a combined-score gate.
        self.assertNotIn("访问门槛已生效", html)


class CombinedCliTests(unittest.TestCase):
    def test_cli_writes_html_and_json(self):
        run = Path("/workspace/skills/geo-eval/runs/nanxing.com/2026-11-12_run01")
        if not (run / "report.json").is_file():
            self.skipTest("nanxing.com run not present")
        with tempfile.TemporaryDirectory() as tmp:
            prev = sys.argv
            try:
                sys.argv = [
                    "build_combined_report.py",
                    str(run),
                    "--content-run",
                    str(run),
                    "--lang",
                    "zh",
                    "--out-dir",
                    tmp,
                ]
                bcr.main()
            finally:
                sys.argv = prev
            html_path = Path(tmp) / "综合报告.html"
            json_path = Path(tmp) / "综合报告.json"
            self.assertTrue(html_path.is_file())
            self.assertTrue(json_path.is_file())
            payload = __import__("json").loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["combined"]["overall_score"], 54.5)
            self.assertEqual(payload["combined"]["grade"], "D")
            self.assertTrue(payload["combined"]["sampled"])
            self.assertNotIn("rubric_version", payload)
            self.assertNotIn("rules_version", payload)


if __name__ == "__main__":
    unittest.main()
