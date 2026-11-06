# SEO Content Discoverability (technical dimension)

> **GEO Checker** by **Beansmile**. GEO = Generative Engine Optimization (websites), never geography.
>
> From scoring **v1.2**, SEO content discoverability is a **15-point dimension** inside the technical **100-point** scale (`scoring.md`). It is **not** a standalone /25 total and **not** scored inside Content GEO (`content_scoring.md`).
>
> Bonuses/penalties (ACC, llms.txt, ItemList, …) remain in `score_adjustments` and are **not** folded into this dimension’s weight.

## Purpose

SEO content discoverability answers: *If web search cannot find the important pages, generative engines have little to ground on.*

It scores how findable and indexable the site’s **content URLs** are — titles, H1/meta intent match, thin/duplicate risk, internal crawl paths, and sitemap/robots as **content-discovery aids**.

It is **not** a full rank-tracking SEO audit (no keyword ranks, backlinks, Core Web Vitals lab scores, or traffic forecasts).

## Relationship to Access (ACC)

| Concern | Where scored |
|---|---|
| AI crawler blocked / HTTPS broken / WAF challenge | Technical **ACC** penalties / Access findings (`score_adjustments`) |
| Whether content pages have unique intent titles, thin/dup risk, internal paths to important URLs, sitemap/robots as discovery aids | This **SEO** dimension (15 pts of the technical 100) |

Cross-reference Access findings when crawl fails; do not double-count the same ACC penalty into this dimension’s numeric total. If robots/sitemap cannot be verified because of an access failure, note that here and keep confidence provisional.

## Score (technical dimension, /15)

Engine still computes a heuristic **raw /25** (same sub-signals as before), then scales into the dimension:

```
dim_score = min(15, round(raw_score_25 * 15 / 25, 1))
```

| Band (dim /15) | Approx raw /25 | Signals |
|---|---|---|
| Strong | 12–15 ↔ 20–25 | Distinct titles/H1 per intent; meta descriptions present; clear nav + internal links to products/cases; sitemap reachable; little thin/duplicate |
| Partial | 6–11.9 ↔ 10–19 | Some indexable pages exist, but titles generic, thin product pages, weak internal links, or sitemap/robots unverifiable |
| Weak | 0–5.9 ↔ 0–9 | Critical pages hard to discover; homepage/robots/sitemap failing; thin slogan pages only |

Grade bands for the dimension percentage follow the same A+–D map as other technical dims (90 / 80 / 70 / 60).

### Heuristic sub-signals (engine, max raw 25)

Used by `scripts/seo_analyze.py`:

1. Title presence & length (~6)
2. H1 presence (~4)
3. Title uniqueness across sample (~3)
4. Meta description coverage (~3)
5. Thin content penalty on product/case/home (− up to 5)
6. Internal link density (~3)
7. Direct crawl success (+2) — discovery hygiene, not ACC penalty replay
8. Sitemap verified (+2)
9. robots.txt verified (+2)
10. Image alt rate when HTML present (~2)

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
  "rubric": "seo_scoring.md v1.1"
}
```

Also appears in `dimensions[]` with `key: "seo"`, `max: 15`, and contributes to `base_score` / `overall_score`.

## Version

v1.1 · 2026-11 · Beansmile · GEO Checker · scoring v1.2 dimension (15 of 100)
