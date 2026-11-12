#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Combined GEO Checker score: technical 40% + content 60%, plus an access gate.

Published combined scores (and any customer-facing weighted breakdown) use
0 / 0.5 increments via snap_half. 40/60 is a product contract, not a
percentage published by any vendor.
"""

from __future__ import annotations

import math

try:
    from content_analyze import snap_half, grade_for, clamp
except ImportError:  # pragma: no cover
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from content_analyze import snap_half, grade_for, clamp

try:
    import crawler_roles
except ImportError:  # pragma: no cover
    crawler_roles = None


TECH_WEIGHT = 0.40
CONTENT_WEIGHT = 0.60
GATE_CAP_HARD = 30  # Googlebot blocked or all verified search crawlers blocked
GATE_CAP_SOFT = 50  # core search/on-demand access penalty already applied

# Search-index tokens that can trigger the "all search crawlers blocked" cap.
# User-initiated fetchers belong to the soft (core access) gate, not this set.
# Training tokens never trigger either gate.
_EXTRA_SEARCH_INDEX = frozenset({
    "Kimi-SearchBot",
    "Meta-WebIndexer",
})


def format_score(n) -> str:
    """Show integers as 18, half-points as 17.5; never 18.0 or 7.3."""
    if n is None or n == "":
        return "—"
    x = float(n)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.1f}"


def _norm_token(name) -> str:
    return str(name or "").strip()


def _role_of(name: str) -> str:
    if crawler_roles is not None:
        role = crawler_roles.role_of(name)
        if role != "unknown":
            return role
    token = _norm_token(name)
    if token in _EXTRA_SEARCH_INDEX:
        return "search_index"
    if token in {"KimiBot"}:
        return "training"
    if token in {"Kimi-User", "Meta-ExternalFetcher"}:
        return "user_fetcher"
    # Mixed training AND product indexing — not training-only.
    if token == "Meta-ExternalAgent":
        return "unknown"
    return "unknown"


def _is_training(name: str) -> bool:
    return _role_of(name) == "training"


def _is_search_index(name: str) -> bool:
    return _role_of(name) == "search_index"


def _blocked_name_lists(tech: dict) -> dict:
    """Collect crawler name lists from a technical report (or a test stub)."""
    scope = tech.get("scope") or {}
    acc = scope.get("crawler_access") or tech.get("crawler_access") or {}
    roles = acc.get("roles") or {}
    decision = acc.get("crawler_decision") or tech.get("crawler_decision") or {}

    def _lst(*seqs):
        out = []
        seen = set()
        for seq in seqs:
            for item in seq or []:
                n = _norm_token(item)
                if n and n not in seen:
                    seen.add(n)
                    out.append(n)
        return out

    core_blocked = _lst(
        roles.get("core_blocked"),
        acc.get("ai_blocked"),
        acc.get("blocked_core"),
        decision.get("core_robots_blocked"),
        decision.get("core_live_blocked"),
        # scope.blocked is the core (non-training) list in current reports
        scope.get("blocked"),
        tech.get("core_blocked"),
    )
    core_ok = _lst(decision.get("core_ok"), acc.get("core_ok"), tech.get("core_ok"))
    return {
        "acc": acc,
        "roles": roles,
        "decision": decision,
        "core_blocked": core_blocked,
        "core_ok": core_ok,
        "engines": acc.get("engines") or tech.get("crawler_engines") or {},
    }


def _engine_search_statuses(engines: dict) -> list[tuple[str, str]]:
    """Return (token, status) for each engine's search-index crawler."""
    out = []
    for spec in (engines or {}).values():
        if not isinstance(spec, dict):
            continue
        token = _norm_token(spec.get("search_token") or spec.get("token") or "")
        status = (
            spec.get("search_status")
            or spec.get("search_live")
            or spec.get("status")
            or ""
        )
        status = str(status).strip().lower()
        if token:
            out.append((token, status))
    return out


def _status_is_blocked(status: str) -> bool:
    return status in {"blocked", "denied", "disallowed"}


def _status_is_allowed(status: str) -> bool:
    return status in {"allowed", "ok", "reachable"}


