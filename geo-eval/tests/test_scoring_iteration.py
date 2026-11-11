#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acceptance tests for the scoring-iteration contract (crawler split,
unsampled ≠ missing, schema/entity split, llms.txt out of core, CLN-08
tiers, numeric verification-first, formula consistency)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import citability  # noqa: E402
import crawler_roles  # noqa: E402
import entity_signals  # noqa: E402
import llms_detect  # noqa: E402
import page_coverage  # noqa: E402
import analyze  # noqa: E402
import run as runmod  # noqa: E402


def _page(url, html, role="content", page_type=None):
    # Minimal page dict compatible with analyze.load_pages output fields we need
    # when calling lower-level functions directly. For analyze.analyze(), we
    # write HTML fixtures instead.
    return {"url": url, "html": html, "role": role, "page_type": page_type}


def write_run(root, *, pages, robots="", llms=None, crawler=None, sitemap_urls=None, domain="acme-tools.com"):
    ev = Path(root) / "evidence" / "pages"
    ev.mkdir(parents=True, exist_ok=True)
    (Path(root) / "evidence").mkdir(parents=True, exist_ok=True)
    lines = []
    for i, (url, html) in enumerate(pages):
        slug = "home" if i == 0 else f"p{i}"
        (ev / f"{slug}.html").write_text(html, encoding="utf-8")
        lines.append(f"{slug}|{url}")
    (ev / "pages.list").write_text("\n".join(lines), encoding="utf-8")
    (Path(root) / "evidence" / "robots.txt").write_bytes(robots.encode("utf-8") if isinstance(robots, str) else robots)
    site = {
        "url": pages[0][0],
        "domain": domain,
        "registrable_domain": domain,
        "sitemap": {"url_count": len(sitemap_urls or pages)},
        "pages_sampled": [{"url": u, "status": 200} for u, _ in pages],
        "scope_warnings": [],
    }
    (Path(root) / "site.json").write_text(json.dumps(site), encoding="utf-8")
    if sitemap_urls:
        locs = "".join(f"<loc>{u}</loc>" for u in sitemap_urls)
        (Path(root) / "evidence" / "sitemap.xml").write_text(
            f'<?xml version="1.0"?><urlset>{locs}</urlset>', encoding="utf-8"
        )
    if llms is not None:
        body, meta = llms if isinstance(llms, tuple) else (llms, {})
        if isinstance(body, str):
            body = body.encode("utf-8")
        (Path(root) / "evidence" / "llms.txt").write_bytes(body)
        if meta:
            (Path(root) / "evidence" / "llms.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    if crawler is not None:
        (Path(root) / "evidence" / "crawler_access.json").write_text(
            json.dumps(crawler), encoding="utf-8"
        )
    return root


HOME = """<!doctype html><html lang="en"><head><title>Acme Tools official site</title>
<meta name="description" content="Acme Tools makes industrial saws.">
</head><body>
<h1>Acme Tools</h1>
<p>Acme Tools was founded in 1994 in Portland. Call +1-503-555-0199. Address: 100 Pine Street, Portland.</p>
<p>Our core business is industrial cutting tools and after-sales service.</p>
<a href="https://www.linkedin.com/company/acme-tools">LinkedIn</a>
</body></html>"""

ABOUT = """<!doctype html><html lang="en"><head><title>About Acme Tools</title></head>
<body><h1>About Acme Tools</h1>
<p>Acme Tools was founded in 1994 and still operates from 100 Pine Street, Portland, Oregon.
The company designs and manufactures industrial cutting tools for factories and workshops.
Customers can call +1-503-555-0199 or email sales@acme-tools.com for product support.
Our core business covers saw systems, spare parts, and after-sales service worldwide.</p>
</body></html>"""


class CrawlerSplitTests(unittest.TestCase):
    def test_gptbot_denied_oai_allowed_is_not_chatgpt_search_blocked(self):
        ua_results = [
            {"ua": "OAI-SearchBot", "status": 200, "challenge": False},
            {"ua": "GPTBot", "status": 403, "challenge": True},
            {"ua": "browser", "status": 200, "challenge": False},
        ]
        engines = crawler_roles.engine_access_status(ua_results, robots_blocked=["GPTBot"])
        self.assertEqual(engines["chatgpt_search"]["search_status"], "allowed")
        self.assertEqual(engines["chatgpt_search"]["training_live"], "blocked")
        decision = crawler_roles.core_penalty_decision(["GPTBot"], ua_results)
        self.assertFalse(decision["apply"])
        self.assertEqual(decision["points"], 0)
        # Wording must not claim ChatGPT search is blocked
        self.assertTrue(crawler_roles.should_not_claim_search_blocked(engines, "chatgpt"))
        lines = " ".join(crawler_roles.engine_status_lines_zh(engines))
        self.assertNotIn("ChatGPT 搜索：被拦截", lines)
        self.assertIn("ChatGPT 搜索：可访问", lines)

    def test_claudebot_denied_searchbot_untested_is_unverified(self):
        ua_results = [
            {"ua": "ClaudeBot", "status": 403, "challenge": True},
            {"ua": "OAI-SearchBot", "status": 200, "challenge": False},
            {"ua": "browser", "status": 200, "challenge": False},
        ]
        engines = crawler_roles.engine_access_status(ua_results, robots_blocked=["ClaudeBot"])
        self.assertEqual(engines["claude_search"]["search_status"], "unverified")
        self.assertEqual(engines["claude_search"]["search_live"], "untested")
        decision = crawler_roles.core_penalty_decision(["ClaudeBot"], ua_results)
        self.assertFalse(decision["apply"])
        lines = " ".join(crawler_roles.engine_status_lines_zh(engines))
        self.assertIn("Claude 搜索：未核实", lines)
        self.assertNotIn("Claude 搜索：被拦截", lines)

    def test_search_bot_blocked_does_penalize(self):
        ua_results = [
            {"ua": "OAI-SearchBot", "status": 403, "challenge": True},
            {"ua": "browser", "status": 200, "challenge": False},
        ]
        decision = crawler_roles.core_penalty_decision([], ua_results)
        self.assertTrue(decision["apply"])
        self.assertEqual(decision["points"], -15)

    def test_google_extended_never_core_and_not_in_probes(self):
        self.assertNotIn("Google-Extended", crawler_roles.AI_AND_SEARCH_PROBES)
        self.assertEqual(crawler_roles.role_of("Google-Extended"), "training")
        self.assertFalse(crawler_roles.is_core_access("Google-Extended"))

    def test_analyze_does_not_penalize_training_only(self):
        with tempfile.TemporaryDirectory() as td:
            write_run(
                td,
                pages=[("https://acme-tools.com/", HOME), ("https://acme-tools.com/about", ABOUT)],
                robots="User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n",
                crawler={
                    "url": "https://acme-tools.com/",
                    "ua_results": [
                        {"ua": "OAI-SearchBot", "status": 200, "challenge": False, "size": 1000},
                        {"ua": "GPTBot", "status": 403, "challenge": True, "size": 200},
                        {"ua": "browser", "status": 200, "challenge": False, "size": 1000},
                    ],
                    "ai_blocked": [],
                    "waf_challenge": False,
                },
            )
            report = analyze.analyze(td)
            self.assertEqual(report["penalty"], 0)
            engines = (report.get("crawler_engines") or {})
            self.assertEqual((engines.get("chatgpt_search") or {}).get("search_status"), "allowed")
            titles = [f.get("title") for f in report["findings"]]
            problems = " ".join((f.get("title") or "") + (f.get("problem") or "") for f in report["findings"] if f.get("scored") is not False)
            self.assertTrue(any("训练爬虫" in (t or "") for t in titles))
            self.assertNotIn("ChatGPT 搜索：被拦截", problems)
            self.assertFalse(any(
                f.get("id") in ("ACC-SEARCH-BLOCKED", "ACC-ROBOTS-SEARCH") for f in report["findings"]
            ))


class UnsampledTests(unittest.TestCase):
    def test_discovered_but_unfetched_product_is_unevaluated(self):
        pages = [
            {"url": "https://acme-tools.com/", "role": "home", "page_type": "home"},
            {"url": "https://acme-tools.com/about", "role": "trust", "page_type": "about"},
        ]
        sitemap = [
            "https://acme-tools.com/",
            "https://acme-tools.com/about",
            "https://acme-tools.com/products/saw-x1",
            "https://acme-tools.com/products/saw-x2",
        ]
        cov = page_coverage.coverage_report(pages, sitemap_urls=sitemap)
        self.assertIn("product_detail", cov["unevaluated_types"])
        self.assertTrue(page_coverage.should_suppress_missing_finding(
            cov, "The site is missing a spec table on product pages"
        ))
        self.assertEqual(page_coverage.label_zh("product_detail", cov), "未评估")

    def test_analyze_emits_unevaluated_not_missing_spec(self):
        with tempfile.TemporaryDirectory() as td:
            write_run(
                td,
                pages=[("https://acme-tools.com/", HOME), ("https://acme-tools.com/about", ABOUT)],
                sitemap_urls=[
                    "https://acme-tools.com/",
                    "https://acme-tools.com/about",
                    "https://acme-tools.com/products/saw-x1",
                ],
            )
            report = analyze.analyze(td)
            types = (report.get("coverage") or {}).get("unevaluated_types") or []
            self.assertTrue("product_detail" in types or "product" in types)
            blob = json.dumps(report, ensure_ascii=False)
            # Must not confidently claim missing specs for unfetched product pages
            self.assertNotRegex(blob, r"缺少规格表")
            self.assertTrue(any("未评估" in (f.get("title") or "") + (f.get("problem") or "")
                                for f in report["findings"]))


class SchemaEntityTests(unittest.TestCase):
    def test_body_clear_no_schema_entity_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            write_run(
                td,
                pages=[("https://acme-tools.com/", HOME), ("https://acme-tools.com/about", ABOUT)],
            )
            report = analyze.analyze(td)
            entity = report["category_scores"]["entity"]["score"]
            kg = report["category_scores"]["kg"]["score"]
            self.assertGreater(entity, 0)
            self.assertGreaterEqual(entity, 8)  # no brand/email conflict → near full
            self.assertGreater(kg, 0, "KG should use body/profile facts, not require JSON-LD")
            schema = report["category_scores"]["schema"]["score"]
            self.assertLess(schema, entity)  # missing schema hurts schema dim, not entity
            self.assertTrue(any(f.get("id") == "SCH-ABSENT-BODY-CLEAR" for f in report["findings"]))
            self.assertFalse(any("无法把站点归到真实实体" in (f.get("title") or "") for f in report["findings"]))

    def test_schema_conflict_is_not_high_completeness(self):
        html = HOME.replace("</head>", '''<script type="application/ld+json">
        {"@type":"Organization","name":"Acme Tools","foundingDate":"2010",
         "url":"https://acme-tools.com/","sameAs":["https://www.linkedin.com/company/acme-tools"]}
        </script></head>''')
        about = ABOUT
        with tempfile.TemporaryDirectory() as td:
            write_run(td, pages=[("https://acme-tools.com/", html), ("https://acme-tools.com/about", about)])
            report = analyze.analyze(td)
            cons = None
            # engine may stash consistency only in findings
            self.assertTrue(any(f.get("id") == "SCH-BODY-CONFLICT" or "不一致" in (f.get("title") or "")
                                for f in report["findings"]))
            # Conflicting schema should not sit at the schema ceiling
            self.assertLess(report["category_scores"]["schema"]["score"], 12)


class LlmsTests(unittest.TestCase):
    def test_llms_not_in_core_score(self):
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            write_run(td1, pages=[("https://acme-tools.com/", HOME), ("https://acme-tools.com/about", ABOUT)])
            write_run(
                td2,
                pages=[("https://acme-tools.com/", HOME), ("https://acme-tools.com/about", ABOUT)],
                llms=("# Acme Tools\n\n- https://acme-tools.com/about\n- Documentation: https://acme-tools.com/docs\n" * 3,
                      {"status": 200, "content_type": "text/plain"}),
            )
            a = analyze.analyze(td1)
            b = analyze.analyze(td2)
            self.assertEqual(a["penalty"], b["penalty"])
            self.assertEqual(a["bonus"], b["bonus"])
            self.assertEqual(a["overall_score"], b["overall_score"])
            self.assertTrue((b.get("llms") or {}).get("present"))
            self.assertFalse((b.get("llms") or {}).get("in_core_score", True))
            self.assertTrue(any(f.get("id") == "ACC-07-LLMS" and f.get("scored") is False
                                for f in b["findings"]))

    def test_binary_utf16_not_false_missing(self):
        body = "# Site\n\n- https://acme-tools.com/\nDocumentation: yes\n".encode("utf-16")
        info = llms_detect.inspect_llms(body, status=200, content_type="application/octet-stream")
        self.assertTrue(info["present"])
        self.assertFalse(info["soft_404"])

    def test_html_soft404_not_present(self):
        info = llms_detect.inspect_llms(
            "<!doctype html><html><body>404 page not found</body></html>",
            status=200, content_type="text/html",
        )
        self.assertFalse(info["present"])
        self.assertTrue(info["disguised_404"] or info["soft_404"])


class DuplicateTiersTests(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(entity_signals.cln08_tier(0.91), ("fail", True))
        self.assertEqual(entity_signals.cln08_tier(0.80), ("advisory", False))
        self.assertEqual(entity_signals.cln08_tier(0.60), ("pass", False))
        self.assertEqual(entity_signals.cln08_tier(0.49), ("pass", False))

    def test_near_copies_are_scored(self):
        text = ("unique paragraph about industrial saws and safety " * 80)
        pages = [
            {"url": "https://acme-tools.com/a", "role": "content", "content": text},
            {"url": "https://acme-tools.com/b", "role": "content", "content": text},
        ]
        sim = entity_signals.pairwise_similarity(pages)
        self.assertGreaterEqual(sim["best"], 0.9)
        self.assertEqual(sim["verdict"], "fail")
        self.assertTrue(sim["scored"])


class NumericConflictTests(unittest.TestCase):
    def test_news_acreage_with_time_range_not_auto_error(self):
        pages = [
            {
                "url": "https://acme-tools.com/about",
                "role": "trust",
                "page_type": "about",
                "content": "公司占地面积800亩，位于南部园区。",
            },
            {
                "url": "https://acme-tools.com/news/2023-expansion",
                "role": "content",
                "page_type": "news",
                "content": "2023年园区面积达500亩，当年年底完成一期建设。",
            },
        ]
        result = entity_signals.analyze_numeric_conflicts(pages, default_entity="南兴")
        self.assertEqual(result["ent10_conflicts"], [])
        # May appear in needs_review, but must not be a scored current-fact error
        self.assertTrue(
            not result["ent10_conflicts"]
            or all(r.get("verification") != "comparable_current_facts" for r in result["ent10_conflicts"])
        )

    def test_same_entity_undated_conflict_is_flagged(self):
        pages = [
            {"url": "https://acme-tools.com/about", "role": "trust", "page_type": "about",
             "content": "南兴集团成立于1994年，是木工机械企业。"},
            {"url": "https://acme-tools.com/company", "role": "trust", "page_type": "about",
             "content": "南兴集团成立于2001年，总部位于东莞。"},
        ]
        result = entity_signals.analyze_numeric_conflicts(pages, default_entity="南兴集团")
        self.assertTrue(result["ent10_conflicts"] or result["ent11_conflicts"] or result["needs_review"])


class CurrencyTests(unittest.TestCase):
    def test_bare_amount_detected_unit_not(self):
        bare = citability.find_bare_currency("售价：12800，立即订购")
        self.assertTrue(bare)
        ok = citability.find_bare_currency("售价：12800元，立即订购")
        self.assertFalse(ok)
        ok2 = citability.find_bare_currency("价格 USD 12800")
        self.assertFalse(ok2)


class FormulaTests(unittest.TestCase):
    def test_overall_matches_clamp_formula(self):
        with tempfile.TemporaryDirectory() as td:
            write_run(td, pages=[("https://acme-tools.com/", HOME), ("https://acme-tools.com/about", ABOUT)])
            report = analyze.analyze(td)
            base = report["base_score"]
            penalty = report["penalty"]
            bonus = report["bonus"]
            expected = int(max(0, min(100, base - penalty + bonus)))
            self.assertEqual(report["overall_score"], expected)
            formula = report.get("score_formula") or {}
            self.assertIn("clamp(0, 100, int(base_score - penalty + bonus))", formula.get("expression", ""))
            # No leftover "no adjustments" when bonus/penalty applied: if both 0, that's fine
            self.assertEqual(report["score_adjustments"]["base_score"], base)
            self.assertEqual(report["score_adjustments"]["penalty"], penalty)
            self.assertEqual(report["score_adjustments"]["bonus"], bonus)
            # Dimension sum (after ceiling on base, base may be clamped)
            dim_sum = sum(d["score"] for d in report["dimensions"])
            if not report.get("ceiling"):
                self.assertAlmostEqual(dim_sum, base, places=1)

    def test_itemlist_bonus_capped_and_llms_not_added(self):
        html = HOME.replace("</head>", '''<script type="application/ld+json">
        {"@type":"ItemList","name":"Products","itemListElement":[]}
        </script></head>''')
        with tempfile.TemporaryDirectory() as td:
            write_run(
                td,
                pages=[("https://acme-tools.com/", html), ("https://acme-tools.com/about", ABOUT)],
                llms=("# x\n" + "- https://acme-tools.com/\n" * 20, {"status": 200, "content_type": "text/plain"}),
            )
            report = analyze.analyze(td)
            reasons = [a.get("reason") for a in report.get("adjustments") or []]
            self.assertTrue(any("ItemList" in (r or "") for r in reasons))
            self.assertFalse(any("llms" in (r or "").lower() for r in reasons))


if __name__ == "__main__":
    unittest.main()


class ChallengeDetectionTests(unittest.TestCase):
    def test_cms_captcha_prefix_is_not_waf(self):
        html = "<!doctype html><html><head><title>南兴装备股份有限公司</title></head>"
        html += "<body><script>page._captcha_domain_prefix=\"captcha.c\";</script>"
        html += "<p>南兴装备股份有限公司成立于1990年代。</p>" + ("正文 " * 2000) + "</body></html>"
        self.assertFalse(runmod.is_challenge_page(200, html, len(html)))

    def test_real_challenge_page_is_flagged(self):
        html = "<html><head><title>Just a moment...</title></head><body>Checking your browser</body></html>"
        self.assertTrue(runmod.is_challenge_page(200, html, len(html)))
        self.assertTrue(runmod.is_challenge_page(403, "<html>forbidden</html>", 20))


class ClassificationAndSamplingTests(unittest.TestCase):
    def test_escaped_external_and_pdf_are_not_sampleable(self):
        self.assertTrue(page_coverage.is_escaped_external_url(
            "https://www.nanxing.com/https/irm-cninfo-com-cn/ircs/x"))
        self.assertTrue(page_coverage.is_escaped_external_url(
            "https://www.nanxing.com/https-ir-p5w-net-c-002757-shtml.html"))
        self.assertTrue(page_coverage.is_non_html_asset(
            "https://www.nanxingmac.com/images/Nanxing_catalog.pdf"))
        self.assertTrue(page_coverage.is_sampleable_url("https://www.nanxing.com/products.html"))
        self.assertFalse(page_coverage.is_sampleable_url(
            "https://www.nanxing.com/http/www-szse-cn/certificate/x"))

    def test_industry_news_is_news_not_solution(self):
        self.assertEqual(
            page_coverage.classify_url("https://www.nanxing.com/foo.html", "行业新闻 - 南兴装备"),
            "news",
        )
        self.assertEqual(
            page_coverage.classify_url("https://www.nanxing.com/jiejuefangan.html", "橱柜卫浴解决方案"),
            "solution",
        )

    def test_faq_and_chanpin_types(self):
        self.assertEqual(page_coverage.classify_url("https://www.nanxing.com/faqlist.html"), "faq")
        self.assertEqual(page_coverage.classify_url("https://www.nanxing.com/products.html"), "product")
        self.assertEqual(page_coverage.classify_url("https://www.nanxing.com/chanpinzhongxinzongliebiao.html"), "product")


class RobotsAndEntityNameTests(unittest.TestCase):
    def test_applebot_extended_is_not_applebot(self):
        robots = """
User-agent: Applebot-Extended
Disallow: /

User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
"""
        self.assertTrue(analyze._robots_section_blocks_all(robots, "Applebot-Extended"))
        self.assertIsNone(analyze._robots_section_blocks_all(robots, "Applebot"))
        self.assertIsNone(analyze._robots_section_blocks_all(robots, "Googlebot"))
        self.assertFalse(analyze._robots_section_blocks_all(robots, "*") or False)
        blocked = []
        wildcard_all = analyze._robots_section_blocks_all(robots, r"\*")
        for ua in analyze.AI_CRAWLERS:
            section_all = analyze._robots_section_blocks_all(robots, ua)
            if section_all is True or (section_all is None and wildcard_all is True):
                blocked.append(ua)
        self.assertIn("Applebot-Extended", blocked)
        self.assertIn("GPTBot", blocked)
        self.assertNotIn("Applebot", blocked)
        decision = __import__("crawler_roles").core_penalty_decision(blocked, [
            {"ua": "OAI-SearchBot", "status": 200, "challenge": False},
            {"ua": "GPTBot", "status": 403, "challenge": True},
        ], waf_challenge=False)
        self.assertFalse(decision.get("apply"), decision)

    def test_acquisition_history_is_not_legal_name_conflict(self):
        pages = [
            {"title": "About-Nanxing Machinery | Woodworking", "h1": [],
             "content": "Copyright Nanxing Machinery Co., Ltd. All Rights Reserved. "
                        "Nanxing Machinery successfully acquired Guangdong Weiyi Network Technology Company in April 2018, "
                        "and Weiyi Network became a wholly-owned subsidiary of Nanxing. "
                        "In February 2019 Weiyi Network completed the acquisition of 47.00% of the shares of Guangdong Zhixiang Technology Co., Ltd."},
        ]
        names = analyze.collect_company_names(pages)
        self.assertTrue(any("Nanxing Machinery" in n for n in names), names)
        self.assertFalse(any("Weiyi" in n or "Zhixiang" in n for n in names), names)


    def test_the_company_is_not_a_legal_name_conflict(self):
        pages = [
            {"title": "Nanxing Machinery Co., Ltd.", "h1": [], "url": "https://www.nanxingmac.com/about.html",
             "schemas": [], "ogp": {}, "html": "", "links_external": set(),
             "content": "Copyright Nanxing Machinery Co., Ltd. All Rights Reserved. The Company was founded in 1996. Nanxing Company ships worldwide."},
        ]
        names = analyze.collect_company_names(pages)
        ent = analyze.detect_ent(pages, "nanxingmac.com")
        self.assertFalse(ent.get("company_conflict"), {"names": names, "ent": ent})


class ClaimYearTests(unittest.TestCase):
    def test_calendar_years_are_not_unverified_claims(self):
        import geo_signals_v13 as v13
        text = "南兴装备成立于1996年，2015年扩建工厂，计划2026年发布新机型。公司拥有30年行业经验，已申请200+项专利。"
        hits = v13.detect_unverified_claims(text, [])
        claims = " ".join(h["claim"] for h in hits)
        self.assertNotIn("1996年", claims, hits)
        self.assertNotIn("2015年", claims, hits)
        self.assertNotIn("2026年", claims, hits)
        self.assertNotIn("996年", claims, hits)
        self.assertNotIn("015年", claims, hits)
        self.assertTrue(any("30年" in h["claim"] or "200" in h["claim"] for h in hits), hits)

    def test_first_quarter_is_not_a_superlative(self):
        import geo_signals_v13 as v13
        text = "2026年第一季度报告 2026 04-25 2026年第一次临时股东会决议公告 2026 07-09"
        hits = v13.detect_unverified_claims(text, [])
        self.assertFalse(hits, hits)

    def test_search_box_location_href_is_not_soft_redirect(self):
        import geo_signals_v13 as v13
        search = "function go(){ location.href = \"search.html?key=\" + document.getElementById(\"footSearch\").value; }"
        self.assertFalse(v13.detect_soft_redirect(search).get("detected"))
        splash = "<html><head><meta http-equiv=\"refresh\" content=\"0; url=/home\"></head></html>"
        self.assertTrue(v13.detect_soft_redirect(splash).get("detected"))
