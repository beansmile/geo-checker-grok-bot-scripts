#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Security hardening: registrable domains, fetch policy, run paths, HTML escaping."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import html_safe  # noqa: E402
import net_policy  # noqa: E402
import public_suffix  # noqa: E402
import run_paths  # noqa: E402
import content_eval  # noqa: E402
import run as runmod  # noqa: E402


class RegistrableDomainTests(unittest.TestCase):
    def test_ordinary_example_com(self):
        self.assertEqual(public_suffix.registrable_domain("https://www.example.com/path"), "example.com")
        self.assertEqual(public_suffix.registrable_domain("example.com"), "example.com")
        self.assertEqual(public_suffix.registrable_domain("shop.example.com"), "example.com")

    def test_com_au(self):
        self.assertEqual(public_suffix.registrable_domain("https://btphysio.com.au/"), "btphysio.com.au")
        self.assertEqual(public_suffix.registrable_domain("https://www.btphysio.com.au/about"), "btphysio.com.au")
        self.assertNotEqual(public_suffix.registrable_domain("https://btphysio.com.au/"), "com.au")
        self.assertEqual(public_suffix.registrable_domain("https://otherclinic.com.au/"), "otherclinic.com.au")
        self.assertNotEqual(
            public_suffix.registrable_domain("https://btphysio.com.au/"),
            public_suffix.registrable_domain("https://otherclinic.com.au/"),
        )

    def test_com_sg(self):
        self.assertEqual(public_suffix.registrable_domain("https://raisewell.com.sg/"), "raisewell.com.sg")
        self.assertEqual(public_suffix.registrable_domain("shop.raisewell.com.sg"), "raisewell.com.sg")
        self.assertNotEqual(public_suffix.registrable_domain("https://raisewell.com.sg/"), "com.sg")

    def test_co_uk(self):
        self.assertEqual(public_suffix.registrable_domain("https://www.bbc.co.uk/news"), "bbc.co.uk")
        self.assertEqual(public_suffix.registrable_domain("https://example.co.uk/"), "example.co.uk")
        self.assertNotEqual(public_suffix.registrable_domain("https://example.co.uk/"), "co.uk")

    def test_shared_helpers_agree(self):
        for url in (
            "https://btphysio.com.au/",
            "https://raisewell.com.sg/",
            "https://www.bbc.co.uk/news",
            "https://www.example.com/",
        ):
            self.assertEqual(runmod.registrable_domain(url), public_suffix.registrable_domain(url))
            self.assertEqual(content_eval.registrable_domain(url), public_suffix.registrable_domain(url))