def _status_is_unverified(status: str) -> bool:
    return status in {"unverified", "untested", "unknown", "not_tested", ""}


def detect_access_gate(tech: dict | None) -> dict:
    """Derive access-gate flags from a technical report (or a test stub).

    Training-crawler blocks and unverified search crawlers do not trigger
    the gate. Meta-ExternalAgent is not treated as training-only.
    """
    tech = tech or {}
    explicit_google = tech.get("googlebot_blocked")
    explicit_all = tech.get("all_search_crawlers_blocked")
    explicit_core = tech.get("core_search_access_penalty")

    data = _blocked_name_lists(tech)
    core_blocked = [n for n in data["core_blocked"] if not _is_training(n)]
    core_ok = [n for n in data["core_ok"] if not _is_training(n)]

    googlebot_blocked = False
    if explicit_google is not None:
        googlebot_blocked = bool(explicit_google)
    else:
        googlebot_blocked = any(n.lower() == "googlebot" for n in core_blocked)
        for token, status in _engine_search_statuses(data["engines"]):
            if token.lower() == "googlebot" and _status_is_blocked(status):
                googlebot_blocked = True
            if token.lower() == "googlebot" and _status_is_allowed(status):
                googlebot_blocked = False
                break
        if any(n.lower() == "googlebot" for n in core_ok):
            googlebot_blocked = False

    # Verified search-index statuses (unverified tokens are ignored).
    verified_allowed = []
    verified_blocked = []
    for token, status in _engine_search_statuses(data["engines"]):
        if not _is_search_index(token):
            # Engine map tokens are search-index by construction; keep them.
            if _is_training(token):
                continue
        if _status_is_allowed(status):
            verified_allowed.append(token)
        elif _status_is_blocked(status):
            verified_blocked.append(token)

    for n in core_ok:
        if _is_search_index(n) or n.lower() == "googlebot":
            if n not in verified_allowed:
                verified_allowed.append(n)
    for n in core_blocked:
        if _is_search_index(n) or n.lower() == "googlebot":
            if n not in verified_allowed and n not in verified_blocked:
                verified_blocked.append(n)

    if explicit_all is not None:
        all_search_crawlers_blocked = bool(explicit_all)
    else:
        # Trigger only when at least one verified search-index crawler is
        # blocked, none are allowed, and every *verified* one is blocked.
        # Unverified crawlers never complete the "all blocked" set.
        all_search_crawlers_blocked = bool(verified_blocked) and not verified_allowed

        # If Googlebot itself is allowed, this cannot be "all" blocked.
        if any(n.lower() == "googlebot" for n in verified_allowed) or (
            explicit_google is False
        ):
            all_search_crawlers_blocked = False
        if not googlebot_blocked:
            # Without a verified Googlebot block, require that every known
            # major search-index token we *did* verify is blocked, and that
            # we actually verified a Googlebot status as blocked. Otherwise
            # "OAI-SearchBot only blocked" is a soft gate, not the hard cap.
            if not any(n.lower() == "googlebot" for n in verified_blocked):
                all_search_crawlers_blocked = False

    core_search_access_penalty = False
    if explicit_core is not None:
        core_search_access_penalty = bool(explicit_core)
    else:
        if data["decision"].get("apply"):
            core_search_access_penalty = True
        if core_blocked:
            core_search_access_penalty = True
        adjustments = []
        sa = tech.get("score_adjustments") or {}
        if isinstance(sa, dict):
            adjustments.extend(sa.get("adjustments") or [])
        adjustments.extend(tech.get("adjustments") or [])
        for adj in adjustments:
            if not isinstance(adj, dict):
                continue
            if adj.get("type") != "penalty":
                continue
            points = adj.get("points")
            reason = str(adj.get("reason") or "")
            accessish = any(
                key in reason.lower()
                for key in (
                    "爬虫",
                    "crawler",
                    "googlebot",
                    "访问",
                    "access",
                    "robots",
                    "searchbot",
                    "waf",
                )
            )
            if points in (-15, 15, "-15") and accessish:
                core_search_access_penalty = True
            elif points in (-15, 15, "-15") and not reason:
                # Current analyzer's only −15 is the core access penalty.
                core_search_access_penalty = True

    if googlebot_blocked or all_search_crawlers_blocked:
        cap = GATE_CAP_HARD
        kind = "hard"
    elif core_search_access_penalty:
        cap = GATE_CAP_SOFT
        kind = "soft"
    else:
        cap = None
        kind = None

    return {
        "googlebot_blocked": bool(googlebot_blocked),
        "all_search_crawlers_blocked": bool(all_search_crawlers_blocked),
        "core_search_access_penalty": bool(core_search_access_penalty),
        "cap": cap,
        "kind": kind,
        "applied": cap is not None,
    }


