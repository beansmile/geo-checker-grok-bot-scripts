# GEO Checker — Grok Bot runtime scripts

**GEO = Generative Engine Optimization** (websites). Not geography.

Python runtime used by the Beansmile **GEO Checker** Grok Bot: crawl a site, run the 9-dimension rules engine, then build English `report.md` + `report.html` decks. The Bot itself does LLM enrichment (no external API key required on the Grok Bot path).

## Layout

```
geo-eval/          # skill runtime (scripts, rules, report templates)
  scripts/         # run.py → analyze → enrich → build_report.py
  report_templates/
  SKILL.md
  …
LICENSE            # MIT
```

## Install for Grok Bot

```bash
git clone https://github.com/beansmile/geo-checker-grok-bot-scripts.git /workspace/skills/geo-checker-grok-bot-scripts
# expected skill path used by GEO Checker:
ln -sfn /workspace/skills/geo-checker-grok-bot-scripts/geo-eval /workspace/skills/geo-eval
```

Or clone directly into `/workspace/skills/geo-eval` if you only need the skill folder.

Requires **Python 3** (stdlib only). Optional: Chrome for PDF export.

## License

MIT © Beansmile
