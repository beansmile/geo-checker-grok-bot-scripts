# Content GEO module — design spec (v1.0)

**Brand:** GEO Checker by Beansmile  
**GEO:** Generative Engine Optimization (websites) — never geography  
**Status:** First shippable pipeline in `geo-eval/` (2026-11)

## Goals

1. Keep the existing **technical 9-dimension / 100** score (`scoring.md`) unchanged.
2. Add a **standalone Content GEO** evaluation focused on:
   - SEO content discoverability (titles, intent pages, thin/duplicate, internal paths, sitemap/robots as discovery aids)
   - Information architecture & taxonomy gaps
   - Answer-first writing / extractability
   - Authority evidence publishing
   - Target buyer-question coverage **including AI/search mention checks**
3. Deliver a separate English client report (`content_report.md` + `.html`).

## Score model

See `content_scoring.md`. Weights: C-SEO 25 · C-IA 15 · C-TAX 10 · C-WRITE 15 · C-AUTH 15 · C-QUERY 20.

## Pipeline

```
# New site
python3 scripts/content_eval.py <URL> --site-type corporate --max-pages 16

# Reuse crawl / snapshots
python3 scripts/content_eval.py --from-run runs/<domain>/<run> \
  --ai-checks evidence/ai_checks.json --offsite evidence/offsite.json

# Agent enriches content_report.json (English) per content_prompts.md
python3 scripts/build_content_report.py runs/<domain>/<run>
```

Artifacts per run: `content_extract.json` → `content.engine.json` → `content_report.json` → `report/content_report.{md,html}`.

## AI mention checks (required)

For each target question record method (`live_ui` | `web_retrieval_proxy` | `agent_tool`), whether the brand was mentioned, whether the **official domain** was cited, sources seen, and notes. Never invent engine quotes. If live ChatGPT/Perplexity/Gemini UIs are unavailable, use labeled web retrieval proxies.

## Research inputs

`docs/content_geo_research_sources.md` + user ChatGPT audit attachment for ltzm.com.

## Out of scope (honest)

Full rank tracking, backlink audits, Core Web Vitals lab scores, guaranteed AI citation rates, blending with technical 100.
