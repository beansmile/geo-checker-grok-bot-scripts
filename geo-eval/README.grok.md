# GEO Checker (Grok Bot) — runtime notes

**GEO = Generative Engine Optimization** (websites / generative-engine readiness). Not geography or maps.

Canonical source: https://github.com/beansmile/geo-checker-grok-bot-scripts (MIT · Beansmile)

Install on the Bot computer:

```bash
git clone --depth 1 https://github.com/beansmile/geo-checker-grok-bot-scripts.git /workspace/skills/geo-checker-grok-bot-scripts
ln -sfn /workspace/skills/geo-checker-grok-bot-scripts/geo-eval /workspace/skills/geo-eval
```

Reports are **English by default** (`build_report.py --lang en`). Enrichment is done by the Bot (no `GEO_EVAL_LLM_API_KEY` on the Grok Bot path).

Customer-facing reports show **GEO Checker** and attribution **Beansmile · GEO Checker**. Do not show Report ID / file numbers, sign-off blocks, or “pending review” copy.


## Content GEO (separate report)

Content evaluation (architecture, writing, authority evidence, buyer-question / AI visibility checks) is **standalone** from the technical 10-dimension score.
SEO content discoverability is a **15-point dimension** inside the technical report /100 (`seo_scoring.md` / scoring v1.3), not part of the Content GEO 100.

```bash
cd /workspace/skills/geo-eval
python3 scripts/content_eval.py <URL> --site-type corporate --max-pages 16
# Agent enriches runs/.../content_report.json using content_prompts.md
python3 scripts/build_content_report.py runs/<domain>/<run>
```

Rubric: `content_scoring.md`. Design: `docs/content_geo_design_spec.md`.

## Client deliverables = HTML only

`build_report.py` and `build_content_report.py` write **HTML** by default. Pass `--also-md` only for internal drafts. Do not hand customers `.md` report files.

## Combined package

```bash
cd /workspace/skills/geo-eval
python3 scripts/build_combined_report.py runs/<domain>/<tech_run> \
  --content-run runs/<domain>/<content_run>
python3 scripts/build_combined_report.py runs/<domain>/<tech_run> \
  --content-run runs/<domain>/<content_run> --lang zh
```

Emits `report/combined_report.html` (+ `.zh.html`). Keeps technical /100 (incl. SEO dim) and Content GEO /100 separate; includes a W0–W16 remediation timeline.


## Scoring versions

- Technical: **scoring v1.3** — 10 dims /100 (SEO discoverability = 15). Weights unchanged from v1.2; richer extractability / URL hygiene / claim-evidence heuristics.
- Content GEO: separate /100 (IA20 TAX15 WRITE20 AUTH20 QUERY25).
- GEO = Generative Engine Optimization only — never geography / local-pack framing.
- Client deliverables: **HTML only**.
