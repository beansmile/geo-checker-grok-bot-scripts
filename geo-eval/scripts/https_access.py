#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ACC-05 HTTPS and redirect scoring.

Penalties (core score_adjustments):
  S1  site is not usable HTTPS          -10
  S2  HTTPS works, but HTTP does not
      redirect to HTTPS                  -3
  S3  official/main URL redirect hops >2 -3

Stacking: S1 is exclusive (no S2/S3 on top). S2 and S3 may both apply
when the site is usable HTTPS. Certificate/hostname mismatch is not itself
an ACC-05 penalty (see TEC-04, warning only); a failed TLS handshake means
HTTPS is not usable, so S1 applies if the official entry is not HTTPS.
Never disable TLS verification to treat a broken certificate as official HTTPS.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlparse, urlunparse

from net_policy import FetchBlocked, check_url, strip_userinfo


EVIDENCE_NAME = "https.json"


class _CountingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_site=None):
        super().__init__()
        self.allowed_site = allowed_site
        self.hops = 0
        self.chain = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl, allowed_site=self.allowed_site, resolve_dns=True)
        self.hops += 1
        self.chain.append({
            "from": req.full_url,
            "status": int(code) if code else None,
            "to": newurl,
        })
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _same_site_url(url, scheme):
    p = urlparse(url)
    return urlunparse((scheme, p.netloc, p.path or "/", p.params, p.query, ""))


def _open(url, *, timeout=15, allowed_site=None, context=None):
    """Follow redirects with hop counting; TLS verification stays on."""
    sanitized = check_url(url, allowed_site=allowed_site, resolve_dns=True)
    handler = _CountingRedirectHandler(allowed_site=allowed_site)
    https_handler = (
        urllib.request.HTTPSHandler(context=context)
        if context is not None
        else urllib.request.HTTPSHandler()
    )
    opener = urllib.request.OpenerDirector()
    for h in (
        urllib.request.ProxyHandler(),
        urllib.request.UnknownHandler(),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
        handler,
        https_handler,
    ):
        opener.add_handler(h)
    req = urllib.request.Request(sanitized, method="GET")
    try:
        resp = opener.open(req, timeout=timeout)
        final = strip_userinfo(getattr(resp, "geturl", lambda: sanitized)() or sanitized)
        status = getattr(resp, "status", None) or resp.getcode()
        try:
            resp.read(64)
        finally:
            resp.close()
        return {
            "ok": True,
            "status": status,
            "final_url": final,
            "hops": handler.hops,
            "chain": handler.chain,
            "error": "",
        }
    except urllib.error.HTTPError as e:
        final = strip_userinfo(getattr(e, "url", None) or url)
        return {
            "ok": 400 <= int(e.code or 0) < 600,
            "status": e.code,
            "final_url": final,
            "hops": handler.hops,
            "chain": handler.chain,
            "error": f"HTTP {e.code}",
        }
    except ssl.SSLError as e:
        return {
            "ok": False,
            "status": 0,
            "final_url": url,
            "hops": handler.hops,
            "chain": handler.chain,
            "error": f"tls: {e}",
            "tls_error": str(e),
        }
    except FetchBlocked as e:
        return {
            "ok": False,
            "status": 0,
            "final_url": url,
            "hops": handler.hops,
            "chain": handler.chain,
            "error": f"blocked: {e}",
        }
    except Exception as e:  # noqa: BLE001
        err = str(e)
        tls = any(k in err.lower() for k in ("certificate", "ssl", "tls", "hostname"))
        return {
            "ok": False,
            "status": 0,
            "final_url": url,
            "hops": handler.hops,
            "chain": handler.chain,
            "error": err[:300],
            **({"tls_error": err[:300]} if tls else {}),
        }


def infer_from_official_url(official_url: str) -> dict:
    """Scheme-only fallback when no probe evidence exists.

    HTTP official entry → S1. HTTPS official entry → no S1; S2/S3 stay
    unknown (not deducted) until a probe is recorded.
    """
    scheme = (urlparse(official_url or "").scheme or "").lower()
    return {
        "official_url": official_url or "",
        "https": scheme == "https",
        "http_redirects_to_https": None,
        "redirect_hops": None,
        "probed": False,
        "https_error": "",
        "source": "official_url_scheme",
    }


