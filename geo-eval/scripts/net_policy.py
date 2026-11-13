#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch policy for the GEO Checker crawl path.

- Only http/https.
- After redirects, re-validate the final host.
- Reject loopback, private, link-local, reserved, and cloud-metadata addresses.
- Sample / page URLs must stay on the target site (same registrable domain).
- Stored URLs have userinfo stripped.
- Sampling and content fetches use a first-party GEO Checker UA and honor
  robots.txt Disallow. Third-party crawler UAs are reserved for limited,
  read-only homepage reachability probes (see run.py test_crawler_access).
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse, urlunparse

from public_suffix import registrable_domain

# First-party UA for robots, sitemaps, llms.txt, and page sampling/content.
# Third-party identities (Googlebot, OAI-SearchBot, …) stay in crawler_roles
# and are used only for homepage reachability probes.
FIRST_PARTY_UA = (
    "GEO-Checker/1.0 (+https://github.com/beansmile/geo-checker-grok-bot-scripts) "
    "Mozilla/5.0 (compatible; GEO-Checker/1.0)"
)
FIRST_PARTY_HEADERS = {
    "User-Agent": FIRST_PARTY_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Hard ceiling for --max-pages (including required-page backfill).
MAX_PAGES_CAP = 100

# Hostnames that must never be fetched.
_BLOCKED_HOSTS = frozenset({
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata.goog",
    "metadata.internal",
    "instance-data",
    "kubernetes",
    "kubernetes.default",
    "kubernetes.default.svc",
})
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".invalid", ".lan", ".corp")

# Extra networks not always covered by ipaddress "is_private" (CGNAT / some metadata).
_EXTRA_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("100.100.100.200/32"),
)


class FetchBlocked(Exception):
    """Raised when a URL is not allowed by the fetch policy."""


def clamp_max_pages(value, default=24, cap=MAX_PAGES_CAP) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    if n < 1:
        n = 1
    if n > cap:
        n = cap
    return n


def canonicalize_url(url: str, default_scheme: str = "https") -> str:
    """Normalize a user/site URL: add scheme if missing, strip userinfo."""
    raw = (url or "").strip()
    if not raw:
        raise FetchBlocked("empty URL")
    if raw.startswith("//"):
        raw = default_scheme + ":" + raw
    elif not urlparse(raw).scheme:
        raw = default_scheme + "://" + raw
    return strip_userinfo(raw)


def strip_userinfo(url: str) -> str:
    """Return the URL with user:pass@ removed. Path/query/fragment kept."""
    p = urlparse((url or "").strip())
    host = p.hostname or ""
    if not host:
        return url or ""
    if ":" in host:
        netloc = f"[{host}]"
    else:
        netloc = host
    if p.port:
        netloc = f"{netloc}:{p.port}"
    return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))


def _ip_blocked(ip: ipaddress._BaseAddress) -> bool:
    if ip.version == 6 and getattr(ip, "ipv4_mapped", None) is not None:
        ip = ip.ipv4_mapped
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True
    for net in _EXTRA_NETWORKS:
        try:
            if ip in net:
                return True
        except TypeError:
            continue
    return False


def _host_blocked_name(host: str) -> bool:
    h = (host or "").rstrip(".").lower()
    if not h:
        return True
    if h in _BLOCKED_HOSTS:
        return True
    if h.endswith(_BLOCKED_SUFFIXES):
        return True
    # Numeric trailing-dot or weird forms
    if h == "0" or h.startswith("0."):
        # 0.0.0.0 handled as IP; "0" alone is not a public host
        try:
            if _ip_blocked(ipaddress.ip_address(h)):
                return True
        except ValueError:
            if h == "0":
                return True
    return False


def resolve_host_ips(host: str) -> list:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise FetchBlocked(f"DNS failed for {host}: {e}") from e
    ips = []
    for info in infos:
        addr = info[4][0]
        try:
            ips.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    if not ips:
        raise FetchBlocked(f"no addresses for {host}")
    return ips


