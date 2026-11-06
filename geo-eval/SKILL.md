---
name: geo-eval
description: >-
  Use for website Generative Engine Optimization (GEO) readiness—not geography.
  Crawl, score, enrich, and deliver English GEO Checker reports: the technical
  10-dimension on-site readiness report (SEO content discoverability is a
  15-point technical dimension) and/or a standalone Content GEO report (architecture,
  taxonomy, writing, authority evidence, and buyer-question coverage), and an
  optional combined HTML package with a remediation timeline, when the
  user asks about GEO, content, AI visibility, or whether a site can be
  understood and cited.
---
# Website Generative Engine Optimization (GEO) — GEO Checker

**GEO = Generative Engine Optimization.** Scope is **websites** only (not geography/maps).

Scripts crawl and score; **you always do deep enrichment** in English. Brand: **GEO Checker** by **Beansmile**.

## Runtime install (required)

Canonical scripts repo (MIT):
`https://github.com/beansmile/geo-checker-grok-bot-scripts`

Expected path: `/workspace/skills/geo-eval`

If that directory is missing or incomplete, install once:

```bash
mkdir -p /workspace/skills
cd /workspace/skills
rm -rf geo-checker-grok-bot-scripts geo-eval
git clone --depth 1 https://github.com/beansmile/geo-checker-grok-bot-scripts.git geo-checker-grok-bot-scripts
ln -sfn /workspace/skills/geo-checker-grok-bot-scripts/geo-eval /workspace/skills/geo-eval
```

To update later **only when origin has the commits**: `git -C /workspace/skills/geo-checker-grok-bot-scripts pull --ff-only` then keep the symlink. Prefer the existing symlink when local is ahead.

Refs in `/workspace/skills/geo-eval`: `rules.md`, `scoring.md` (v1.3, technical 10-dim /100 including SEO /15; weights same as v1.2), `seo_scoring.md` (SEO dim rubric; raw heuristic /25 → dim /15), `prompts.md`, `methodology.md`, `content_scoring.md`, `content_prompts.md`, `docs/content_geo_design_spec.md`, `README.grok.md`.

## Status wording

Prefer “Website GEO (Generative Engine Optimization) readiness…”. Chinese:「网站生成式引擎优化评测」. Never「地理检查」.

## LLM / tools (Grok Bot native)

- Crawl + scoring: local Python under `scripts/` (stdlib).
- Enrichment: **you**, via `prompts.md` (technical, including `seo_discoverability` narrative) and `content_prompts.md` (content). Do **not** set `GEO_EVAL_LLM_API_KEY` or call external OpenAI APIs.
- Technical reports: `python3 scripts/build_report.py <run> --lang en` → HTML only.
- Content reports: `python3 scripts/build_content_report.py <run>` → HTML only.
- Combined package: `python3 scripts/build_combined_report.py <tech_run> --content-run <content_run> [--lang zh]`.

## Fixed 4 steps (technical on-site readiness)

1. Ensure runtime installed (above).
2. `cd /workspace/skills/geo-eval && python3 scripts/run.py <URL> --site-type corporate --max-pages 16`
3. Enrich `report.json` in English per `prompts.md`. Also enrich `seo_discoverability.narr` / `callout` when present (rubric: `seo_scoring.md`). SEO is a **15-point technical dimension** inside `overall_score` /100 (bonuses stay in `score_adjustments`).
4. `python3 scripts/build_report.py runs/<domain>/<run> --lang en` → deliver `report.html` (SEO appears among the ten dimensions). Client deliverables are **HTML only** (pass `--also-md` only for internal drafts).

## Content GEO evaluation (standalone report)

When the user asks for **content** GEO evaluation, information architecture advice, writing or authority-content recommendations, buyer-question coverage, or a content report separate from the technical score:

1. Ensure runtime installed (above).
2. Run:
   ```bash
   cd /workspace/skills/geo-eval
   python3 scripts/content_eval.py <URL> --site-type corporate --max-pages 16
   ```
   Or reuse a crawl: `python3 scripts/content_eval.py --from-run runs/<domain>/<run>`.
3. Build target procurement questions for the industry/company. Run AI/search visibility checks (`live_ui` when available; otherwise labeled `web_retrieval_proxy`). Save `evidence/ai_checks.json` and optional `evidence/offsite.json`, then re-run analyze with those files if needed.
4. **Agent enrichment (required):** rewrite `content_report.json` in English per `content_prompts.md` (company-specific; disclose fetch limits; never invent engine quotes). The intro explains what Content GEO evaluates — do **not** open with a “this is not the technical 10-dimension score” disclaimer.
5. `python3 scripts/build_content_report.py runs/<domain>/<run>` → deliver `report/content_report.html` (HTML only).

**Placement:** SEO content discoverability (titles/H1/meta, thin/duplicate risk, internal crawl paths, sitemap/robots as discovery aids) lives in the **technical** report as a **15-point dimension** of the 100 (`seo_scoring.md`). Content GEO (`content_scoring.md`) covers information architecture, taxonomy/gaps, writing, authority evidence, and target query coverage only — no SEO dim there.

Rules: the Content GEO score is **separate** from the technical 100; never merge them into one total. GEO ≠ geography. Brand GEO Checker / Beansmile. If homepage body cannot be obtained, mark unevaluable or provisional — do not fake precision.


## Combined package (technical + content + timeline)

When the user wants one executive HTML that surfaces both tracks and a remediation schedule:

```bash
cd /workspace/skills/geo-eval
python3 scripts/build_combined_report.py runs/<domain>/<tech_run> \
  --content-run runs/<domain>/<content_run>
# Chinese:
python3 scripts/build_combined_report.py runs/<domain>/<tech_run> \
  --content-run runs/<domain>/<content_run> --lang zh
```

Output: `report/combined_report.html` (or `combined_report.zh.html`). The combined report keeps **two** headline scores — technical /100 (incl. SEO dim) and Content GEO /100 — **separate**; never invent one merged total. Intro explains the package purpose; do **not** open with a “this is not the technical 10-dimension score” disclaimer. Ends with a phased remediation timeline (W0–W16).

## Boundaries

- Technical 10-dim score = readiness of on-site signals to be understood / trusted / cited by AI—not rankings or traffic. SEO discoverability is one 15-pt dim inside that 100; bonuses/penalties are listed separately.
- Technical SEO dimension = content discoverability (titles, intent pages, thin/duplicate content, internal paths, sitemap/robots as discovery aids). Not a full rank-tracking SEO audit.
- Content score = architecture, writing, evidence system, and query coverage / AI visibility.
- Evidence required; drop false positives.
- Chrome: GEO Checker · Beansmile; no Report ID; no sign-off blocks.
