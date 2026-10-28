# ICP config: example values

> Replace these with your own ICP. The scoring tables in `scripts/score_leads.py` mirror this file.

## Buyer persona (0–40)
| Points | Titles |
|---|---|
| 40 | CFO, Chief Accounting Officer, VP / Head / Director of Finance, Finance Director, Controller |
| 32 | Assistant Controller; Director / VP / Head of Accounting, FP&A, Reporting or Tax |
| 25 | Fractional CFO; Founder / CEO / COO / CTO at a software or fintech company |
| 20 | Finance or accounting manager |
| 15 | Founder / CEO / COO / CTO elsewhere |
| 12 | Title unknown |
| 8 | Finance individual contributor |
| 0 | Non-finance role |

## Company fit (0–60), operating companies
- **Industry (25 max):** Software/SaaS 25 · Financial services 22 · Holding/PE 20 · Healthcare & life sciences 18 · Professional services 18 · Energy 12 · Education 10 · Other 8 · Manufacturing 0
- **Size (20 max):** revenue sweet spot **$30M–$200M** = 20; falls back to employee count when revenue is unknown
- **Multi-entity (10 max):** Yes 10 · Unknown 4 · No 1
- **Geography (5 max):** core markets 5 · unknown 2 · other 1
- **Customer lookalike:** +5 when the sub-industry matches a segment you already win in

## Other company types
Accounting/advisory firm and solo consultants → **Tier P** (partner/channel) · Big enterprise 8 · Nonprofit/Gov/Edu 5 · Student 0

## Adjustments
- Low-confidence employer match × 0.6 · Medium × 0.85
- Excluded verticals (manufacturing, non-hospitality retail) capped at 54, so Tier C at most

## Tiers
**A ≥70** route to an AE now · **B 55–69** SDR/AE follow-up · **C 35–54** nurture · **D <35** low priority · **P** partner/channel · **U** unscored