def check_url(url: str, *, allowed_site: str | None = None, resolve_dns: bool = True) -> str:
    """Validate a URL. Returns the sanitized URL, or raises FetchBlocked."""
    if not url or not str(url).strip():
        raise FetchBlocked("empty URL")
    sanitized = strip_userinfo(url.strip())
    p = urlparse(sanitized)
    scheme = (p.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise FetchBlocked(f"scheme not allowed: {scheme or '(none)'}")
    host = p.hostname or ""
    if not host:
        raise FetchBlocked("URL has no host")
    if _host_blocked_name(host):
        raise FetchBlocked(f"blocked host: {host}")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and _ip_blocked(ip):
        raise FetchBlocked(f"blocked address: {host}")
    if resolve_dns and ip is None:
        for resolved in resolve_host_ips(host):
            if _ip_blocked(resolved):
                raise FetchBlocked(f"blocked resolved address for {host}: {resolved}")
    if allowed_site and not is_same_site(sanitized, allowed_site):
        raise FetchBlocked(f"off-site URL: {host}")
    return sanitized


def is_public_http_url(url: str, *, resolve_dns: bool = False) -> bool:
    try:
        check_url(url, resolve_dns=resolve_dns)
        return True
    except FetchBlocked:
        return False


def is_same_site(url: str, target: str) -> bool:
    """True if url is on the same registrable domain as the target site."""
    try:
        u = strip_userinfo(url)
        t = strip_userinfo(target)
    except Exception:
        return False
    pu, pt = urlparse(u), urlparse(t)
    if (pu.scheme or "").lower() not in ("http", "https"):
        return False
    uh = (pu.hostname or "").lower().rstrip(".")
    th = (pt.hostname or "").lower().rstrip(".")
    if not uh or not th:
        return False
    if uh == th:
        return True
    return registrable_domain(u) == registrable_domain(t) and bool(registrable_domain(t))


def is_allowed_page_url(url: str, target: str, *, resolve_dns: bool = False) -> bool:
    try:
        check_url(url, allowed_site=target, resolve_dns=resolve_dns)
        return True
    except FetchBlocked:
        return False


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_site=None):
        super().__init__()
        self.allowed_site = allowed_site

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl, allowed_site=self.allowed_site, resolve_dns=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _RejectNonHttpHandler(urllib.request.BaseHandler):
    def file_open(self, req):  # noqa: ARG002
        raise FetchBlocked("scheme not allowed: file")

    def ftp_open(self, req):  # noqa: ARG002
        raise FetchBlocked("scheme not allowed: ftp")

    def data_open(self, req):  # noqa: ARG002
        raise FetchBlocked("scheme not allowed: data")


def _opener(allowed_site=None):
    redirect = _SafeRedirectHandler(allowed_site=allowed_site)
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        urllib.request.UnknownHandler(),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
        redirect,
        urllib.request.HTTPSHandler(),
        _RejectNonHttpHandler(),
    ):
        opener.add_handler(handler)
    return opener


def safe_urlopen(url, *, headers=None, timeout=15, allowed_site=None):
    """urlopen with protocol/host checks on the request and every redirect hop."""
    sanitized = check_url(url, allowed_site=allowed_site, resolve_dns=True)
    req = urllib.request.Request(sanitized, headers=headers or FIRST_PARTY_HEADERS)
    resp = _opener(allowed_site=allowed_site).open(req, timeout=timeout)
    final = getattr(resp, "geturl", lambda: sanitized)() or sanitized
    check_url(final, allowed_site=allowed_site, resolve_dns=True)
    return resp


# ---------------------------------------------------------------------------
# robots.txt — honor Disallow for sampling / content fetches
# ---------------------------------------------------------------------------

def parse_robots(body) -> dict:
    """Parse robots.txt into {user_agent_lower: [(allow|disallow, path), ...]}.

    Groups are keyed by the User-agent value (lowercase). The wildcard group
    is '*'. Comments and Crawl-delay / Sitemap are ignored.
    Consecutive User-agent lines share the following rules; a User-agent line
    after rules starts a new group.
    """
    if body is None:
        return {}
    if isinstance(body, (bytes, bytearray)):
        text = body.decode("utf-8", "replace")
    else:
        text = str(body)
    groups: dict[str, list] = {}
    current_agents: list[str] = []
    start_new_group = True
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            ua = value.lower() or "*"
            if start_new_group:
                current_agents = [ua]
                start_new_group = False
            else:
                current_agents.append(ua)
            groups.setdefault(ua, [])
            continue
        if key in ("allow", "disallow"):
            if not current_agents:
                current_agents = ["*"]
                groups.setdefault("*", [])
            for agent in current_agents:
                groups.setdefault(agent, []).append((key, value))
            start_new_group = True
    return groups


def _path_from_url(url: str) -> str:
    p = urlparse(url)
    path = p.path or "/"
    if p.query:
        path = path + "?" + p.query
    return path


def _rule_matches(path: str, prefix: str) -> bool:
    if prefix == "":
        # Disallow: (empty) means allow all, per robots RFC / Google
        return False
    if path.startswith(prefix):
        return True
    # A prefix that is a directory should also match with implicit slash
    return False


def robots_allowed(url: str, robots_body, user_agent: str = FIRST_PARTY_UA) -> bool:
    """True if robots.txt allows fetching this URL for the given UA.

    Uses the most specific User-agent group (longest matching token), falling
    back to '*'. Longest matching Allow/Disallow prefix wins; Allow wins ties.
    Missing or empty robots.txt → allowed. A failed parse → allowed.
    """
    try:
        groups = parse_robots(robots_body)
    except Exception:
        return True
    if not groups:
        return True
    ua = (user_agent or "*").lower()
    # Prefer a group whose name appears as a token in the UA string,
    # choosing the longest group name; else '*'.
    chosen = None
    best_len = -1
    for name in groups:
        if name == "*":
            continue
        if name in ua and len(name) > best_len:
            chosen = name
            best_len = len(name)
    rules = groups.get(chosen) if chosen is not None else None
    if rules is None:
        rules = groups.get("*") or []
    path = _path_from_url(url)
    best = None  # (length, is_allow)
    for kind, prefix in rules:
        if not _rule_matches(path, prefix):
            continue
        length = len(prefix)
        is_allow = kind == "allow"
        if best is None or length > best[0] or (length == best[0] and is_allow and not best[1]):
            best = (length, is_allow)
    if best is None:
        return True
    return bool(best[1])


def join_url(base: str, loc: str) -> str:
    return urljoin(base if base.endswith("/") else base + "/", loc)
