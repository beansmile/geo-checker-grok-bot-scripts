# Content GEO — Agent enrichment prompts

> Used after `scripts/content_eval.py` / `content_analyze.py` produce `content.engine.json`.
> **Grok Bot path:** the Agent rewrites into English client prose. Do not call external OpenAI APIs.
> Brand: GEO Checker (Beansmile). GEO = Generative Engine Optimization (websites), never geography.

## 1. Overall Content GEO narrative

```
You are a Content GEO advisor for GEO Checker (Beansmile). Site: {brand} ({domain}).
Using ONLY the evidence in content.engine.json + page texts + AI-check records:
1. Write overall_summary (1–2 paragraphs): strengths, gaps, SEO discoverability vs GEO citability.
2. Write closing (one sentence, retellable).
3. Do not invent HTML you did not see. Disclose fetch_mode and sample scope.
4. Keep Content GEO score separate from any technical 9-dim score.
Output JSON fields: overall_summary, closing, confidence, fetch_disclosure
```

## 2. Dimension narratives

```
For each content dimension (C-SEO, C-IA, C-TAX, C-WRITE, C-AUTH, C-QUERY), write:
- narr: one plain-English paragraph naming brand-specific evidence
- callout: concrete improvement for this company (not generic SEO tips)
- findings: 0–3 company-specific issues with evidence quotes/URLs
```

## 3. Target questions + AI checks

```
Build or refine 6–12 procurement questions for this industry/company.
For each question fill: on_site_support (0–3), knowledge_gaps[], ai_checks[] with check_type
(live_ui | web_retrieval_proxy | agent_tool), engines_or_methods, answer_summary,
mentioned_brand, cited_official_domain, sources_seen[], notes.
Never fabricate engine quotes. If live ChatGPT/Perplexity/Gemini UI was unavailable, say so.
```

## 4. Recommended IA + page briefs

```
Produce recommended_ia_tree and page_briefs[]: URL pattern, page purpose, must-have sections
(answer-first lead, specs table, standards, cases, FAQ, inquiry CTA, source links),
and which target questions each page should win.
```

## 5. Priority actions

```
List 5–8 priority actions ordered P0–P2 for Content GEO (SEO discoverability + citable content +
evidence publishing + query coverage). Owner hints: content / SEO / eng / PR. English only.
```
