#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registrable-domain helper (eTLD+1) using a vendored multi-part public-suffix table.

Ordinary two-label hosts such as example.com stay example.com. Multi-part ICANN
suffixes (com.au, co.uk, com.sg, …) take one extra label so btphysio.com.au is
not collapsed into com.au.

This is a compact snapshot of common multi-part suffixes, not a live Public
Suffix List download. Unknown suffixes fall back to “last two labels”.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

# Multi-part ICANN / commonly used suffixes. Single-label suffixes (com, org,
# cn, io, …) are implied by the last-two-labels fallback and omitted here.
MULTIPART_SUFFIXES = frozenset({
    # Australia / NZ
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "asn.au", "id.au",
    "csiro.au", "conf.au", "info.au",
    "co.nz", "net.nz", "org.nz", "govt.nz", "ac.nz", "school.nz", "cri.nz",
    "geek.nz", "gen.nz", "kiwi.nz", "maori.nz", "mil.nz", "iwi.nz",
    # UK / IE
    "co.uk", "org.uk", "me.uk", "ac.uk", "gov.uk", "ltd.uk", "plc.uk",
    "net.uk", "sch.uk", "nhs.uk", "police.uk", "mod.uk", "nic.uk",
    "com.ie", "net.ie", "org.ie", "gov.ie", "edu.ie",
    # Singapore / MY / ID / PH / TH / VN / HK / TW / MO
    "com.sg", "net.sg", "org.sg", "edu.sg", "gov.sg", "per.sg",
    "com.my", "net.my", "org.my", "gov.my", "edu.my", "mil.my", "name.my",
    "co.id", "or.id", "go.id", "ac.id", "sch.id", "web.id", "my.id", "biz.id",
    "desa.id", "ponpes.id",
    "com.ph", "net.ph", "org.ph", "gov.ph", "edu.ph",
    "co.th", "ac.th", "go.th", "or.th", "net.th", "in.th", "mi.th",
    "com.vn", "net.vn", "org.vn", "gov.vn", "edu.vn", "ac.vn", "health.vn",
    "biz.vn", "info.vn", "name.vn", "pro.vn", "int.vn",
    "com.hk", "org.hk", "edu.hk", "gov.hk", "net.hk", "idv.hk",
    "com.tw", "org.tw", "edu.tw", "gov.tw", "net.tw", "idv.tw", "game.tw",
    "ebiz.tw", "club.tw", "mil.tw",
    "com.mo", "net.mo", "org.mo", "edu.mo", "gov.mo",
    # China
    "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn", "ac.cn", "mil.cn",
    "ah.cn", "bj.cn", "cq.cn", "fj.cn", "gd.cn", "gs.cn", "gz.cn", "gx.cn",
    "ha.cn", "hb.cn", "he.cn", "hi.cn", "hl.cn", "hn.cn", "jl.cn", "js.cn",
    "jx.cn", "ln.cn", "nm.cn", "nx.cn", "qh.cn", "sc.cn", "sd.cn", "sh.cn",
    "sn.cn", "sx.cn", "tj.cn", "xj.cn", "xz.cn", "yn.cn", "zj.cn",
    # Japan / Korea
    "co.jp", "or.jp", "ne.jp", "ac.jp", "go.jp", "ad.jp", "ed.jp", "gr.jp",
    "lg.jp",
    "co.kr", "or.kr", "ne.kr", "go.kr", "ac.kr", "re.kr", "pe.kr", "hs.kr",
    "ms.kr", "es.kr", "sc.kr", "kg.kr", "mil.kr", "busan.kr", "seoul.kr",
    # India / PK / BD / LK
    "co.in", "net.in", "org.in", "gen.in", "firm.in", "ind.in", "ac.in",
    "edu.in", "res.in", "gov.in", "mil.in", "nic.in",
    "com.pk", "net.pk", "org.pk", "gov.pk", "edu.pk", "web.pk", "fam.pk",
    "com.bd", "net.bd", "org.bd", "ac.bd", "edu.bd", "gov.bd",
    "com.lk", "org.lk", "edu.lk", "gov.lk", "net.lk", "ac.lk",
    # Middle East
    "co.il", "org.il", "ac.il", "gov.il", "net.il", "k12.il", "muni.il", "idf.il",
    "co.ae", "net.ae", "org.ae", "ac.ae", "gov.ae", "sch.ae", "mil.ae",
    "com.sa", "net.sa", "org.sa", "gov.sa", "edu.sa", "med.sa", "pub.sa", "sch.sa",
    "com.eg", "edu.eg", "eun.eg", "gov.eg", "mil.eg", "name.eg", "net.eg",
    "org.eg", "sci.eg",
    "com.tr", "org.tr", "gov.tr", "edu.tr", "net.tr", "av.tr", "bel.tr",
    "dr.tr", "gen.tr", "k12.tr", "pol.tr", "web.tr",
    "org.ir", "co.ir", "ac.ir", "gov.ir", "id.ir", "net.ir", "sch.ir",
    # Africa
    "co.za", "org.za", "web.za", "gov.za", "ac.za", "edu.za", "net.za",
    "law.za", "mil.za", "nom.za", "school.za",
    "co.ke", "or.ke", "ac.ke", "go.ke", "ne.ke", "sc.ke", "me.ke", "info.ke",
    "mobi.ke",
    "com.ng", "org.ng", "gov.ng", "edu.ng", "net.ng", "sch.ng", "mil.ng",
    "name.ng", "mobi.ng",
    "co.ug", "or.ug", "ac.ug", "go.ug", "ne.ug", "sc.ug", "com.ug",
    "co.tz", "or.tz", "ac.tz", "go.tz", "ne.tz", "sc.tz", "hotel.tz",
    "co.bw", "org.bw", "ac.bw", "gov.bw",
    "co.zw", "org.zw", "ac.zw", "gov.zw",
    "co.ao", "ed.ao", "gv.ao", "it.ao", "og.ao", "pb.ao",
    "co.ls", "org.ls", "ac.ls", "gov.ls",
    "co.sz", "ac.sz", "org.sz",
    "co.mz", "org.mz", "ac.mz", "gov.mz", "edu.mz",
    "co.zm", "org.zm", "ac.zm", "gov.zm", "edu.zm", "net.zm", "sch.zm",
    "co.na", "org.na", "alt.na", "edu.na",
    "co.mg", "org.mg", "nom.mg", "gov.mg", "prd.mg", "tm.mg", "edu.mg", "mil.mg",
    "co.ci", "or.ci", "ed.ci", "go.ci", "ac.ci", "net.ci", "edu.ci", "int.ci",
    "com.gh", "edu.gh", "gov.gh", "org.gh", "mil.gh",
    "co.rw", "org.rw", "ac.rw", "gov.rw", "net.rw",
    "co.tz",
    # Europe (selected multi-part)
    "com.es", "nom.es", "org.es", "gob.es", "edu.es",
    "com.pt", "edu.pt", "gov.pt", "org.pt", "int.pt", "net.pt", "publ.pt",
    "com.pl", "net.pl", "org.pl", "gov.pl", "edu.pl", "info.pl", "biz.pl",
    "com.ru", "net.ru", "org.ru", "pp.ru", "spb.ru", "msk.ru",
    "com.ua", "org.ua", "net.ua", "gov.ua", "edu.ua", "in.ua", "co.ua",
    "com.ro", "or.at", "co.at", "ac.at", "gv.at",
    "co.no",  # not actually used widely; harmless if present
    "com.gr", "edu.gr", "gov.gr", "net.gr", "org.gr",
    "com.hr", "com.mk", "com.mt", "com.cy",
    "ac.rs", "co.rs", "edu.rs", "gov.rs", "in.rs", "org.rs",
    "com.bg", "gov.bg",
    "com.hr",
    "asn.lv", "conf.lv", "edu.lv", "gov.lv", "id.lv", "mil.lv", "net.lv", "org.lv",
    "com.ge", "edu.ge", "gov.ge", "org.ge", "net.ge", "pvt.ge", "school.ge",
    # Americas
    "com.br", "net.br", "org.br", "gov.br", "edu.br", "mil.br", "art.br",
    "adv.br", "adm.br", "ind.br", "inf.br", "jor.br", "lel.br", "tmp.br",
    "blog.br", "flog.br", "nom.br", "rec.br", "vlog.br", "wiki.br", "tv.br",
    "com.mx", "org.mx", "gob.mx", "edu.mx", "net.mx",
    "com.ar", "org.ar", "gob.ar", "edu.ar", "net.ar", "tur.ar", "int.ar",
    "mil.ar",
    "com.co", "org.co", "gov.co", "edu.co", "net.co", "mil.co", "nom.co",
    "com.pe", "org.pe", "gob.pe", "edu.pe", "net.pe", "mil.pe", "nom.pe",
    "com.cl",  # most Chilean sites use .cl; harmless
    "com.ve", "co.ve", "org.ve", "gov.ve", "edu.ve", "net.ve", "mil.ve", "web.ve",
    "com.uy", "edu.uy", "gub.uy", "net.uy", "org.uy", "mil.uy",
    "com.ec", "edu.ec", "gov.ec", "org.ec", "net.ec", "mil.ec", "med.ec", "fin.ec",
    "com.bo", "net.bo", "org.bo", "gov.bo", "edu.bo", "mil.bo", "int.bo", "tv.bo",
    "com.py", "edu.py", "gov.py", "org.py", "net.py", "mil.py",
    "com.pa", "ac.pa", "gob.pa", "edu.pa", "org.pa", "net.pa", "ing.pa", "med.pa",
    "com.do", "edu.do", "gob.do", "org.do", "net.do", "mil.do", "sld.do", "web.do",
    "com.gt", "edu.gt", "gob.gt", "ind.gt", "mil.gt", "net.gt", "org.gt",
    "com.sv", "edu.sv", "gob.sv", "org.sv", "red.sv",
    "com.hn", "edu.hn", "gob.hn", "mil.hn", "net.hn", "org.hn",
    "com.ni", "gob.ni", "edu.ni", "org.ni", "nom.ni", "net.ni", "mil.ni", "co.ni",
    "com.cr", "co.cr", "ac.cr", "ed.cr", "fi.cr", "go.cr", "or.cr", "sa.cr",
    "com.cu", "edu.cu", "gov.cu", "org.cu", "net.cu", "inf.cu",
    "com.pr", "net.pr", "org.pr", "edu.pr", "gov.pr", "ac.pr", "isla.pr",
    "com.ag", "co.ag", "net.ag", "org.ag", "nom.ag",
    "com.bs", "net.bs", "org.bs", "edu.bs", "gov.bs",
    "com.bb", "net.bb", "org.bb", "gov.bb", "edu.bb",
    "com.jm", "net.jm", "org.jm", "edu.jm", "gov.jm", "mil.jm",
    "com.tt", "net.tt", "org.tt", "gov.tt", "edu.tt", "biz.tt", "co.tt", "name.tt",
    "co.vi", "com.vi", "net.vi", "org.vi",
    "com.bz", "net.bz", "org.bz", "edu.bz", "gov.bz",
    "com.gy", "co.gy", "net.gy", "org.gy", "edu.gy", "gov.gy",
    "com.sr",
    "com.ai", "net.ai", "off.ai", "org.ai", "com.vc", "net.vc", "org.vc", "gov.vc",
    "com.lc", "net.lc", "org.lc", "co.lc", "com.dm", "net.dm", "org.dm", "edu.dm",
    "com.gd", "net.gd", "org.gd", "gov.gd", "edu.gd",
    "com.ht", "net.ht", "org.ht", "edu.ht", "gob.ht", "pol.ht", "rel.ht", "med.ht",
    "com.aw",
    # Canada / US multi-part (selected)
    "gc.ca", "gov.bc.ca", "gov.on.ca", "gov.ab.ca", "gov.qc.ca",
    "co.uk",  # already
    "ac.uk",
    # Other ccTLD multi-part
    "com.au",
    "com.fj", "ac.fj", "gov.fj", "biz.fj", "org.fj", "mil.fj", "net.fj", "pro.fj", "school.fj",
    "com.pg", "net.pg", "ac.pg", "gov.pg", "org.pg",
    "com.sb", "net.sb", "org.sb", "edu.sb", "gov.sb",
    "com.ws",  # usually .ws
    "com.nr", "net.nr", "org.nr", "edu.nr", "gov.nr", "biz.nr", "info.nr",
    "com.ki", "net.ki", "org.ki", "edu.ki", "gov.ki", "biz.ki", "info.ki",
    "com.mu", "net.mu", "org.mu", "gov.mu", "ac.mu", "co.mu", "or.mu",
    "com.sc", "net.sc", "org.sc", "gov.sc", "edu.sc",
    "com.lv",
    "com.ee",
    "com.is",
    "com.ac", "edu.ac", "gov.ac", "mil.ac", "net.ac", "org.ac",
    "com.sh", "net.sh", "org.sh", "gov.sh", "mil.sh", "edu.sh",
    "com.io",  # not actually a suffix; harmless
    "com.by", "gov.by", "mil.by", "of.by",
    "com.kz", "org.kz", "edu.kz", "gov.kz", "mil.kz", "net.kz",
    "com.uz", "co.uz", "org.uz", "gov.uz", "net.uz",
    "com.tm", "co.tm", "org.tm", "net.tm", "edu.tm", "gov.tm",
    "com.az", "net.az", "org.az", "gov.az", "edu.az", "mil.az", "biz.az", "pp.az",
    "com.am", "net.am", "org.am",
    "co.hu", "org.hu", "priv.hu", "sport.hu", "news.hu", "info.hu", "shop.hu",
    "com.hr", "iz.hr", "from.hr", "name.hr", "com.ba", "edu.ba", "gov.ba", "mil.ba", "net.ba", "org.ba", "rs.ba", "unsa.ba", "co.ba",
    "com.al", "edu.al", "gov.al", "mil.al", "net.al", "org.al",
    "com.mk", "org.mk", "net.mk", "edu.mk", "gov.mk", "inf.mk",
    "com.me", "net.me", "org.me", "edu.me", "gov.me", "its.me", "priv.me",
    "co.rs",
    "com.lk",
    # Common private / platform suffixes so each tenant gets its own folder
    "github.io", "githubusercontent.com", "herokuapp.com", "azurewebsites.net",
    "cloudfront.net", "vercel.app", "now.sh", "netlify.app", "netlify.com",
    "pages.dev", "workers.dev", "gitlab.io", "bitbucket.io", "web.app",
    "firebaseapp.com", "appspot.com", "blogspot.com", "wordpress.com",
    "tumblr.com", "ghost.io", "shopify.com", "myshopify.com", "weebly.com",
    "squarespace.com", "wixsite.com", "carrd.co", "glitch.me", "repl.co",
    "hypha.app",
})

