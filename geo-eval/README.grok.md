# GEO Checker (Grok Bot) — runtime notes

**GEO = Generative Engine Optimization** (websites / generative-engine readiness). Not geography or maps.

This folder is the shared skill runtime for the **GEO Checker** Grok Bot (Beansmile).

## Default language

Reports are **English by default** (`build_report.py --lang en`). Pass `--lang zh` only when the user explicitly asks for Chinese.

## LLM enrichment (no external API on Grok Bot)

1. `scripts/enrich.py` runs after the rules engine.
2. On Grok Bot: **do not set** `GEO_EVAL_LLM_API_KEY`. The script copies `report.engine.json` → `report.json`.
3. The Agent then rewrites `report.json` using **`prompts.md`** (English prompts, same JSON shapes).
4. Then run `scripts/build_report.py <run_dir>` (defaults to English templates).

Client-facing prose in the report must be English unless the user requested Chinese.

## Branding

Customer-facing reports show **GEO Checker** and attribution **Beansmile · GEO Checker**. Do not show Report ID / file numbers, sign-off blocks, or “pending review” copy.
