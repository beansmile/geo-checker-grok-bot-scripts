# Content GEO Scoring Rubric (v1.0)

> **GEO = Generative Engine Optimization** (websites / generative-engine readiness). Never geography.
> Brand: **GEO Checker** by **Beansmile**.
> This score is **separate** from the technical 9-dimension 100-point score in `scoring.md`. Do **not** merge or re-weight the technical formula.

## Purpose

Content GEO evaluates whether a site’s **pages and knowledge** can be discovered by search, understood by AI retrieval systems, and cited as evidence when buyers ask real questions.

It covers:

1. SEO content discoverability (if search cannot find pages, AI cannot use them either)
2. Information architecture and page structure
3. Content taxonomy and gaps
4. Writing quality (answer-first, extractable, evidence-backed)
5. Authority / evidence publishing
6. Target query coverage + knowledge completeness
7. **Live / proxy AI-mention checks** for those target questions (first-version requirement)

It does **not** replace full rank-tracking SEO, backlink audits, or paid AI-visibility dashboards. Scope limits must be disclosed in every report.

## Relationship to technical scoring

| Track | File | What it measures |
|---|---|---|
| Technical GEO | `scoring.md` (v1.1) | On-site readiness signals: schema, entity, OGP, robots/HTTPS heuristics, absorption block counts, trust pages, etc. |
| Content GEO | this file | Whether content is findable, structured for questions, written for citation, backed by evidence, and actually referenced for buyer questions |

Reports are **standalone**. Never invent a blended “overall” that mixes the two 100-point scales.

## Dimensions (100 points)

| ID | Dimension | Max | What we score |
|---|---|---|---|
| C-SEO | SEO content discoverability | 25 | Unique intent-matched pages; descriptive titles/H1/meta; heading structure; thin/duplicate risk; internal crawl paths to important content; sitemap/robots as they affect **content discovery**; image alt / extractable docs when observed. Honest: not a full ranking audit. |
| C-IA | Information architecture | 15 | Current vs recommended tree; independent URLs for products, solutions, cases, R&D/specs, company proof, knowledge hub |
| C-TAX | Content taxonomy & gaps | 10 | Page-type inventory vs required types for the site class; missing / thin / overlapping categories |
| C-WRITE | Writing quality | 15 | Answer-first openings; self-contained extractable passages; specs/scenarios/standards vs slogans; tables/lists/FAQ where useful |
| C-AUTH | Authority & evidence publishing | 15 | Cases, certifications, specs, awards, patents, media on official URLs with verifiable source links; recovery of off-site evidence onto the site |
| C-QUERY | Target query coverage | 20 | Buyer/user question set for this business; on-site answerability + knowledge completeness fields (what / who-for / specs / standards / cases / inquiry path). **Includes AI-engine mention/citation checks** as evidence for this dimension (see § AI checks). |

Grade map (same bands as technical, separate label **Content GEO**):

| Score | Grade |
|---|---|
| 90–100 | A+ |
| 80–89 | A |
| 70–79 | B |
| 60–69 | C |
| 0–59 | D |
| Cannot evaluate (no usable homepage/body evidence) | F / unevaluable |

## Scoring principles

1. **Evidence required.** No HTML/text evidence → do not invent a precise sub-score; mark `unknown` / reduce confidence.
2. **Disclose sample scope** (URLs reviewed, fetch mode: direct crawl / alternate provider / search snippet).
3. **If homepage body cannot be obtained by any honest path** → overall Content GEO = unevaluable; still publish IA/query/off-site recommendations.
4. **Provisional scores** are allowed when evidence comes from alternate public fetchers or search snippets while direct box crawl fails — label `confidence: provisional` and list blockers (e.g. HTTP 500 / SSL / WAF).
5. **Company-specific prose.** Ban generic template advice that could fit any manufacturer.
6. **English client reports** by default.

## Sub-score guidance (heuristic)

### C-SEO (25)

| Band | Points | Signals |
|---|---|---|
| Strong | 20–25 | Distinct titles/H1 per intent; meta descriptions present; clear nav + internal links to products/cases; sitemap reachable; little thin/duplicate |
| Partial | 10–19 | Some indexable pages exist in search, but titles generic, thin product pages, weak internal links, or sitemap/robots unverifiable |
| Weak | 0–9 | Critical pages hard to discover; homepage/robots/sitemap failing; thin slogan pages only |

### C-IA (15)

Score against a **site-type recommended tree**. Corporate B2B lighting example: Products (each line), Industry solutions, Project cases, R&D/specs, Company strength (certs/awards), Knowledge hub (selection/FAQ), Contact.

### C-TAX (10)

Inventory observed page types vs recommended. Deduct for missing product detail, missing case depth, news-only “evidence”, collapsed “About” dumping.

### C-WRITE (15)

Prefer pages that open with a direct answer, then specs/modules/scenarios. Penalize slogan-only copy (“professional”, “excellent quality”) without parameters.

### C-AUTH (15)

On-site pages for awards/patents/certs/cases with outbound links to primary sources score higher than claims only in About prose or only on third-party sites.

### C-QUERY (20)

1. Build 6–12 procurement questions for the business.
2. For each: score on-site support (0 none / 1 thin / 2 partial / 3 citable).
3. Run **AI mention checks** (§ below) and fold results into narrative + a dedicated evidence table. Mention checks **inform** C-QUERY but do not invent engine quotes.

Knowledge completeness folds into C-QUERY and C-AUTH: each core product/service should cover what it is, who it is for, key specs, standards, representative cases, inquiry path.

## AI mention / citation checks (required in v1)

For each target question, attempt to observe whether mainstream AI / AI-search surfaces mention or cite the **official domain**.

### Allowed methods (label clearly)

| Method | Label | Notes |
|---|---|---|
| Live ChatGPT / Perplexity / Gemini / Claude UI with browsing | `live_ui` | Preferred when available |
| Web search / AI Overview / indexed shortlists (proxy for retrieval corpus) | `web_retrieval_proxy` | Honest proxy when live UIs unavailable |
| Agent native tools that return synthesized answers with citations | `agent_tool` | Record tool name |

### Forbidden

- Inventing quotes or citations from engines not queried
- Claiming `live_ui` when only web search was used
- Counting brand mentions on third-party pages as “official site cited” unless the answer links/cites the official domain

### Per-question record fields

```
question, intent, engines_or_methods, answer_summary, mentioned_brand (yes/no),
cited_official_domain (yes/no), sources_seen[], notes, check_type
```

Report section: **“Target questions × AI / search visibility”** as its own evidence table.

## Research basis (content practices)

Rubric informed by (non-exhaustive; cite URLs used in each run’s research notes):

- Google Search Central — Creating helpful, people-first content; SEO Starter Guide (titles, snippets, organization, alt text, sitemaps as discovery aids)
- Search Engine Land — GEO / extractability / answer-first guidance (2025–2026)
- HubSpot — AEO / answer-first and question-intent practices (2026)
- OpenAI crawler docs — OAI-SearchBot (search) vs GPTBot (training) independence

Technical crawlability remains in the technical report; Content GEO focuses on whether **content** is discoverable and citable once access exists.

## Outputs

Per content run directory:

- `content.engine.json` — heuristic extraction + draft dimension scores
- `content_report.json` — Agent-enriched English narratives, query table, AI-check table, priorities
- `report/content_report.md` + `report/content_report.html` — standalone client deliverable

## Version

v1.0 · 2026-11 · Beansmile · GEO Checker
