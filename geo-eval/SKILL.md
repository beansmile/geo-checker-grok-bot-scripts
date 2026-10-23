---
name: geo-eval
description: Evaluate a website’s GEO (Generative Engine Optimization) readiness — crawl, 9-dimension rules scoring, Agent deep interpretation, output English md+html client report. Use when the user asks to evaluate/diagnose a site’s GEO, AI visibility, or whether content can be understood and cited by AI.
---

# Website GEO deep evaluation (GEO Checker)

Scripts do execution; the Agent does interpretation and drafting. Both are fixed pipeline steps: scripts produce rule hits and 9-dimension scores (`report.engine.json`); Agent enrichment produces client-readable finding rewrites + fix code + dimension/overall narratives (overwrite `report.json`); then md+html. **Agent enrichment is required every run — not optional.**

Runtime root on the Grok Bot box: `/workspace/skills/geo-eval`. See `README.grok.md`.

**Defaults for GEO Checker:** English reports; brand **GEO Checker**; attribution **Beansmile · GEO Checker**. Do not rely on an external OpenAI API key.

## Pipeline (fixed 4 steps — do not skip step 3)

1. Crawl + rules engine:
   ```bash
   cd /workspace/skills/geo-eval
   python3 scripts/run.py <URL> --site-type corporate --max-pages 16
   ```
   - `--site-type`: corporate / personal / blog / ecommerce / saas (omit if unsure).
   - Writes `runs/<domain>/<date>_runNN/report.engine.json` (hits + evidence + scores, no narrative) and a fallback `report.json`.
   - After quota sampling, FAQ/About/Contact/Privacy are force-added; missing pages go into `scope.scope_warnings`.
   - Same-day re-runs increment (`_run01` → `_run02` …) and do not overwrite prior evidence.

2. (Optional, diagnostics only) Read `report.engine.json`: `overall_score`, `grade`, `dimensions`, `findings[]`, `dimension_details[]`, `scope`, `strengths[]`.

3. **Agent deep interpretation (required)**:
   ```bash
   python3 scripts/enrich.py runs/<domain>/<run>
   ```
   - **Grok Bot path (default):** do **not** set `GEO_EVAL_LLM_API_KEY`. enrich.py copies engine → `report.json` (`llm_enabled=false`). **You (the Agent)** then rewrite `report.json` using the English prompts in `prompts.md`: plain-English findings with real brand/domain/email/URL, paste-ready fix code and evidence quotes, plus `dimension_details`, `overall_summary`, and `closing`. **Do not ship the engine’s raw fallback copy as the client report.**
   - Optional legacy only: if `GEO_EVAL_LLM_API_KEY` is set, enrich.py may call an OpenAI-compatible API. GEO Checker does not use this.

4. Build report (English by default):
   ```bash
   python3 scripts/build_report.py runs/<domain>/<run>
   ```
   - Writes `runs/<domain>/<run>/report/report.md` + `report.html` (30+ page deck). Use `--lang zh` only if the user explicitly asks for Chinese.

## Scoring snapshot

9 dimensions / 100 points: schema 15 · entity 15 · ogp 5 · richness 15 · kg 10 · absorption 15 · trust 15 · on_page 5 · quality 5.

**v1.1 highlights** (see `scoring.md`):
- OGP scored on homepage only; inner-page tags are advisory.
- richness 5/5/5 (FAQ / articles / body); `llms.txt` is a +3 adjustment only.
- kg totals 10; absorption = Citability × 0.75 (`scripts/citability.py`).
- trust needs real About/Contact content; template legal pages do not score.
- `scored: false` findings show as Advisory and do not affect the severity strip.

Trust Ceiling: S1 consistency conflicts → trust≤50%, entity≤30%, total≤70; lorem → total≤75. A single email domain ≠ site domain is a warning, not scored.

Grades: 90–100 A+｜80–89 A｜70–79 B｜60–69 C｜0–59 D.

## Reference files

- Rules → `rules.md`
- Agent prompts (English) → `prompts.md`
- Methodology → `methodology.md`
- Scoring detail → `scoring.md`
- Output schema → `output_schema.md`
- Grok Bot notes → `README.grok.md`

## Boundaries

- Score = readiness to be understood / trusted / cited by AI — not ranking or traffic promises.
- Every conclusion needs evidence; drop false positives.
- If a crawl returns 0 sitemap URLs, re-run once.
- Deliverable is Agent+script output branded GEO Checker (Beansmile). No client sign-off / file-number / “pending review” UI.
