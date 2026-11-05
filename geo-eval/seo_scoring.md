# SEO Content Discoverability (technical add-on)

> **GEO Checker** by **Beansmile**. GEO = Generative Engine Optimization (websites), never geography.
>
> This block lives in the **technical** GEO readiness report. It does **not** change the nine-dimension 100-point formula in `scoring.md` (v1.1). Historical technical totals stay comparable.
>
> Do **not** score this block inside Content GEO (`content_scoring.md`). Content GEO covers architecture, taxonomy, writing, authority evidence, and buyer-question coverage.

## Purpose

SEO content discoverability answers: *If web search cannot find the important pages, generative engines have little to ground on.*

It scores how findable and indexable the site’s **content URLs** are — titles, H1/meta intent match, thin/duplicate risk, internal crawl paths, and sitemap/robots as **content-discovery aids**.

It is **not** a full rank-tracking SEO audit (no keyword ranks, backlinks, Core Web Vitals lab scores, or traffic forecasts).

## Relationship to Access (ACC)

| Concern | Where scored |
|---|---|
| AI crawler blocked / HTTPS broken / WAF challenge | Technical **ACC** penalties / Access findings |
| Whether content pages have unique intent titles, thin/dup risk, internal paths to important URLs, sitemap/robots as discovery aids | This **SEO discoverability** block |

Cross-reference Access findings when crawl fails; do not double-count the same ACC penalty into this block’s numeric total. If robots/sitemap cannot be verified because of an access failure, note that here and keep confidence provisional.

## Score (standalone, /25)

| Band | Points | Signals |
|---|---|---|
| Strong | 20–25 | Distinct titles/H1 per intent; meta descriptions present; clear nav + internal links to products/cases; sitemap reachable; little thin/duplicate |
| Partial | 10–19 | Some indexable pages exist, but titles generic, thin product pages, weak internal links, or sitemap/robots unverifiable |
| Weak | 0–9 | Critical pages hard to discover; homepage/robots/sitemap failing; thin slogan pages only |

Grade bands for the block percentage follow the same A+–D map as technical dims (90 / 80 / 70 / 60).

### Heuristic sub-signals (engine)

Used by `scripts/seo_analyze.py` (max 25):

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

- Show as its own chapter / scored card: **SEO content discoverability · xx / 25 (grade)**
- Clearly label: *Separate from the nine-dimension on-site readiness total — not added into the 100.*
- Include findings, callout, fetch confidence, and sample scope

## Outputs

`report.json` / `report.engine.json` field:

```json
"seo_discoverability": {
  "score": 7.3,
  "max": 25,
  "grade": "D",
  "confidence": "provisional",
  "notes": [],
  "narr": "",
  "callout": "",
  "findings": []
}
```

## Version

v1.0 · 2026-11 · Beansmile · GEO Checker
