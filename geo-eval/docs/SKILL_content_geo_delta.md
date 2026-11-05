# Draft SKILL.md delta — Content GEO + technical SEO chapter (for parent UpdateSkill)

Replace the Content GEO section and clarify technical steps. Do **not** change the technical 9-dimension formula.

## Fixed 4 steps (technical on-site readiness)

1. Ensure runtime installed (`/workspace/skills/geo-eval`).
2. `cd /workspace/skills/geo-eval && python3 scripts/run.py <URL> --site-type corporate --max-pages 16`
3. Enrich `report.json` in English per `prompts.md`. Also enrich `seo_discoverability.narr` / `callout` when present (rubric: `seo_scoring.md`). The SEO block is **separate** from the nine-dimension 100 — never merge into `overall_score`.
4. `python3 scripts/build_report.py runs/<domain>/<run> --lang en` → deliver `report.md` + `report.html` (includes SEO content discoverability chapter).

## Content GEO evaluation (standalone report)

When the user asks for **content** GEO evaluation, information architecture advice, writing or authority-content recommendations, buyer-question coverage, or a content report separate from the technical score:

1. Ensure runtime installed.
2. Run:
   ```bash
   cd /workspace/skills/geo-eval
   python3 scripts/content_eval.py <URL> --site-type corporate --max-pages 16
   ```
   Or reuse a crawl: `python3 scripts/content_eval.py --from-run runs/<domain>/<run>`.
3. Build target procurement questions. Run AI/search visibility checks (`live_ui` when available; otherwise labeled `web_retrieval_proxy`). Save `evidence/ai_checks.json` and optional `evidence/offsite.json`, then re-run analyze with those files if needed.
4. **Agent enrichment (required):** rewrite `content_report.json` in English per `content_prompts.md` (company-specific; disclose fetch limits; never invent engine quotes). Intro explains what Content GEO evaluates — do **not** open with a “this is not the nine-dimension score” disclaimer.
5. `python3 scripts/build_content_report.py runs/<domain>/<run>` → deliver `report/content_report.md` + `content_report.html`.

### Important placement note

**SEO content discoverability** (titles/H1/meta intent match, thin/duplicate risk, internal crawl paths, sitemap/robots as discovery aids) lives in the **technical** report (`seo_scoring.md`, score /25, not added to the 100). Content GEO (`content_scoring.md` v1.1) covers IA, taxonomy, writing, authority evidence, and target query coverage only.

Rules: Content GEO score is separate from technical 100; do not merge. GEO ≠ geography. Brand GEO Checker / Beansmile. If homepage body cannot be obtained, mark unevaluable or provisional — do not fake precision.

Refs: `scoring.md` (9-dim unchanged), `seo_scoring.md`, `content_scoring.md`, `content_prompts.md`, `docs/content_geo_design_spec.md`.
