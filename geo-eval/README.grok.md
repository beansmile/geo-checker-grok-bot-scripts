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
