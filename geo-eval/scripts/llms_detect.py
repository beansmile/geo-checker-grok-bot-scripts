#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detect /llms.txt as an experimental/auxiliary signal — not part of the core 100.

Keeps detection, but:
- does not invent a missing file when the body is binary / oddly encoded;
- flags disguised 404, wrong MIME, and soft-404 HTML;
- never contributes a general-purpose bonus or penalty to the core score.
"""

from __future__ import annotations

import re

SOFT404_PATTERNS = re.compile(
    r"(?:page\s+not\s+found|not\s+found|404\s*error|页面不存在|未找到页面|"
    r"sorry,\s+we\s+can'?t\s+find|the\s+page\s+you\s+requested)",
    re.I,
)
HTML_START = re.compile(r"^\s*(<!doctype\s+html|<html\b)", re.I)
# A real llms.txt is usually markdown-ish: headings, list of links, "Documentation:".
LLMS_HINT = re.compile(
    r"(^#\s|\bllms\.txt\b|documentation\s*:|^\s*-\s+https?://)",
    re.I | re.M,
)


def _try_decode(raw) -> tuple[str, str]:
    """Return (text, encoding_used). Never treat undecodable bytes as 'missing'."""
    if raw is None:
        return "", "empty"
    if isinstance(raw, str):
        # Already decoded by the caller. Detect leftover replacement-heavy text later.
        return raw, "str"
    if not isinstance(raw, (bytes, bytearray)):
        return str(raw), "str"

    data = bytes(raw)
    if not data:
        return "", "empty"

    # BOM-aware
    if data.startswith(b"\xff\xfe"):
        try:
            return data.decode("utf-16-le"), "utf-16-le"
        except UnicodeDecodeError:
            pass
    if data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16-be"), "utf-16-be"
        except UnicodeDecodeError:
            pass
    if data.startswith(b"\xef\xbb\xbf"):
        try:
            return data.decode("utf-8-sig"), "utf-8-sig"
        except UnicodeDecodeError:
            pass

    for enc in ("utf-8", "utf-16", "gb18030", "latin-1"):
        try:
            text = data.decode(enc)
            # latin-1 always succeeds; only accept it if the text looks textual.
            if enc == "latin-1" and _binary_ratio(data) > 0.30:
                continue
            return text, enc
        except UnicodeDecodeError:
            continue
    # Last resort: replace so we can still inspect, but flag as binary.
    return data.decode("utf-8", "replace"), "binary-replace"


def _binary_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    sample = data[:4096]
    nul = sample.count(b"\x00")
    nontext = sum(1 for b in sample if b < 9 or (13 < b < 32 and b != 27) or b == 0x7F)
    return (nul + nontext) / max(1, len(sample))


def _looks_html(text: str, content_type: str | None) -> bool:
    ct = (content_type or "").lower()
    if "text/html" in ct or "application/xhtml" in ct:
        return True
    return bool(HTML_START.search(text or ""))


def inspect_llms(body, status=None, content_type=None, url="/llms.txt") -> dict:
    """Inspect a fetched llms.txt body.

    Return a dict:
      present (bool) — a usable non-HTML llms.txt-like document was found
      quality — none | low | ok | high
      reasons — human-readable flags
      experimental — always True (not in core score)
      body_preview, encoding, status, content_type
    """
    reasons = []
    text, encoding = _try_decode(body)
    raw = body if isinstance(body, (bytes, bytearray)) else None
    binaryish = encoding in ("binary-replace",) or (raw is not None and _binary_ratio(bytes(raw)) > 0.30)

    status_i = None
    try:
        if status is not None and status != "":
            status_i = int(status)
    except (TypeError, ValueError):
        status_i = None

    result = {
        "url": url,
        "present": False,
        "quality": "none",
        "reasons": reasons,
        "experimental": True,
        "in_core_score": False,
        "status": status_i,
        "content_type": content_type or "",
        "encoding": encoding,
        "body_length": len(text or ""),
        "binary": bool(binaryish),
        "soft_404": False,
        "disguised_404": False,
        "wrong_mime": False,
        "body_preview": (text or "")[:240],
    }

    if status_i in (404, 410):
        reasons.append(f"HTTP {status_i} — 文件不存在")
        return result
    if status_i and status_i >= 500:
        reasons.append(f"HTTP {status_i} — 单次观察，未将文件判为缺失")
        result["quality"] = "unverified"
        return result
    if status_i and status_i not in (200, 304) and status_i != 0 and status_i is not None:
        # 403/401 etc.
        reasons.append(f"HTTP {status_i} — 未能读取，不按缺失计核心分")
        result["quality"] = "unverified"
        return result

    stripped = (text or "").strip()
    if not stripped:
        if binaryish:
            reasons.append("响应体为二进制且未能解码为文本，不按“文件缺失”计")
            result["quality"] = "unverified"
            return result
        reasons.append("响应体为空")
        return result

    if _looks_html(stripped, content_type):
        result["wrong_mime"] = "text/html" in (content_type or "").lower() or True
        result["soft_404"] = True
        if SOFT404_PATTERNS.search(stripped) or status_i == 200:
            result["disguised_404"] = bool(SOFT404_PATTERNS.search(stripped) or len(stripped) < 400)
        reasons.append("返回的是 HTML 页面（伪装 404 或站点模板），不是 llms.txt 文本")
        return result

    ct = (content_type or "").lower()
    if ct and not any(x in ct for x in ("text/plain", "text/markdown", "text/x-markdown", "application/octet-stream", "text/")):
        result["wrong_mime"] = True
        reasons.append(f"Content-Type 异常：{content_type}")

    if SOFT404_PATTERNS.search(stripped) and len(stripped) < 800:
        result["disguised_404"] = True
        result["soft_404"] = True
        reasons.append("文本短且含 404/未找到用语，视为软 404")
        return result

    if len(stripped) <= 10:
        reasons.append("正文过短，无法视为有效 llms.txt")
        return result

    # Binary successfully decoded (e.g. UTF-16) — treat as present if textual.
    if binaryish and len(stripped) > 10 and not _looks_html(stripped, content_type):
        reasons.append("正文以非常规编码/二进制保存，已成功解码")

    result["present"] = True
    if LLMS_HINT.search(stripped) and len(stripped) >= 80:
        result["quality"] = "high" if len(stripped) >= 200 else "ok"
    elif len(stripped) >= 40:
        result["quality"] = "ok"
        reasons.append("文件存在，但结构不像典型的 llms.txt（缺少标题或文档链接）")
    else:
        result["quality"] = "low"
        reasons.append("文件存在但内容很短")
    return result


def load_from_run(run_dir: str) -> dict:
    """Read evidence/llms.txt plus optional evidence/llms.meta.json."""
    import json
    import os

    meta = {}
    meta_path = os.path.join(run_dir, "evidence", "llms.meta.json")
    if os.path.isfile(meta_path):
        try:
            meta = json.load(open(meta_path, encoding="utf-8"))
        except (ValueError, OSError):
            meta = {}

    path = os.path.join(run_dir, "evidence", "llms.txt")
    raw = b""
    if os.path.isfile(path):
        with open(path, "rb") as f:
            raw = f.read()
    status = meta.get("status")
    content_type = meta.get("content_type") or meta.get("content-type")
    url = meta.get("url") or "/llms.txt"
    return inspect_llms(raw, status=status, content_type=content_type, url=url)
