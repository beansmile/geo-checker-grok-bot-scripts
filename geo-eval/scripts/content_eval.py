#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Content GEO evaluation entrypoint (standalone from technical 10-dim pipeline; prefer --from-run to reuse the tech crawl).

Usage:
  python3 scripts/content_eval.py <URL> [--max-pages 16] [--site-type corporate]
  python3 scripts/content_eval.py --from-run runs/<domain>/<run>
  python3 scripts/content_eval.py --from-run <run> --ai-checks evidence/ai_checks.json --offsite evidence/offsite.json

Flow:
  1) Reuse an existing technical crawl OR run fetch-only crawl
  2) content_extract.py → content_extract.json
  3) content_analyze.py → content.engine.json
  4) Copy skeleton → content_report.json (Agent enriches per content_prompts.md)
  5) Optionally build_content_report.py if content_report.json already enriched

Does not modify scoring.md or technical report.engine.json scoring formula.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse


def skill_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def registrable_domain(url: str) -> str:
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def next_run_id(domain: str, prefix: str = "content") -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    domain_dir = os.path.join(skill_root(), "runs", domain)
    for i in range(1, 100):
        candidate = f"{date}_{prefix}{i:02d}"
        if not os.path.isdir(os.path.join(domain_dir, candidate)):
            return candidate
    return f"{date}_{prefix}{int(datetime.now().timestamp())}"


