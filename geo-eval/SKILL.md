---
name: geo-eval
description: >-
  Use for website Generative Engine Optimization (GEO) readiness—not geography.
  Crawl, score, enrich, and deliver GEO Checker reports (English by default;
  Chinese when the user explicitly asks): the technical 10-dimension on-site
  readiness report (SEO content discoverability is a 15-point technical
  dimension) and/or a standalone Content GEO report (architecture, taxonomy,
  writing, authority evidence, and buyer-question coverage), and an optional
  combined HTML package with a remediation timeline, when the user asks about
  GEO, content, AI visibility, or whether a site can be understood and cited.
---
# Website Generative Engine Optimization (GEO) — GEO Checker

**GEO = Generative Engine Optimization.** Scope is **websites** only (not geography/maps).

Scripts crawl and score; **you always do deep enrichment** in the **report language** (English by default; Chinese when the user explicitly asked for a Chinese report). Brand: **GEO Checker** by **Beansmile**.

## Language (required)

- **Default = English.** Enrich and build every requested report in English.
- Switch to Chinese **only** when the user’s message explicitly asks for it (e.g. 中文报告 / Chinese report / 出中文). Do not ask for language unless they asked for both or the request is ambiguous.
- Never show scoring / rules / rubric version numbers in customer HTML or user chat.
- For Chinese runs, write Chinese into **primary** narrative fields (not only parallel `*_zh` keys). Builders still accept `*_zh` as fallbacks.

Build commands:

- EN tech: `python3 scripts/build_report.py <run> --lang en`
- ZH tech: `python3 scripts/build_report.py <run> --lang zh`
- Content: `python3 scripts/build_content_report.py <run> [--lang zh]`
- Combined: `python3 scripts/build_combined_report.py … [--lang zh]`

If Chinese is requested after an English technical HTML was already delivered: produce Chinese content + Chinese combined on the follow-up; prefer re-enriching technical narrative in Chinese then rebuilding tech HTML from the same `report.json`.

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

Refs in `/workspace/skills/geo-eval`: `rules.md`, `scoring.md` (technical 10-dim /100 including SEO /15), `seo_scoring.md`, `prompts.md`, `methodology.md`, `content_scoring.md`, `content_prompts.md`, `docs/content_geo_design_spec.md`, `README.grok.md`, `pipeline.md`. Do **not** quote scoring/rules/rubric version numbers in customer HTML or user chat.

## Status wording

Prefer “Website GEO (Generative Engine Optimization) readiness…”. Chinese:「网站生成式引擎优化评测」. Never「地理检查」.

## LLM / tools (Grok Bot native)

- Crawl + scoring: local Python under `scripts/` (stdlib).
- Enrichment: **you**, via `prompts.md` (technical, including `seo_discoverability` narrative) and `content_prompts.md` (content). Do **not** set `GEO_EVAL_LLM_API_KEY` or call external OpenAI APIs. Enrich in the report language.
- Technical reports: `python3 scripts/build_report.py <run> --lang en` (or `--lang zh`) → HTML only (`Technical_Report.html` / `技术报告.html`).
- Content reports: `python3 scripts/build_content_report.py <run> [--lang zh]` → HTML only (`Content_Report.html` / `内容报告.html`).
- Combined package: `python3 scripts/build_combined_report.py <tech_run> --content-run <content_run> [--lang zh]` → `Combined_Report.html` / `综合报告.html`.

## Fixed 4 steps (technical on-site readiness)

1. Ensure runtime installed (above). Detect report language from the user message (EN default).
2. `cd /workspace/skills/geo-eval && python3 scripts/run.py <URL> --site-type corporate --max-pages 16`
3. Enrich `report.json` in the report language per `prompts.md`. Also enrich `seo_discoverability.narr` / `callout` when present (rubric: `seo_scoring.md`). SEO is a **15-point technical dimension** inside `overall_score` /100 (bonuses stay in `score_adjustments`).
4. `python3 scripts/build_report.py runs/<domain>/<run> --lang en` (or `--lang zh`) → deliver `Technical_Report.html` / `技术报告.html` (SEO appears among the ten dimensions). Client deliverables are **HTML only** (pass `--also-md` only for internal drafts).

Then ask once whether to also produce Content GEO + combined (see below). One crawl powers all three reports when the user says yes. Build content/combined in the **same** report language.

## After technical HTML: ask once

Default UX: deliver **technical HTML first**, then ask whether to also produce **Content GEO + combined package**. Do **not** auto-run content without that ask. Never show scoring/rules/rubric version numbers in user-facing copy or HTML chrome.

## Content GEO + combined (same crawl, on yes)

When the user agrees (or explicitly asks for content / combined after a successful technical run):

1. **Reuse the tech crawl** — never re-fetch:
   ```bash
   cd /workspace/skills/geo-eval
   python3 scripts/content_eval.py --from-run runs/<domain>/<tech_run>
   ```
2. Build target procurement questions; run AI/search visibility checks (`live_ui` or labeled `web_retrieval_proxy`). Save `evidence/ai_checks.json` / optional `evidence/offsite.json` under that run if needed.
3. Enrich `content_report.json` in the **report language** per `content_prompts.md` (company-specific; disclose fetch limits; never invent engine quotes). For Chinese, put Chinese in primary fields.
4. Same turn (match language):
   ```bash
   python3 scripts/build_content_report.py runs/<domain>/<tech_run>           # EN
   # python3 scripts/build_content_report.py runs/<domain>/<tech_run> --lang zh
   python3 scripts/build_combined_report.py runs/<domain>/<tech_run> \
     --content-run runs/<domain>/<tech_run>
   # … --lang zh for Chinese combined
   ```
   If content artifacts are in a separate content run dir that still reused the tech crawl, pass that path as `--content-run`.

Standalone content-only (no prior tech run): `python3 scripts/content_eval.py <URL> --site-type corporate --max-pages 16` then `build_content_report.py`.

**Placement:** SEO discoverability lives in the **technical** report as a **15-point dimension** of the 100 (`seo_scoring.md`). Content GEO (`content_scoring.md`) covers IA, taxonomy, writing, authority evidence, and query coverage only — no SEO dim there.

Rules: Content GEO score is **separate** from the technical 100; never merge into one total. Combined HTML keeps **two** headline scores + an effort-based remediation timeline (checklist + day-scale schedule). GEO ≠ geography. Brand GEO Checker / Beansmile. If homepage body cannot be obtained, mark unevaluable or provisional.

## Boundaries

- Technical 10-dim score = readiness of on-site signals to be understood / trusted / cited by AI—not rankings or traffic. SEO discoverability is one 15-pt dim inside that 100; bonuses/penalties are listed separately.
- Technical SEO dimension = content discoverability (titles, intent pages, thin/duplicate content, internal paths, sitemap/robots as discovery aids). Not a full rank-tracking SEO audit.
- Content score = architecture, writing, evidence system, and query coverage / AI visibility.
- Evidence required; drop false positives.
- Chrome: GEO Checker · Beansmile; no Report ID; no sign-off blocks; no scoring/rules/rubric version strings in customer HTML or user chat.
