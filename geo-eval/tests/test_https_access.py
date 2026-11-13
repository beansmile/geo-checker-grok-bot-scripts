#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ACC-05 HTTPS penalties are core score adjustments."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import https_access  # noqa: E402
import analyze  # noqa: E402
from test_scoring_iteration import write_run, HOME  # noqa: E402


ABOUT = """<!doctype html><html lang="en"><head><title>About Acme Tools</title>
<meta name="description" content="About Acme Tools."></head>
<body><h1>About</h1><p>Acme Tools was founded in 1994 in Portland.</p></body></html>"""


class EvaluateAcc05Tests(unittest.TestCase):
    def test_no_https_is_minus_10_only(self):
        result = https_access.evaluate_acc05({
            "official_url": "http://www.kojo.cn/",
            "https": False,
            "http_redirects_to_https": False,
            "redirect_hops": 5,
            "https_error": "certificate hostname mismatch",
        })
        self.assertEqual(result["penalty"], 10)
        self.assertEqual([a["points"] for a in result["adjustments"]], [-10])
        self.assertEqual(result["adjustments"][0]["reason"], "网站不是 HTTPS")
        self.assertEqual(result["findings"][0]["id"], "ACC-05")
        self.assertTrue(result["findings"][0]["scored"])

    def test_https_without_http_redirect_is_minus_3(self):
        result = https_access.evaluate_acc05({
            "official_url": "https://www.example.com/",
            "https": True,
            "http_redirects_to_https": False,
            "redirect_hops": 0,
        })
        self.assertEqual(result["penalty"], 3)
        self.assertEqual(result["adjustments"][0]["reason"], "已是 HTTPS，但 HTTP 没有跳转到 HTTPS")

    def test_https_with_more_than_two_hops_is_minus_3(self):
        result = https_access.evaluate_acc05({
            "official_url": "https://www.example.com/",
            "https": True,
            "http_redirects_to_https": True,
            "redirect_hops": 3,
        })
        self.assertEqual(result["penalty"], 3)
        self.assertIn("主 URL 跳转超过 2 次", result["adjustments"][0]["reason"])

    def test_https_redirect_and_hops_can_stack(self):
        result = https_access.evaluate_acc05({
            "official_url": "https://www.example.com/",
            "https": True,
            "http_redirects_to_https": False,
            "redirect_hops": 4,
        })
        self.assertEqual(result["penalty"], 6)
        self.assertEqual([a["points"] for a in result["adjustments"]], [-3, -3])

    def test_clean_https_is_not_penalized(self):
        result = https_access.evaluate_acc05({
            "official_url": "https://www.example.com/",
            "https": True,
            "http_redirects_to_https": True,
            "redirect_hops": 1,
        })
        self.assertEqual(result["penalty"], 0)
        self.assertEqual(result["adjustments"], [])
        self.assertEqual(result["findings"], [])

    def test_cert_mismatch_alone_does_not_penalize_usable_https(self):
        # TEC-04 warning: apex cert issues are not ACC-05 if official HTTPS works.
        result = https_access.evaluate_acc05({
            "official_url": "https://www.example.com/",
            "https": True,
            "http_redirects_to_https": True,
            "redirect_hops": 0,
            "https_error": "",
            "apex_tls_ok": False,
            "apex_tls_error": "certificate hostname mismatch for example.com",
        })
        self.assertEqual(result["penalty"], 0)

    def test_scheme_fallback_http_is_s1(self):
        info = https_access.infer_from_official_url("http://www.kojo.cn/")
        result = https_access.evaluate_acc05(info)
        self.assertFalse(info["https"])
        self.assertEqual(result["penalty"], 10)

    def test_scheme_fallback_https_does_not_guess_redirect_or_hops(self):
        info = https_access.infer_from_official_url("https://www.example.com/")
        result = https_access.evaluate_acc05(info)
        self.assertTrue(info["https"])
        self.assertIsNone(info["http_redirects_to_https"])
        self.assertIsNone(info["redirect_hops"])
        self.assertEqual(result["penalty"], 0)


class AnalyzeAcc05Tests(unittest.TestCase):
    def _analyze(self, official, https_evidence=None):
        pages = [
            (official, HOME.replace("https://www.acme-tools.com", official.rstrip("/"))),
            (official.rstrip("/") + "/about/", ABOUT),
        ]
        with tempfile.TemporaryDirectory() as td:
            write_run(td, pages=pages, robots="User-agent: *\nAllow: /\n")
            if https_evidence is not None:
                ev = Path(td) / "evidence"
                ev.mkdir(parents=True, exist_ok=True)
                (ev / "https.json").write_text(json.dumps(https_evidence), encoding="utf-8")
            return analyze.analyze(td)

    def test_analyze_http_official_drops_10_from_overall(self):
        # Same site, only the official scheme / ACC-05 evidence changes.
        https_clean = self._analyze(
            "https://www.acme-tools.com/",
            {
                "official_url": "https://www.acme-tools.com/",
                "https": True,
                "http_redirects_to_https": True,
                "redirect_hops": 0,
                "probed": True,
            },
        )
        http_only = self._analyze(
            "http://www.acme-tools.com/",
            {
                "official_url": "http://www.acme-tools.com/",
                "https": False,
                "http_redirects_to_https": False,
                "redirect_hops": 0,
                "probed": True,
                "https_error": "certificate hostname mismatch",
            },
        )
        self.assertEqual(https_clean["penalty"], 0)
        self.assertEqual(http_only["penalty"], 10)
        self.assertEqual(http_only["overall_score"], https_clean["overall_score"] - 10)
        reasons = [a.get("reason") for a in http_only.get("adjustments") or []]
        self.assertIn("网站不是 HTTPS", reasons)
        ids = [f.get("id") for f in http_only.get("findings") or []]
        self.assertIn("ACC-05", ids)

    def test_analyze_http_scheme_without_probe_still_deducts(self):
        report = self._analyze("http://www.acme-tools.com/")
        self.assertEqual(report["penalty"], 10)
        self.assertIn("网站不是 HTTPS", [a.get("reason") for a in report.get("adjustments") or []])


if __name__ == "__main__":
    unittest.main()
