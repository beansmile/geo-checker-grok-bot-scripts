# Draft SKILL.md delta — Content GEO (for parent UpdateSkill)

Append to geo-eval skill (do not remove technical 4-step pipeline):

## Content GEO evaluation (standalone report)

When the user asks for **content** GEO/SEO evaluation, content architecture advice, buyer-question coverage, or a content report separate from the technical score:

1. Ensure runtime installed (`/workspace/skills/geo-eval`).
2. Run:
   ```bash
   cd /workspace/skills/geo-eval
   python3 scripts/content_eval.py <URL> --site-type corporate --max-pages 16
   ```
   Or reuse a crawl: `python3 scripts/content_eval.py --from-run runs/<domain>/<run>`.
3. Build target procurement questions for the industry/company. Run AI/search visibility checks (`live_ui` when available; otherwise labeled `web_retrieval_proxy`). Save `evidence/ai_checks.json` and optional `evidence/offsite.json`, then re-run `content_analyze.py` with those files.
4. **Agent enrichment (required):** rewrite `content_report.json` in English per `content_prompts.md` (company-specific; disclose fetch limits; never invent engine quotes).
5. `python3 scripts/build_content_report.py runs/<domain>/<run>` → deliver `report/content_report.md` + `content_report.html`.

Rules: Content GEO score is separate from technical 100; do not merge. GEO ≠ geography. Brand GEO Checker / Beansmile. If homepage body cannot be obtained, mark unevaluable or provisional — do not fake precision.

Refs: `content_scoring.md`, `content_prompts.md`, `docs/content_geo_design_spec.md`.
