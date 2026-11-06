# GEO Checker (Grok Bot) — runtime notes

**GEO = Generative Engine Optimization** (websites / generative-engine readiness). Not geography or maps.

Canonical source: https://github.com/beansmile/geo-checker-grok-bot-scripts (MIT · Beansmile)

Install on the Bot computer:

```bash
git clone --depth 1 https://github.com/beansmile/geo-checker-grok-bot-scripts.git /workspace/skills/geo-checker-grok-bot-scripts
ln -sfn /workspace/skills/geo-checker-grok-bot-scripts/geo-eval /workspace/skills/geo-eval
```

## Language (required)

- **Default = English.** Build and enrich all reports in English unless the user’s message explicitly asks for Chinese (e.g. 中文报告 / Chinese report / 出中文).
- Do **not** ask for language preference unless the user asked for both languages or the request is ambiguous.
- Never show scoring / rules / rubric **version numbers** in HTML chrome or user-facing prompts (prior product rule).
- Enrichment prose language = report language. For Chinese runs, write Chinese into **primary** fields (`overall_summary`, dim `narr`/`callout`, findings, …); `*_zh` fields remain optional fallbacks for the builders.

**HARD RULE:** Never deliver Chinese HTML by only flipping `--lang zh` on English enrichment. Re-enrich every client-facing narrative field into Chinese first, then build. Chrome-only ZH is a bug.

Build flags:

| Report | English (default) | Chinese |
|---|---|---|
| Technical | `build_report.py <run> --lang en` | `build_report.py <run> --lang zh` |
| Content | `build_content_report.py <run>` | `build_content_report.py <run> --lang zh` |
| Combined | `build_combined_report.py …` | `build_combined_report.py … --lang zh` |

Outputs: `Technical_Report.html` / `技术报告.html`, `Content_Report.html` / `内容报告.html`, `Combined_Report.html` / `综合报告.html`.

If the user asks for Chinese **after** an English technical report was already delivered: on the content ask / follow-up, produce Chinese content + Chinese combined. Prefer rewriting enrichment to Chinese then rebuilding technical HTML from the same `report.json`; chrome-only language flip leaves English narrative — re-enrich in Chinese when delivering a Chinese tech report.

Customer-facing reports show **GEO Checker** and attribution **Beansmile · GEO Checker**. Do not show Report ID / file numbers, sign-off blocks, or “pending review” copy.

## Product UX (required)

1. Run the **technical** crawl + enrich + `build_report.py` (in the report language) → deliver **technical HTML** first.
2. Then **ask once** whether the user also wants Content GEO + the combined package.
3. Do **not** auto-run content without that ask.

## Same-crawl Content GEO + combined (on yes)

When the user says yes, **reuse the technical run’s crawl** — never re-fetch the site for content when a successful technical run exists:

```bash
cd /workspace/skills/geo-eval
# Reuse pages/evidence from the technical run (no second site crawl)
python3 scripts/content_eval.py --from-run runs/<domain>/<tech_run>

# Agent enriches content_report.json in the report language (content_prompts.md)
python3 scripts/build_content_report.py runs/<domain>/<tech_run>            # EN
# python3 scripts/build_content_report.py runs/<domain>/<tech_run> --lang zh  # ZH

# Same turn: combined HTML from the same tech run + that content output
python3 scripts/build_combined_report.py runs/<domain>/<tech_run> \
  --content-run runs/<domain>/<tech_run>
# python3 scripts/build_combined_report.py … --content-run … --lang zh
```

If content artifacts land in a separate content run directory **while still reusing the tech crawl**, pass that path as `--content-run`. One crawl powers technical + content + combined.

Standalone content-only (no prior tech run) remains available:

```bash
python3 scripts/content_eval.py <URL> --site-type corporate --max-pages 16
python3 scripts/build_content_report.py runs/<domain>/<run>
```

Rubric docs (internal): `content_scoring.md`, `docs/content_geo_design_spec.md`. SEO content discoverability is a **15-point dimension** inside the technical report /100 (`seo_scoring.md`), not part of the Content GEO 100.

## Client deliverables = HTML only

`build_report.py` and `build_content_report.py` write **HTML** by default. Pass `--also-md` only for internal drafts. Do not hand customers `.md` report files.

## Combined package

```bash
cd /workspace/skills/geo-eval
python3 scripts/build_combined_report.py runs/<domain>/<tech_run> \
  --content-run runs/<domain>/<content_or_same_run>
```

Emits `report/Combined_Report.html` (ZH: `综合报告.html`). Keeps technical /100 (incl. SEO dim) and Content GEO /100 separate; includes an **effort-based** remediation timeline (checklist + schedule; HTTPS/crawl ≤1 day — not a padded W0–W16 calendar).

## Scoring (internal; do not quote versions to customers)

- Technical: **10 dimensions /100** (SEO discoverability = 15).
- Content GEO: separate /100 (IA20 · TAX15 · WRITE20 · AUTH20 · QUERY25).
- GEO = Generative Engine Optimization only — never geography / local-pack framing.
- Client deliverables: **HTML only**. Keep version ids in JSON / `scoring.md` for engineers; never in customer HTML or chat copy.