class FetchPolicyTests(unittest.TestCase):
    def test_http_https_only(self):
        self.assertFalse(net_policy.is_public_http_url("file:///etc/passwd"))
        self.assertFalse(net_policy.is_public_http_url("ftp://example.com/a"))
        self.assertFalse(net_policy.is_public_http_url("javascript:alert(1)"))
        self.assertTrue(net_policy.is_public_http_url("https://example.com/a", resolve_dns=False))
        self.assertTrue(net_policy.is_public_http_url("http://example.com/a", resolve_dns=False))

    def test_rejects_loopback_private_link_local_metadata(self):
        blocked = [
            "http://127.0.0.1/",
            "http://127.0.0.1:8080/secret",
            "http://localhost/",
            "http://[::1]/",
            "http://192.168.1.10/",
            "http://10.0.0.5/",
            "http://172.16.0.2/",
            "http://169.254.169.254/latest/meta-data",
            "http://metadata.google.internal/",
            "http://192.168.0.1/",
            "http://0.0.0.0/",
        ]
        for url in blocked:
            with self.subTest(url=url):
                self.assertFalse(net_policy.is_public_http_url(url, resolve_dns=False))
                with self.assertRaises(net_policy.FetchBlocked):
                    net_policy.check_url(url, resolve_dns=False)

    def test_same_site_and_off_site(self):
        target = "https://www.example.com/"
        self.assertTrue(net_policy.is_same_site("https://example.com/about", target))
        self.assertTrue(net_policy.is_same_site("https://www.example.com/a", target))
        self.assertTrue(net_policy.is_same_site("https://shop.example.com/a", target))
        self.assertFalse(net_policy.is_same_site("https://evil.example.org/a", target))
        self.assertFalse(net_policy.is_allowed_page_url("https://evil.example.org/a", target, resolve_dns=False))
        self.assertFalse(net_policy.is_allowed_page_url("http://127.0.0.1/", target, resolve_dns=False))

    def test_multipart_tld_same_site_does_not_span_siblings(self):
        self.assertFalse(
            net_policy.is_same_site("https://otherclinic.com.au/", "https://btphysio.com.au/")
        )
        self.assertTrue(
            net_policy.is_same_site("https://www.btphysio.com.au/about", "https://btphysio.com.au/")
        )

    def test_strip_userinfo(self):
        self.assertEqual(
            net_policy.strip_userinfo("https://user:s3cret@example.com:8443/a?b=1#f"),
            "https://example.com:8443/a?b=1#f",
        )
        self.assertEqual(
            net_policy.canonicalize_url("https://alice:pw@www.example.com/x"),
            "https://www.example.com/x",
        )

    def test_max_pages_cap(self):
        self.assertEqual(net_policy.clamp_max_pages(16), 16)
        self.assertEqual(net_policy.clamp_max_pages(10000), net_policy.MAX_PAGES_CAP)
        self.assertEqual(net_policy.clamp_max_pages(0), 1)
        self.assertEqual(net_policy.MAX_PAGES_CAP, 100)

    def test_robots_disallow(self):
        body = b"""
User-agent: *
Disallow: /private
Allow: /private/ok
Disallow: /tmp

User-agent: GEO-Checker
Disallow: /hidden
"""
        star = "Mozilla/5.0"
        self.assertTrue(net_policy.robots_allowed("https://example.com/", body, star))
        self.assertFalse(net_policy.robots_allowed("https://example.com/private/secret", body, star))
        self.assertTrue(net_policy.robots_allowed("https://example.com/private/ok", body, star))
        self.assertFalse(net_policy.robots_allowed("https://example.com/tmp/a", body, star))
        # A named GEO-Checker group is more specific than * and does not inherit * rules
        bot = "GEO-Checker/1.0"
        self.assertFalse(net_policy.robots_allowed("https://example.com/hidden", body, bot))
        self.assertTrue(net_policy.robots_allowed("https://example.com/private/secret", body, bot))
        # Sampling uses desktop Chrome, so it follows the * group
        self.assertTrue(net_policy.robots_allowed("https://example.com/hidden", body, net_policy.FIRST_PARTY_UA))
        self.assertFalse(net_policy.robots_allowed("https://example.com/private/secret", body, net_policy.FIRST_PARTY_UA))
        self.assertIn("Chrome/141.0.0.0", net_policy.FIRST_PARTY_UA)
        self.assertNotIn("GEO-Checker", net_policy.FIRST_PARTY_UA)


class RunPathTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.pop("GEO_EVAL_RUNS_ROOT", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.run = self.root / "runs" / "example.com" / "2026-01-01_run01"
        self.run.mkdir(parents=True)
        (self.run / "site.json").write_text(
            json.dumps({
                "url": "https://www.example.com/",
                "domain": "www.example.com",
                "registrable_domain": "example.com",
            }),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()
        if self._old is not None:
            os.environ["GEO_EVAL_RUNS_ROOT"] = self._old
        else:
            os.environ.pop("GEO_EVAL_RUNS_ROOT", None)

    def test_accepts_normal_relative_and_absolute(self):
        a = run_paths.resolve_run_dir("runs/example.com/2026-01-01_run01", root=str(self.root))
        b = run_paths.resolve_run_dir("example.com/2026-01-01_run01", root=str(self.root))
        c = run_paths.resolve_run_dir(str(self.run), root=str(self.root))
        self.assertEqual(Path(a), Path(c))
        self.assertEqual(Path(b), Path(c))

    def test_rejects_dotdot(self):
        with self.assertRaises(SystemExit):
            run_paths.resolve_run_dir("runs/example.com/../example.com/2026-01-01_run01", root=str(self.root))

    def test_rejects_path_outside_runs(self):
        outside = self.root / "secret"
        outside.mkdir()
        with self.assertRaises(SystemExit):
            run_paths.resolve_run_dir(str(outside), root=str(self.root))

    def test_rejects_symlink_escape(self):
        target = Path(self.tmp.name) / "escaped"
        target.mkdir()
        link = self.root / "runs" / "example.com" / "escape"
        link.symlink_to(target)
        with self.assertRaises(SystemExit):
            run_paths.resolve_run_dir(str(link), root=str(self.root))

    def test_no_cross_site_copy(self):
        # New layout: each registrable domain has its own folder.
        a = self.root / "runs" / "btphysio.com.au" / "2026-01-01_run01"
        b = self.root / "runs" / "otherclinic.com.au" / "2026-01-02_run01"
        # Legacy (incorrect) shared folder must not be consulted for a new site match.
        legacy = self.root / "runs" / "com.au" / "2026-01-03_run01"
        a.mkdir(parents=True)
        b.mkdir(parents=True)
        legacy.mkdir(parents=True)
        (a / "site.json").write_text(json.dumps({
            "url": "https://btphysio.com.au/",
            "domain": "btphysio.com.au",
            "registrable_domain": "btphysio.com.au",
        }), encoding="utf-8")
        (b / "site.json").write_text(json.dumps({
            "url": "https://otherclinic.com.au/",
            "domain": "otherclinic.com.au",
            "registrable_domain": "otherclinic.com.au",
        }), encoding="utf-8")
        (legacy / "site.json").write_text(json.dumps({
            "url": "https://btphysio.com.au/",
            "domain": "btphysio.com.au",
            "registrable_domain": "com.au",
        }), encoding="utf-8")
        matches = run_paths.find_matching_runs("https://btphysio.com.au/", root=str(self.root))
        self.assertEqual(len(matches), 1, matches)
        self.assertTrue(matches[0].endswith(str(a)) or matches[0].endswith("btphysio.com.au/2026-01-01_run01")
                        or Path(matches[0]) == a)
        other = run_paths.find_matching_runs("https://otherclinic.com.au/", root=str(self.root))
        self.assertEqual(len(other), 1, other)
        self.assertFalse(run_paths.same_site_identity(
            json.loads((b / "site.json").read_text()), "https://btphysio.com.au/",
        ))
        # A site.json sitting only in the legacy com.au folder is not auto-picked
        # for a different host, and new lookups use the registrable-domain folder.
        self.assertFalse(any(Path(m) == legacy for m in matches))


class HtmlSafeTests(unittest.TestCase):
    def test_escapes_script_and_whitelists_strong_br(self):
        out = html_safe.inline_md("<script>alert(1)</script> **ok** <strong>keep</strong><br>done")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("<strong>ok</strong>", out)
        self.assertIn("<strong>keep</strong>", out)
        self.assertIn("<br>", out)

    def test_mustache_does_not_reinterpolate_values(self):
        css = "body{color:red}"
        js = "alert(1)"
        html = html_safe.render_mustache(
            "<style>{{style}}</style><div>{{overall_summary}}</div><script>{{script}}</script>",
            {
                "style": css,
                "script": js,
                "overall_summary": "See {{style}} and {{script}} please",
            },
        )
        self.assertIn(css, html)
        self.assertIn(js, html)
        self.assertNotIn("See body{color:red}", html)
        self.assertIn("&#123;&#123;style&#125;&#125;", html)
        self.assertIn("&#123;&#123;script&#125;&#125;", html)

    def test_href_restricted_and_quote_true(self):
        self.assertEqual(html_safe.safe_href("javascript:alert(1)"), "")
        self.assertEqual(html_safe.safe_href("file:///etc/passwd"), "")
        href = html_safe.safe_href("https://example.com/a?x=1&y=2")
        self.assertIn("https://example.com/a?x=1", href)
        self.assertIn("&amp;", href)
        self.assertNotIn("&y=2", href.replace("&amp;y=2", ""))
        self.assertTrue(html_safe.safe_href("#p3").startswith("#"))
        self.assertIn("&quot;", html_safe.esc('say "hi"', quote=True))

    def test_csp_meta_hashes_script_and_style(self):
        script = "(function(){console.log('x')})();"
        style = "body{margin:0}"
        meta = html_safe.csp_meta(script, style)
        self.assertIn("Content-Security-Policy", meta)
        self.assertIn(html_safe.sha256_csp(script), meta)
        self.assertIn(html_safe.sha256_csp(style), meta)
        self.assertIn("default-src 'none'", meta)
        self.assertNotIn("unsafe-inline", meta)


if __name__ == "__main__":
    unittest.main()
