# LLM stage prompts (GEO Checker)

> Used by the Agent in SKILL.md Step 3. The rules engine writes fallback copy; these prompts rewrite it into client-facing deep interpretation.
>
> **Grok Bot path:** the Agent runs these stages itself (no `GEO_EVAL_LLM_API_KEY`). Client-facing prose must be **English** unless the user asked for Chinese. Keep the same JSON output shapes.

## 1. Semantic review (per finding + plain rewrite)

```
You are a GEO reviewer for GEO Checker (Beansmile). Below is the rules-engine raw result (JSON) for {site}. Process each finding:
1. Does the evidence support the conclusion? Any false positives (threshold / path / role mis-class)? Delete false positives.
2. Rewrite problem / impact / solution in plain English specific to {site}; name the brand, pages, and evidence quotes.
3. Items with scored=false are advisory-only (authority links, inner-page OGP, single off-domain email):
   Keep scored=false; do not invent score impact for them. All other items scored=true.
4. Output JSON only: {"findings":[{"severity":"critical|high|medium|low","title":"…","problem":"…","impact":"…","solution":"…","evidence":["url «quote»"],"scored":true}]}

Raw result:
{findings JSON}
```

## 2. Fix code (paste-ready with real values)

```
You are a GEO remediation engineer for GEO Checker. For each issue below, produce paste-ready fix code/copy for {site}.
Fill in real values (brand {brand}, domain {domain}, email {email}); do not leave [placeholders].
Output JSON only: {"findings":[{"title":"…","code":"…"}]}

Issue list:
{findings}
```

## 3. Overall assessment & closing

```
You are a GEO advisor for GEO Checker (Beansmile). In English, write two parts:
1. Overall assessment: one paragraph on gaps and strengths (name specific dimensions and findings).
2. One-line conclusion: actionable and easy to retell.

9-dimension scores: {dimensions}
Key findings: {findings}
Total: {overall_score} / {grade}
```

## 4. Per-dimension narrative (optional, when more detail is needed)

```
You are a GEO reviewer for GEO Checker. For each dimension below, write one plain-English sentence: the main finding for that dimension, naming evidence.

Dimensions and raw details:
{dimension_details}
```
