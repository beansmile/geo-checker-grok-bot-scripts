# SEO Content Discoverability (technical dimension)

> **GEO Checker** by **Beansmile**. GEO = Generative Engine Optimization (websites), never geography.
>
> From scoring **v1.2**, SEO content discoverability is a **15-point dimension** inside the technical **100-point** scale (`scoring.md`). **v1.3** keeps the same weight and raw /25 → /15 scale; it adds richer sub-heuristics (image-locked thin pages, URL hygiene findings).
>
> Bonuses/penalties (ACC, llms.txt, ItemList, …) remain in `score_adjustments` and are **not** folded into this dimension’s weight.

## Purpose

SEO content discoverability answers: *If web search cannot find the important pages, generative engines have little to ground on.*

It scores how findable and indexable the site’s **content URLs** are — titles, H1/meta intent match, thin/duplicate / **non-extractable** risk, internal crawl paths, sitemap/robots as **content-discovery aids**, and **entry/URL hygiene**.

It is **not** a full rank-tracking SEO audit (no keyword ranks, backlinks, Core Web Vitals lab scores, or traffic forecasts). It is **not** local/geo keyword optimization.

## Relationship to Access (ACC)

| Concern | Where scored |
|---|---|
| AI crawler blocked / HTTPS broken / WAF challenge | Technical **ACC** penalties / Access findings (`score_adjustments`) |
| Soft splash redirects, canonical gaps, multi-home variants, thin/image-locked bodies, titles/H1/meta, internal paths, sitemap/robots | This **SEO** dimension (15 pts of the technical 100) |

Cross-reference Access findings when crawl fails; **do not double-count** the ACC HTTPS penalty into this dimension’s numeric total. If robots/sitemap cannot be verified because of an access failure, note that here and keep confidence provisional.

## Score (technical dimension, /15)

Engine still computes a heuristic **raw /25**, then scales into the dimension:

```
dim_score = min(15, round(raw_score_25 * 15 / 25, 1))
```

| Band (dim /15) | Approx raw /25 | Signals |
|---|---|---|
| Strong | 12–15 ↔ 20–25 | Distinct titles/H1 per intent; meta descriptions present; clear nav + internal links; sitemap reachable; little thin/image-locked; clean home URL |
| Partial | 6–11.9 ↔ 10–19 | Some indexable pages exist, but titles generic, thin/image-locked product pages, weak internal links, canonical/home hygiene issues, or sitemap/robots unverifiable |
| Weak | 0–5.9 ↔ 0–9 | Critical pages hard to discover; homepage/robots/sitemap failing; slogan or media-only pages |

### Heuristic sub-signals (engine, max raw 25)

Used by `scripts/seo_analyze.py`:

1. Title presence & length (~6)
2. H1 presence (~4)
3. Title uniqueness across sample (~3)
4. Meta description coverage (~3)
5. Thin **and/or image-locked** penalty on product/case/home/news (− up to 5)
6. Internal link density (~3)
7. Direct crawl success (+2) — discovery hygiene, not ACC penalty replay
8. Sitemap verified (+2)
9. robots.txt verified (+2)
10. Image alt rate when HTML present (~2)
11. **v1.3 URL hygiene** (small raw deductions, findings SEO-URL-01…04): soft splash / JS redirect; missing canonical majority; canonical mismatch; multiple home host/path variants without 301 evidence

## Report presentation

- Include in the technical dimension table / chart as **SEO content discoverability · xx / 15 (grade)** — part of the **100**.
- Chapter may still expand narrative, notes, findings, and fetch confidence.
- Do **not** label it “separate from the 100” or “not added into overall_score”.
- Keep bonuses/penalties on the adjustments page, distinct from dimension weights.

## Outputs

`report.json` / `report.engine.json`:

```json
"seo_discoverability": {
  "score": 4.4,
  "max": 15,
  "score_raw_25": 7.3,
  "max_raw_25": 25,
  "dim_score": 4.4,
  "grade": "D",
  "confidence": "provisional",
  "notes": [],
  "narr": "",
  "callout": "",
  "findings": [],
  "rubric": "seo_scoring.md v1.2",
  "scoring_version": "v1.3"
}
```

Also appears in `dimensions[]` with `key: "seo"`, `max: 15`, and contributes to `base_score` / `overall_score`.

## Version

v1.2 · 2026-11 · Beansmile · GEO Checker · scoring v1.3 dimension (15 of 100; weights unchanged from scoring v1.2)