def is_sampled(tech: dict | None, content: dict | None) -> bool:
    """True when either component is a sampled-pages score."""
    tech = tech or {}
    content = content or {}
    scope = tech.get("scope") or {}
    coverage = tech.get("coverage") or {}
    for src in (scope, coverage, tech, content):
        if not isinstance(src, dict):
            continue
        flag = src.get("score_scope") or src.get("score_label") or ""
        if str(flag).lower() in {"sampled_pages", "sampled", "sample"}:
            return True
    for text in (
        content.get("fetch_disclosure") or "",
        content.get("scope_note") or "",
        content.get("overall_summary") or "",
        tech.get("overall_summary") or "",
        coverage.get("note_zh") or "",
        coverage.get("note_en") or "",
    ):
        low = str(text).lower()
        if "抽样页" in str(text) or "sampled-pages" in low or "sampled pages" in low:
            return True
    return False


def compute_combined(
    tech_overall,
    content_overall,
    gate: dict | None = None,
) -> dict:
    """Return the published combined score (or a missing-side placeholder).

    Inputs must be the *displayed* overalls. Do not recompute from base_score.
    """
    if tech_overall is None or content_overall is None or tech_overall == "" or content_overall == "":
        return {
            "overall_score": None,
            "grade": None,
            "raw_weighted": None,
            "raw_after_gate": None,
            "cap": None,
            "gate_applied": False,
            "weights": {"technical": TECH_WEIGHT, "content": CONTENT_WEIGHT},
            "missing": True,
        }
    raw = TECH_WEIGHT * float(tech_overall) + CONTENT_WEIGHT * float(content_overall)
    raw_weighted = raw
    cap = (gate or {}).get("cap")
    if cap is not None:
        raw = min(raw, float(cap))
    score = clamp(snap_half(raw), 0, 100)
    return {
        "overall_score": score,
        "grade": grade_for(score),
        "raw_weighted": raw_weighted,
        "raw_after_gate": raw,
        "cap": cap,
        "gate_applied": cap is not None and raw_weighted > cap,
        "weights": {"technical": TECH_WEIGHT, "content": CONTENT_WEIGHT},
        "missing": False,
    }


def score_from_reports(tech: dict | None, content: dict | None) -> dict:
    """Compute combined score + gate + sampled label from report dicts."""
    tech = tech or {}
    content = content or {}
    tech_score = tech.get("overall_score")
    content_score = content.get("overall_score")
    gate = detect_access_gate(tech) if tech else {
        "googlebot_blocked": False,
        "all_search_crawlers_blocked": False,
        "core_search_access_penalty": False,
        "cap": None,
        "kind": None,
        "applied": False,
    }
    combined = compute_combined(tech_score, content_score, gate)
    combined["gate"] = gate
    combined["sampled"] = is_sampled(tech, content)
    combined["tech_overall"] = tech_score
    combined["tech_grade"] = tech.get("grade")
    combined["content_overall"] = content_score
    combined["content_grade"] = content.get("grade")
    return combined


__all__ = [
    "TECH_WEIGHT",
    "CONTENT_WEIGHT",
    "GATE_CAP_HARD",
    "GATE_CAP_SOFT",
    "snap_half",
    "grade_for",
    "clamp",
    "format_score",
    "detect_access_gate",
    "is_sampled",
    "compute_combined",
    "score_from_reports",
]
