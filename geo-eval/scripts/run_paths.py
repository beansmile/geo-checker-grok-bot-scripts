#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolve and constrain GEO Checker run directories.

CLI entry points must keep run paths under geo-eval/runs/ (or an explicit
data root). Library functions used by tests may still accept any directory.
"""

from __future__ import annotations

import os

_DOTDOT = ".."


def skill_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def runs_root(root: str | None = None) -> str:
    override = os.environ.get("GEO_EVAL_RUNS_ROOT")
    if override:
        return os.path.abspath(override)
    return os.path.join(root or skill_root(), "runs")


def is_under(path: str, root: str) -> bool:
    try:
        real_path = os.path.realpath(path)
        real_root = os.path.realpath(root)
        common = os.path.commonpath([real_path, real_root])
        return common == real_root
    except (ValueError, OSError):
        return False


def _rejects_dotdot(raw: str) -> bool:
    parts = raw.replace("\\", "/").split("/")
    return _DOTDOT in parts


def resolve_run_dir(path: str, *, root: str | None = None, require: bool = True) -> str:
    """Resolve a run directory and require it to stay under runs/.

    Accepts (in order):
      - absolute paths already under the runs root
      - paths relative to the skill root (e.g. runs/example.com/2026-01-01_run01)
      - paths relative to the runs root (e.g. example.com/2026-01-01_run01)
      - cwd-relative paths that still resolve under the runs root

    Rejects ``..`` segments and symlink escapes out of the runs root.
    """
    raw = (path or "").strip()
    if not raw:
        raise SystemExit("Run dir is empty")
    if _rejects_dotdot(raw):
        raise SystemExit(f"Run dir must not contain '..': {path}")

    root = root or skill_root()
    data_root = runs_root(root)
    candidates = []
    if os.path.isabs(raw):
        candidates.append(raw)
    else:
        candidates.append(os.path.join(root, raw))
        if not raw.startswith("runs/") and not raw.startswith("runs" + os.sep):
            candidates.append(os.path.join(data_root, raw))
        candidates.append(os.path.abspath(raw))

    seen = set()
    last_existing = None
    for cand in candidates:
        cand = os.path.abspath(cand)
        if cand in seen:
            continue
        seen.add(cand)
        if os.path.isdir(cand):
            last_existing = cand
            if is_under(cand, data_root):
                return os.path.realpath(cand)
        elif not require and is_under(cand, data_root):
            # Allow a not-yet-created path only if its parent chain stays under runs/
            parent = os.path.dirname(cand)
            if os.path.isdir(parent) and is_under(parent, data_root):
                return cand

    if last_existing and not is_under(last_existing, data_root):
        raise SystemExit(
            f"Run dir must stay under {data_root} (rejected {path})"
        )
    raise SystemExit(f"Run dir not found under {data_root}: {path}")


def site_host(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url or "").hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def same_site_identity(site: dict, url: str) -> bool:
    """True if a site.json document describes the same site as url."""
    from public_suffix import registrable_domain

    site_url = (site or {}).get("url") or (site or {}).get("site_url") or ""
    site_host_raw = (site or {}).get("domain") or ""
    target_reg = registrable_domain(url)
    target_host = site_host(url)
    if not target_reg and not target_host:
        return False
    cand_url = site_url or (
        ("https://" + site_host_raw) if site_host_raw else ""
    )
    if not cand_url:
        return False
    if registrable_domain(cand_url) != target_reg:
        return False
    cand_host = site_host(cand_url) or site_host("https://" + site_host_raw)
    return cand_host == target_host


def find_matching_runs(url: str, *, root: str | None = None, exclude=None) -> list[str]:
    """List run dirs under the registrable-domain folder whose site.json matches url.

    Newest-looking names first (lexicographic reverse, which works for
    YYYY-MM-DD_runNN). Never returns a run for a different host that merely
    shares the same parent folder.
    """
    import json
    from public_suffix import registrable_domain

    root = root or skill_root()
    exclude = {os.path.realpath(x) for x in (exclude or []) if x}
    domain = registrable_domain(url)
    if not domain:
        return []
    folder = os.path.join(runs_root(root), domain)
    if not os.path.isdir(folder):
        return []
    names = sorted(
        (n for n in os.listdir(folder) if os.path.isdir(os.path.join(folder, n))),
        reverse=True,
    )
    out = []
    for name in names:
        path = os.path.join(folder, name)
        real = os.path.realpath(path)
        if real in exclude:
            continue
        site_path = os.path.join(path, "site.json")
        if not os.path.isfile(site_path):
            continue
        try:
            with open(site_path, encoding="utf-8") as f:
                site = json.load(f)
        except (OSError, ValueError):
            continue
        if same_site_identity(site, url):
            out.append(real)
    return out