def run_py(script: str, args: list[str]) -> int:
    cmd = [sys.executable, os.path.join(skill_root(), "scripts", script), *args]
    print("→", " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode


def skeleton_report(engine: dict) -> dict:
    return {
        "schema": "content_geo.report.v1",
        "brand": "GEO Checker",
        "attribution": "Beansmile · GEO Checker",
        "title": "Content GEO Evaluation Report",
        "domain": engine.get("domain"),
        "site_url": engine.get("site_url"),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rubric_version": "content_scoring.md v1.1",
        "overall_score": engine.get("overall_score"),
        "grade": engine.get("grade"),
        "confidence": engine.get("confidence"),
        "fetch_mode": engine.get("fetch_mode"),
        "unevaluable": engine.get("unevaluable"),
        "fetch_disclosure": engine.get("note", ""),
        "overall_summary": engine.get("overall_summary") or "",
        "closing": engine.get("closing") or "",
        "dimensions": engine.get("dimensions") or [],
        "strengths": engine.get("strengths") or [],
        "findings": engine.get("findings") or [],
        "priority_actions": engine.get("priority_actions") or [],
        "recommended_ia_tree": [],
        "page_briefs": [],
        "target_questions": [],
        "ai_checks": engine.get("ai_checks") or [],
        "offsite_evidence": engine.get("offsite_evidence") or [],
        "sample_urls": engine.get("sample_urls") or [],
        "pages_analyzed": engine.get("pages_analyzed"),
        "page_type_counts": engine.get("page_type_counts") or {},
        "scope_note": (
            "Content GEO evaluates whether site content can be understood, trusted, and cited "
            "(architecture, page types/gaps, writing, authority evidence, buyer-question coverage). "
            "It does not measure rankings or traffic. AI mention checks are labeled by method "
            "(live_ui / web_retrieval_proxy / agent_tool). SEO discoverability is covered in the "
            "technical GEO readiness report."
        ),
        "enrichment_status": "pending_agent",
    }


def main():
    ap = argparse.ArgumentParser(description="Content GEO evaluation entrypoint")
    ap.add_argument("url", nargs="?", help="Target URL (omit with --from-run)")
    ap.add_argument("--from-run", dest="from_run", help="Reuse existing run directory")
    ap.add_argument("--max-pages", type=int, default=16)
    ap.add_argument("--site-type", default="corporate")
    ap.add_argument("--ai-checks", help="JSON file with AI mention check records")
    ap.add_argument("--offsite", help="JSON file with off-site evidence items")
    ap.add_argument("--build", action="store_true", help="Also run build_content_report.py")
    ap.add_argument("--skip-fetch", action="store_true", help="Do not call technical run.py")
    args = ap.parse_args()

    root = skill_root()
    if args.from_run:
        run_dir = args.from_run
        if not os.path.isabs(run_dir):
            run_dir = os.path.join(root, run_dir) if not run_dir.startswith("runs/") else os.path.join(root, run_dir)
            if not os.path.isdir(run_dir):
                run_dir = os.path.join(root, args.from_run)
        if not os.path.isdir(run_dir):
            # try relative to cwd
            run_dir = os.path.abspath(args.from_run)
        if not os.path.isdir(run_dir):
            raise SystemExit(f"Run dir not found: {args.from_run}")
    else:
        if not args.url:
            raise SystemExit("Provide URL or --from-run")
        url = args.url
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        domain = registrable_domain(url)
        run_id = next_run_id(domain)
        run_dir = os.path.join(root, "runs", domain, run_id)
        os.makedirs(os.path.join(run_dir, "evidence", "pages"), exist_ok=True)

        if not args.skip_fetch:
            # Attempt technical fetch-only crawl into this run by temporarily using run.py
            # run.py creates its own run id — so we call it then copy, OR document reuse.
            print("[1] Attempting technical fetch-only crawl (may fail on WAF/region blocks)…")
            rc = run_py("run.py", [url, "--site-type", args.site_type, "--max-pages", str(args.max_pages), "--fetch-only"])
            # Find newest run for domain and copy evidence if our run is empty
            domain_runs = os.path.join(root, "runs", domain)
            newest = None
            if os.path.isdir(domain_runs):
                cands = sorted(
                    [d for d in os.listdir(domain_runs) if os.path.isdir(os.path.join(domain_runs, d))],
                    reverse=True,
                )
                for c in cands:
                    if c == run_id:
                        continue
                    newest = os.path.join(domain_runs, c)
                    break
            pages = os.path.join(run_dir, "evidence", "pages")
            if newest and (not os.listdir(pages)):
                print(f"    Copying evidence from {newest} → {run_dir}")
                for name in ("evidence", "site.json", "scope.json"):
                    src = os.path.join(newest, name)
                    dst = os.path.join(run_dir, name)
                    if os.path.isdir(src):
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                    elif os.path.isfile(src):
                        shutil.copy2(src, dst)
            # Write minimal site.json if still missing
            if not os.path.isfile(os.path.join(run_dir, "site.json")):
                site = {
                    "url": url if url.endswith("/") else url.rsplit("/", 1)[0] + "/",
                    "domain": urlparse(url).hostname or "",
                    "registrable_domain": domain,
                    "site_type": {"type": args.site_type, "source": "manual"},
                    "pages_sampled": [],
                    "content_eval_only": True,
                }
                with open(os.path.join(run_dir, "site.json"), "w", encoding="utf-8") as f:
                    json.dump(site, f, ensure_ascii=False, indent=2)
            print(f"    fetch-only rc={rc}; continuing with whatever evidence is in {run_dir}")

    # Optional AI / offsite args relative to run_dir
    ai_path = args.ai_checks
    off_path = args.offsite
    if ai_path and not os.path.isabs(ai_path) and not os.path.isfile(ai_path):
        cand = os.path.join(run_dir, ai_path)
        if os.path.isfile(cand):
            ai_path = cand
    if off_path and not os.path.isabs(off_path) and not os.path.isfile(off_path):
        cand = os.path.join(run_dir, off_path)
        if os.path.isfile(cand):
            off_path = cand

    print("[2] content_extract")
    run_py("content_extract.py", [run_dir])
    print("[3] content_analyze")
    analyze_args = [run_dir]
    if ai_path:
        analyze_args += ["--ai-checks", ai_path]
    if off_path:
        analyze_args += ["--offsite", off_path]
    run_py("content_analyze.py", analyze_args)

    engine = json.load(open(os.path.join(run_dir, "content.engine.json"), encoding="utf-8"))
    report_path = os.path.join(run_dir, "content_report.json")
    if not os.path.isfile(report_path):
        sk = skeleton_report(engine)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(sk, f, ensure_ascii=False, indent=2)
        print(f"[4] Wrote skeleton {report_path} — Agent must enrich (content_prompts.md)")
    else:
        print(f"[4] Keeping existing content_report.json")

    if args.build:
        print("[5] build_content_report")
        run_py("build_content_report.py", [run_dir])

    print(f"\nDone. Run dir: {run_dir}")
    print("Next: enrich content_report.json in English, then:")
    print(f"  python3 scripts/build_content_report.py {run_dir}")


if __name__ == "__main__":
    main()
