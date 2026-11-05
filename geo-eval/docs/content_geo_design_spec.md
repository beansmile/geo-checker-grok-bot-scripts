# Content GEO module — design spec (v1.1)

**Brand:** GEO Checker by Beansmile  
**GEO:** Generative Engine Optimization (websites) — never geography  
**Status:** Content pipeline + technical SEO chapter (2026-11)

## Goals

1. Keep the existing **technical 9-dimension / 100** score (`scoring.md`) unchanged.
2. Add **SEO content discoverability** as a **separate scored block** in the technical report (`seo_scoring.md`, /25, not merged into the 100).
3. Deliver a **standalone Content GEO** report focused on:
   - Information architecture & taxonomy gaps
   - Answer-first writing / extractability
   - Authority evidence publishing
   - Target buyer-question coverage **including AI/search mention checks**
4. Client-facing English by default; Chinese copies on request for review.

## Score model

See `content_scoring.md` v1.1. Weights: C-IA 20 · C-TAX 15 · C-WRITE 20 · C-AUTH 20 · C-QUERY 25.

SEO discoverability (former Content C-SEO) → technical report only.

## Pipeline

```
# Technical (includes SEO chapter)
python3 scripts/run.py <URL> --site-type corporate --max-pages 16
# Agent enriches report.json per prompts.md (+ seo_discoverability.narr/callout)
python3 scripts/build_report.py runs/<domain>/<run> --lang en

# Content GEO (standalone)
python3 scripts/content_eval.py <URL> --site-type corporate --max-pages 16
# or: --from-run runs/<domain>/<run> --ai-checks evidence/ai_checks.json --offsite evidence/offsite.json
# Agent enriches content_report.json per content_prompts.md
python3 scripts/build_content_report.py runs/<domain>/<run>
```

## AI mention checks (required for Content GEO)

Label method (`live_ui` | `web_retrieval_proxy` | `agent_tool`). Never invent engine quotes.

## Out of scope (honest)

Full rank tracking, backlink audits, Core Web Vitals lab scores, guaranteed AI citation rates, blending Content GEO with technical 100.
