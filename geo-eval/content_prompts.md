# Content GEO — Agent enrichment prompts

**HARD RULE:** If report language is Chinese, rewrite primary JSON prose into Chinese before `build_* --lang zh`. Never chrome-only ZH from English enrichment.

> Used after `scripts/content_eval.py` / `content_analyze.py` produce `content.engine.json`.
> **Grok Bot path:** the Agent rewrites into client prose in the **report language** (English by default; Chinese when the user explicitly asked — 中文报告 / Chinese report / 出中文). Do not call external OpenAI APIs. Do not ask for language unless they asked for both or it is ambiguous.
> Brand: GEO Checker (Beansmile). GEO = Generative Engine Optimization (websites), never geography.
>
> SEO content discoverability is enriched in the **technical** report (`seo_scoring.md`), not here.
>
> After technical HTML is delivered, ask once whether to also produce Content GEO + combined. On yes, always use `content_eval.py --from-run <tech_run>` (same crawl; no second fetch). Build with `build_content_report.py [--lang zh]` matching the report language. For Chinese, write Chinese into **primary** fields (`overall_summary`, `closing`, dim `narr`/`callout`, findings, actions); `*_zh` remain optional builder fallbacks.

## 1. Overall Content GEO narrative

```
You are a Content GEO advisor for GEO Checker (Beansmile). Site: {brand} ({domain}).
Using ONLY the evidence in content.engine.json + page texts + AI-check records:
1. Write overall_summary (1–2 paragraphs) in {REPORT_LANGUAGE}: strengths and gaps in architecture, writing,
   authority evidence, and buyer-question coverage / AI visibility.
2. Write closing (one sentence, retellable) in {REPORT_LANGUAGE}.
3. Do not invent HTML you did not see. Disclose fetch_mode and sample scope.
4. Explain what Content GEO evaluates (understand / trust / cite). Do NOT open with a
   comparison disclaimer about the technical 10-dimension score.
Output JSON fields: overall_summary, closing, confidence, fetch_disclosure
```

## 2. Dimension narratives

```
For each content dimension (C-IA, C-TAX, C-WRITE, C-AUTH, C-QUERY), write in {REPORT_LANGUAGE}:
- narr: one plain paragraph naming brand-specific evidence
- callout: concrete improvement for this company (not generic tips)
- findings: 0–3 company-specific issues with evidence quotes/URLs
```

## 3. Target questions + AI checks

```
Build or refine 6–12 procurement questions for this industry/company
(questions may stay in the market language of the site / buyers).
For each question fill: on_site_support (0–3), knowledge_gaps[], ai_checks[] with check_type
(live_ui | web_retrieval_proxy | agent_tool), engines_or_methods, answer_summary,
mentioned_brand, cited_official_domain, sources_seen[], notes.
Narratives / notes / answer_summary in {REPORT_LANGUAGE}.
Never fabricate engine quotes. If live ChatGPT/Perplexity/Gemini UI was unavailable, say so.
```

## 4. Recommended IA + page briefs

```
Produce recommended_ia_tree and page_briefs[] in {REPORT_LANGUAGE}: URL pattern, page purpose, must-have sections
(answer-first lead, specs table, standards, cases, FAQ, inquiry CTA, source links),
and which target questions each page should win.
```

## 5. Priority actions (concrete + sample)

```
List 5–8 priority actions ordered P0–P2 for Content GEO (citable content + evidence
publishing + query coverage). Write in {REPORT_LANGUAGE}.
Do not duplicate the technical report’s SEO discoverability actions unless content-owned.

Each action MUST be an object with:
- sev: P0|P1|P2
- action: short title (what changes)
- detail: what to change on which URLs / templates, and acceptance criteria
- sample: concrete example the client can copy — sample H1/title, answer-first lead,
  outline, JSON-LD sketch, or paragraph pattern (brand-specific; not generic filler)
- owner: content | eng | eng/ops | PR | content/eng | …
- effort_days: number (calendar days; HTTPS/crawl ≤1; evergreen page ~2–4 each;
  proof hub / EN export ~5–10; re-test 1)
- outcome: expected result after the change

Builders render sample in a distinct callout and build an effort-based follow-up
timeline (checklist + schedule) from these fields. Prefer structured objects over
plain strings.
```

`{REPORT_LANGUAGE}` = `English` (default) or `Chinese` when the user asked for a Chinese report.