def probe_https_access(official_url: str, *, timeout=15, allowed_site=None) -> dict:
    """Live-probe official URL, HTTPS usability, HTTP→HTTPS redirect, and hops."""
    official = strip_userinfo(official_url or "")
    allowed = allowed_site or official
    info = {
        "official_url": official,
        "https": False,
        "http_redirects_to_https": None,
        "redirect_hops": None,
        "probed": True,
        "https_error": "",
        "source": "probe",
        "official_fetch": {},
        "https_fetch": {},
        "http_fetch": {},
    }
    try:
        official_fetch = _open(official, timeout=timeout, allowed_site=allowed)
    except FetchBlocked as e:
        official_fetch = {"ok": False, "status": 0, "final_url": official, "hops": 0, "chain": [], "error": f"blocked: {e}"}
    info["official_fetch"] = official_fetch

    official_scheme = (urlparse(official).scheme or "").lower()
    final_url = official_fetch.get("final_url") or official
    final_scheme = (urlparse(final_url).scheme or "").lower()

    https_url = _same_site_url(official if official_scheme in ("http", "https") else final_url, "https")
    http_url = _same_site_url(official if official_scheme in ("http", "https") else final_url, "http")

    if official_scheme == "https" or final_scheme == "https":
        if official_scheme == "https" and official_fetch.get("tls_error"):
            info["https"] = False
            info["https_error"] = official_fetch.get("tls_error") or official_fetch.get("error") or ""
            info["https_fetch"] = official_fetch
        elif official_scheme == "https" or (final_scheme == "https" and official_fetch.get("ok")):
            info["https"] = True
            info["redirect_hops"] = int(official_fetch.get("hops") or 0)
            info["https_fetch"] = official_fetch if official_scheme == "https" else {"via": "http_redirect", **official_fetch}
        else:
            # Official stayed HTTP or HTTPS hop failed; try HTTPS directly.
            https_fetch = _open(https_url, timeout=timeout, allowed_site=allowed)
            info["https_fetch"] = https_fetch
            if https_fetch.get("ok") and (urlparse(https_fetch.get("final_url") or "").scheme or "").lower() == "https" and not https_fetch.get("tls_error"):
                info["https"] = True
                info["redirect_hops"] = int(https_fetch.get("hops") or 0)
            else:
                info["https"] = False
                info["https_error"] = https_fetch.get("tls_error") or https_fetch.get("error") or ""
    else:
        https_fetch = _open(https_url, timeout=timeout, allowed_site=allowed)
        info["https_fetch"] = https_fetch
        if https_fetch.get("ok") and (urlparse(https_fetch.get("final_url") or "").scheme or "").lower() == "https" and not https_fetch.get("tls_error"):
            info["https"] = True
            info["redirect_hops"] = int(https_fetch.get("hops") or 0)
        else:
            info["https"] = False
            info["https_error"] = https_fetch.get("tls_error") or https_fetch.get("error") or ""

    # HTTP → HTTPS redirect (only meaningful once HTTPS is usable, but always record).
    if (urlparse(http_url).scheme or "").lower() == "http":
        http_fetch = _open(http_url, timeout=timeout, allowed_site=allowed)
        info["http_fetch"] = http_fetch
        final_http = http_fetch.get("final_url") or ""
        info["http_redirects_to_https"] = (
            bool(http_fetch.get("ok") or http_fetch.get("hops"))
            and (urlparse(final_http).scheme or "").lower() == "https"
        )
        if info["https"] and official_scheme == "http" and info["redirect_hops"] is None:
            info["redirect_hops"] = int(http_fetch.get("hops") or 0)

    return info


def load_from_run(run_dir: str, official_url: str = "") -> dict:
    path = os.path.join(run_dir, "evidence", EVIDENCE_NAME)
    if os.path.isfile(path):
        try:
            data = json.loads(open(path, encoding="utf-8").read())
            if isinstance(data, dict):
                data.setdefault("official_url", official_url)
                data.setdefault("source", "evidence")
                return data
        except (OSError, json.JSONDecodeError):
            pass
    site_path = os.path.join(run_dir, "site.json")
    if os.path.isfile(site_path):
        try:
            site = json.loads(open(site_path, encoding="utf-8").read())
            tech = site.get("tech") if isinstance(site, dict) else None
            if isinstance(tech, dict) and ("https" in tech or "http_redirects_to_https" in tech):
                out = {
                    "official_url": official_url or (site.get("url") if isinstance(site, dict) else "") or "",
                    "https": bool(tech.get("https")),
                    "http_redirects_to_https": tech.get("http_redirects_to_https"),
                    "redirect_hops": tech.get("redirect_hops"),
                    "probed": True,
                    "https_error": tech.get("https_error") or tech.get("apex_tls_error") or "",
                    "source": "site.tech",
                }
                return out
            if not official_url and isinstance(site, dict):
                official_url = site.get("url") or ""
        except (OSError, json.JSONDecodeError):
            pass
    return infer_from_official_url(official_url)