_HOST_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _hostname(url_or_host: str) -> str:
    raw = (url_or_host or "").strip()
    if not raw:
        return ""
    if "://" in raw or raw.startswith("//"):
        host = urlparse(raw if "://" in raw else "https:" + raw).hostname or ""
    elif raw.startswith("[") and "]" in raw:
        host = raw[1:raw.index("]")]
    else:
        # Bare host, or host:port, or a path-less URL typo
        host = raw.split("/")[0]
        if "@" in host:
            host = host.rsplit("@", 1)[-1]
        if host.count(":") == 1:
            # hostname:port (not IPv6)
            left, right = host.rsplit(":", 1)
            if right.isdigit():
                host = left
        host = host.strip().strip("[]")
    return host.rstrip(".").lower()


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def public_suffix(host: str) -> str:
    """Return the public suffix of a hostname (no scheme)."""
    host = (host or "").rstrip(".").lower()
    if not host or _is_ip(host):
        return host
    labels = [p for p in host.split(".") if p]
    if not labels:
        return host
    for n in range(len(labels), 1, -1):
        cand = ".".join(labels[-n:])
        if cand in MULTIPART_SUFFIXES:
            return cand
    return labels[-1]


def registrable_domain(url_or_host: str) -> str:
    """Return the registrable domain (eTLD+1) for a URL or hostname.

    Examples:
        https://www.example.com/ → example.com
        https://btphysio.com.au/ → btphysio.com.au
        shop.raisewell.com.sg → raisewell.com.sg
        https://www.bbc.co.uk/news → bbc.co.uk
    """
    host = _hostname(url_or_host)
    if not host:
        return ""
    if _is_ip(host):
        return host
    suffix = public_suffix(host)
    if not suffix:
        return host
    if host == suffix:
        # The host *is* the suffix (e.g. "com.au") — keep it, callers should
        # still not use this as a shared customer folder for different sites.
        return host
    if not host.endswith("." + suffix):
        return host
    rest = host[: -(len(suffix) + 1)]
    left = rest.split(".")[-1] if rest else ""
    return f"{left}.{suffix}" if left else host
