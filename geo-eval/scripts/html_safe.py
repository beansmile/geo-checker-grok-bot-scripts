#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML escaping, mustache-safe interpolation, href allowlist, and CSP for reports."""

from __future__ import annotations

import base64
import hashlib
import html as html_mod
import re
from urllib.parse import urlparse


def esc(s, quote: bool = True) -> str:
    return html_mod.escape("" if s is None else str(s), quote=True)


def neutralize_mustache(s: str) -> str:
    """Prevent leftover {{word}} inside interpolated values from matching templates."""
    return (s or "").replace("{{", "&#123;&#123;").replace("}}", "&#125;&#125;")


def inline_md(s: str, breaks: bool = True) -> str:
    """Escape first, then restore a tiny whitelist of <strong>/<br> and **bold**/`code`.

    Agent/LLM narrative may contain <strong>/<br> or markdown; anything else
    stays escaped. Mustache braces in the value are neutralized.
    """
    text = esc(s)
    # Restore a deliberate whitelist after escaping.
    text = re.sub(r"&lt;(/?)strong&gt;", r"<\1strong>", text, flags=re.I)
    text = re.sub(r"&lt;br\s*/?&gt;", "<br>", text, flags=re.I)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    if breaks:
        text = text.replace("\n", "<br>")
    return neutralize_mustache(text)


def safe_href(url: str) -> str:
    """Attribute-safe href. Allows http(s) URLs and in-page #fragments only."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if raw.startswith("#") and "\n" not in raw and "\r" not in raw:
        # Keep a simple fragment; drop anything that could break out of the attr.
        if any(c in raw for c in ('"', "'", "<", ">", "`")):
            return ""
        return esc(raw, quote=True)
    p = urlparse(raw)
    if (p.scheme or "").lower() in ("http", "https") and p.netloc:
        return esc(raw, quote=True)
    return ""


def sha256_csp(text: str) -> str:
    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


def csp_meta(script: str, style: str | None = None) -> str:
    """Build a CSP <meta> that allows this report's inlined CSS/JS by hash only."""
    parts = [
        "default-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
        "img-src data:",
        "font-src 'none'",
        "connect-src 'none'",
        "object-src 'none'",
        "frame-src 'none'",
    ]
    if style:
        parts.append(f"style-src '{sha256_csp(style)}'")
    else:
        parts.append("style-src 'unsafe-inline'")
    if script:
        parts.append(f"script-src '{sha256_csp(script)}'")
    else:
        parts.append("script-src 'none'")
    content = "; ".join(parts)
    # Content is only fixed tokens + base64 hashes; keep source-text quotes so
    # browsers see default-src 'none' rather than &#x27;none&#x27;.
    if "<" in content or ">" in content or '"' in content:
        raise ValueError("refusing to emit CSP with unexpected characters")
    return f'<meta http-equiv="Content-Security-Policy" content="{content}">'


_TRUSTED_MUSTACHE_KEYS = frozenset({"style", "script", "csp_meta"})


def render_mustache(template: str, data: dict, trusted_keys=None) -> str:
    """Minimal {{var}} / {{#list}} renderer that will not re-interpolate values."""
    trusted = _TRUSTED_MUSTACHE_KEYS if trusted_keys is None else frozenset(trusted_keys)

    def safe(v, key=None) -> str:
        s = "" if v is None else str(v)
        if key in trusted:
            return s
        return neutralize_mustache(s)

    def expand_lists(text: str) -> str:
        out = []
        i = 0
        while i < len(text):
            m = re.search(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", text[i:], re.S)
            if not m:
                out.append(text[i:])
                break
            out.append(text[i:i + m.start()])
            key, body = m.group(1), m.group(2)
            items = data.get(key) or []
            for item in items:
                rendered = body
                if isinstance(item, dict):
                    for k, v in item.items():
                        rendered = rendered.replace("{{%s}}" % k, safe(v, k))
                else:
                    rendered = rendered.replace("{{.}}", safe(item))
                out.append(rendered)
            i += m.end()
        return "".join(out)

    text = expand_lists(template)

    def sub(m):
        key = m.group(1)
        return safe(data.get(key, ""), key)

    return re.sub(r"\{\{(\w+)\}\}", sub, text)