def save_to_run(run_dir: str, info: dict) -> str:
    ev = os.path.join(run_dir, "evidence")
    os.makedirs(ev, exist_ok=True)
    path = os.path.join(ev, EVIDENCE_NAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return path


def evaluate_acc05(info: dict | None) -> dict:
    """Return ACC-05 penalties, reasons, and findings. No network I/O."""
    info = info or {}
    https = bool(info.get("https"))
    redirects = info.get("http_redirects_to_https")
    hops = info.get("redirect_hops")
    official = info.get("official_url") or ""
    error = info.get("https_error") or ""

    adjustments = []
    findings = []
    penalty = 0

    if not https:
        penalty += 10
        adjustments.append({
            "type": "penalty",
            "points": -10,
            "rule_id": "ACC-05",
            "reason": "网站不是 HTTPS",
        })
        extra = f"（{error}）" if error else ""
        findings.append({
            "severity": "严重",
            "id": "ACC-05",
            "scored": True,
            "root_cause_id": "https_access",
            "evidence_kind": "observed",
            "title": "网站不是 HTTPS",
            "problem": f"评分入口 {official or '（未记录）'} 不是可用的 HTTPS{extra}。"
                       "没有用证书校验来把失败的 HTTPS 当成官网入口。",
            "impact": "浏览器和抓取器无法在加密连接上稳定打开官网，也缺少 HTTP 到 HTTPS 的可靠跳转。",
            "solution": "为官网域名配置有效 HTTPS 证书，并把 HTTP 请求 301 到 HTTPS。",
            "evidence": [{"url": official, "quote": error or f"official scheme is {(urlparse(official).scheme or 'unknown')}"}],
        })
        return {"penalty": penalty, "adjustments": adjustments, "findings": findings, "https": False}

    if redirects is False:
        penalty += 3
        adjustments.append({
            "type": "penalty",
            "points": -3,
            "rule_id": "ACC-05",
            "reason": "已是 HTTPS，但 HTTP 没有跳转到 HTTPS",
        })
        findings.append({
            "severity": "高",
            "id": "ACC-05-REDIRECT",
            "scored": True,
            "root_cause_id": "https_access",
            "evidence_kind": "observed",
            "title": "HTTP 没有跳转到 HTTPS",
            "problem": "网站已经可以走 HTTPS，但从 HTTP 打开时没有跳转到 HTTPS。",
            "impact": "用户或抓取器若从 HTTP 进入，会停在未加密地址上。",
            "solution": "把 HTTP 请求 301 到对应的 HTTPS 地址。",
            "evidence": [{"url": official, "quote": "http_redirects_to_https=false"}],
        })

    if hops is not None:
        try:
            hop_n = int(hops)
        except (TypeError, ValueError):
            hop_n = 0
        if hop_n > 2:
            penalty += 3
            adjustments.append({
                "type": "penalty",
                "points": -3,
                "rule_id": "ACC-05",
                "reason": f"主 URL 跳转超过 2 次（{hop_n} 次）",
            })
            findings.append({
                "severity": "中",
                "id": "ACC-05-HOPS",
                "scored": True,
                "root_cause_id": "https_access",
                "evidence_kind": "observed",
                "title": "主地址跳转次数过多",
                "problem": f"打开主 URL 时跳转了 {hop_n} 次，超过 2 次。",
                "impact": "过长的跳转链会增加抓取失败和入口不稳定的风险。",
                "solution": "把主地址的跳转缩短到不超过 2 次，并统一到一个 HTTPS 规范地址。",
                "evidence": [{"url": official, "quote": f"redirect_hops={hop_n}"}],
            })

    return {"penalty": penalty, "adjustments": adjustments, "findings": findings, "https": True}


__all__ = [
    "EVIDENCE_NAME",
    "evaluate_acc05",
    "infer_from_official_url",
    "load_from_run",
    "probe_https_access",
    "save_to_run",
]
