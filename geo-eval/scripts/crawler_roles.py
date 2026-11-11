#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Crawler purpose split for GEO Checker access scoring.

Training crawlers, search-index crawlers, and on-demand/user fetchers are
classified separately. Only blocked *search-index* or *user-access* crawlers
may reduce the core access/readiness score. Training-bot blocks are
informational and must not be worded as "the AI search engine cannot see
this site."

Google-Extended is a robots training/generation token with no independent
User-Agent — never invent a UA to probe it, and never treat it as a
search-access core item.

Claude search status is determined by Claude-SearchBot, not ClaudeBot.
ChatGPT search status is determined by OAI-SearchBot (and ChatGPT-User when
tested), not GPTBot.
"""

from __future__ import annotations

# Robots tokens / UA names by purpose.
TRAINING_TOKENS = frozenset({
    "GPTBot",
    "ClaudeBot",
    "Google-Extended",
    "GoogleExtendedCrawler",  # unofficial alias some sites invent; still training
    "anthropic-ai",
    "Applebot-Extended",
    "CCBot",
})

SEARCH_INDEX_TOKENS = frozenset({
    "OAI-SearchBot",
    "Claude-SearchBot",
    "PerplexityBot",
    "Googlebot",
    "Bingbot",
    "Applebot",
    "DuckDuckBot",
})

USER_FETCHER_TOKENS = frozenset({
    "ChatGPT-User",
    "Claude-User",
    "Perplexity-User",
})

CORE_ACCESS_TOKENS = SEARCH_INDEX_TOKENS | USER_FETCHER_TOKENS

# Official probe UAs. Google-Extended is intentionally absent.
SEARCH_UA_PROBES = {
    "Googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
}

# Search-index and user-fetcher probes that feed the core access decision.
CORE_UA_PROBES = {
    "OAI-SearchBot": "Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",
    "Claude-SearchBot": (
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
        "Claude-SearchBot/1.0; +claude-searchbot@anthropic.com)"
    ),
    "PerplexityBot": "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "ChatGPT-User": "Mozilla/5.0 (compatible; ChatGPT-User/1.0; +https://openai.com/bot)",
}

# Training probes are evidence-only (do not drive the core penalty).
TRAINING_UA_PROBES = {
    "GPTBot": "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)",
    "ClaudeBot": "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
}

# Combined probe list used by run.py (search + core + training). No Google-Extended.
AI_AND_SEARCH_PROBES = {**SEARCH_UA_PROBES, **CORE_UA_PROBES, **TRAINING_UA_PROBES}

# Backward-compatible name: historical AI_UA_PROBES mixed training + search.
AI_UA_PROBES = {**CORE_UA_PROBES, **TRAINING_UA_PROBES}

ENGINE_MAP = {
    "chatgpt_search": {
        "search": "OAI-SearchBot",
        "user": "ChatGPT-User",
        "training": "GPTBot",
        "label_zh": "ChatGPT 搜索",
        "label_en": "ChatGPT search",
    },
    "claude_search": {
        "search": "Claude-SearchBot",
        "user": "Claude-User",
        "training": "ClaudeBot",
        "label_zh": "Claude 搜索",
        "label_en": "Claude search",
    },
    "perplexity_search": {
        "search": "PerplexityBot",
        "user": "Perplexity-User",
        "training": None,
        "label_zh": "Perplexity 搜索",
        "label_en": "Perplexity search",
    },
}


def role_of(name: str) -> str:
    """Return training | search_index | user_fetcher | unknown."""
    ua = (name or "").strip()
    if ua in TRAINING_TOKENS:
        return "training"
    if ua in SEARCH_INDEX_TOKENS:
        return "search_index"
    if ua in USER_FETCHER_TOKENS:
        return "user_fetcher"
    return "unknown"


def is_core_access(name: str) -> bool:
    return role_of(name) in ("search_index", "user_fetcher")


def split_by_role(names) -> dict:
    out = {"training": [], "search_index": [], "user_fetcher": [], "unknown": []}
    for n in names or []:
        out[role_of(n)].append(n)
    return out


def _result_blocked(row: dict) -> bool:
    if not row:
        return False
    if row.get("challenge"):
        return True
    status = row.get("status")
    return status in (0, 403, 429, 401)


def _result_ok(row: dict) -> bool:
    if not row:
        return False
    status = row.get("status")
    return status in (200, 304) and not row.get("challenge") and not row.get("error")


def index_ua_results(ua_results) -> dict:
    by_name = {}
    for row in ua_results or []:
        name = row.get("ua") or row.get("name")
        if name:
            by_name[name] = row
    return by_name


def classify_live(ua_results) -> dict:
    """Split live probe rows into core-blocked, training-blocked, ok, untested."""
    by_name = index_ua_results(ua_results)
    core_blocked, training_blocked, core_ok, training_ok = [], [], [], []
    for name, row in by_name.items():
        if name == "browser":
            continue
        role = role_of(name)
        if _result_blocked(row):
            if role in ("search_index", "user_fetcher"):
                core_blocked.append(name)
            elif role == "training":
                training_blocked.append(name)
        elif _result_ok(row):
            if role in ("search_index", "user_fetcher"):
                core_ok.append(name)
            elif role == "training":
                training_ok.append(name)
    return {
        "by_name": by_name,
        "core_blocked": core_blocked,
        "training_blocked": training_blocked,
        "core_ok": core_ok,
        "training_ok": training_ok,
    }


def classify_robots(blocked_tokens) -> dict:
    split = split_by_role(blocked_tokens)
    return {
        "core_blocked": split["search_index"] + split["user_fetcher"],
        "training_blocked": split["training"],
        "unknown_blocked": split["unknown"],
        "split": split,
    }


def probe_status(by_name: dict, token: str | None) -> str:
    """allowed | blocked | untested | not_applicable."""
    if not token:
        return "not_applicable"
    row = by_name.get(token)
    if row is None:
        return "untested"
    if _result_ok(row):
        return "allowed"
    if _result_blocked(row):
        return "blocked"
    # Unexpected status (e.g. 500, 404) — treat as a single observation, not a
    # definitive search-access failure.
    return "unverified"


def engine_access_status(ua_results, robots_blocked=None) -> dict:
    """Per-engine search access: never infer search from a training bot alone."""
    by_name = index_ua_results(ua_results)
    robots = set(robots_blocked or [])
    engines = {}
    for key, spec in ENGINE_MAP.items():
        search_tok = spec["search"]
        user_tok = spec.get("user")
        train_tok = spec.get("training")
        search_live = probe_status(by_name, search_tok)
        user_live = probe_status(by_name, user_tok)
        train_live = probe_status(by_name, train_tok)
        search_robots = "blocked" if search_tok in robots else (
            "untested" if search_tok not in (list(by_name) + list(robots)) and search_live == "untested"
            else "allowed"
        )
        if search_tok in robots:
            search_robots = "blocked"
        else:
            # robots did not name this token as blocked (may still be untested live)
            search_robots = "not_blocked"

        # Search status is driven by the search-index crawler (and user fetcher
        # if tested). Training results are attached only as context.
        if search_live == "allowed" or user_live == "allowed":
            search_status = "allowed"
        elif search_live == "blocked" or search_robots == "blocked":
            search_status = "blocked"
        elif search_live in ("untested", "unverified") and user_live in ("untested", "not_applicable", "unverified"):
            search_status = "unverified"
        else:
            search_status = "unverified"

        engines[key] = {
            "label_zh": spec["label_zh"],
            "label_en": spec["label_en"],
            "search_status": search_status,
            "search_token": search_tok,
            "search_live": search_live,
            "user_token": user_tok,
            "user_live": user_live,
            "training_token": train_tok,
            "training_live": train_live,
            "training_robots_blocked": bool(train_tok and train_tok in robots),
        }
    return engines


def core_penalty_decision(robots_blocked, ua_results, waf_challenge=False) -> dict:
    """Decide whether to apply the −15 core access penalty.

    Training-only blocks never trigger the penalty.
    A browser WAF challenge only triggers the penalty when no core search
    crawler was observed succeeding (otherwise the challenge may be
    UA-specific and search bots already get through).
    """
    robots = classify_robots(robots_blocked)
    live = classify_live(ua_results)
    by_name = live["by_name"]
    browser = by_name.get("browser") or {}
    browser_waf = bool(waf_challenge) or _result_blocked(browser)

    core_robots = list(robots["core_blocked"])
    core_live = list(live["core_blocked"])
    core_ok = list(live["core_ok"])

    apply = bool(core_robots or core_live)
    if browser_waf and not core_ok and not apply:
        # Site-wide challenge and no successful core search probe.
        apply = True
        reason_kind = "waf_no_core_ok"
    elif apply and core_robots and core_live:
        reason_kind = "robots_and_live"
    elif core_robots:
        reason_kind = "robots"
    elif core_live:
        reason_kind = "live"
    else:
        reason_kind = "none"

    return {
        "apply": apply,
        "points": -15 if apply else 0,
        "reason_kind": reason_kind,
        "core_robots_blocked": core_robots,
        "core_live_blocked": core_live,
        "core_ok": core_ok,
        "training_robots_blocked": list(robots["training_blocked"]),
        "training_live_blocked": list(live["training_blocked"]),
        "browser_waf": browser_waf,
        "engines": engine_access_status(ua_results, robots_blocked),
    }


def penalty_reason_zh(decision: dict) -> str:
    robots = decision.get("core_robots_blocked") or []
    live = decision.get("core_live_blocked") or []
    if decision.get("reason_kind") == "waf_no_core_ok":
        return "搜索/按需抓取爬虫不可达：普通请求命中 WAF/挑战页，且未见搜索索引或按需抓取爬虫成功取到页面"
    if robots and live:
        return (
            "搜索/按需抓取爬虫不可达：robots.txt 屏蔽 "
            + ", ".join(robots)
            + "；实测同样被拦截（WAF/挑战页）。两种成因计一次"
        )
    if robots:
        return "搜索/按需抓取爬虫被 robots.txt 屏蔽（" + ", ".join(robots) + "）"
    if live:
        return (
            "搜索/按需抓取爬虫实测被拦截（"
            + ", ".join(live)
            + " 命中 WAF/挑战页，robots.txt 放行但取不到）"
        )
    return ""


def engine_status_lines_zh(engines: dict) -> list[str]:
    lines = []
    status_zh = {
        "allowed": "可访问",
        "blocked": "被拦截",
        "unverified": "未核实",
    }
    for spec in (engines or {}).values():
        st = spec.get("search_status")
        label = spec.get("label_zh") or spec.get("label_en")
        search_tok = spec.get("search_token")
        search_live = spec.get("search_live")
        train_tok = spec.get("training_token")
        train_live = spec.get("training_live")
        extra = []
        if train_tok and train_live == "blocked":
            extra.append(f"训练爬虫 {train_tok} 被拦截（不影响搜索判定）")
        if search_live == "untested":
            extra.append(f"{search_tok} 本次未实测，故搜索状态为未核实")
        suffix = "；".join(extra)
        line = f"{label}：{status_zh.get(st, st)}"
        if suffix:
            line += f"（{suffix}）"
        lines.append(line)
    return lines


def should_not_claim_search_blocked(engines: dict, product: str) -> bool:
    """True when we must not say that product's search is blocked."""
    key = {"chatgpt": "chatgpt_search", "claude": "claude_search", "perplexity": "perplexity_search"}.get(
        product, product
    )
    spec = (engines or {}).get(key) or {}
    return spec.get("search_status") != "blocked"
