---
name: "webinar-lead-enrichment"
description: "Enrich a webinar or event registrant list (find employers for personal emails, add titles and firmographics via web and Clay), score it against your ICP (`icp-config.md`), customer lookalikes and target accounts, mark attendees, and return a ranked CSV."
---

# Webinar lead enrichment + ICP ranking

Turns a raw webinar/event lead list into a ranked, sales-ready CSV. There are four stages, and the user can ask for any subset:

1. **Employer lookup** for personal-email rows (gmail, yahoo and so on).
2. **Firmographic and title research** for every row that has an employer (web search first, Clay to fill the gaps).
3. **ICP scoring and tiering** against the ICP in `icp-config.md`, lookalikes from your customer list, and your target-account list. The arithmetic is in `scripts/score_leads.py`.
4. **Attendance marking** from a HubSpot / Zoom attendee export.

Always keep every original row and column unchanged. Add new columns; never overwrite source values, except filling a blank LinkedIn URL.

## Before you start

- Read the input CSV. Report the row count, columns, and the value counts of any status column (e.g. `Company Source`).
- **Ask** (AskUserQuestion) only what isn't clear: which rows to process, whether Clay credits may be used, and whether there's an attendee export. Default to all rows, web research first, and Clay for gaps.
- Registrant list ≠ attendee list. If the user calls it an "attendee list", confirm or ask for the attendee export, because it changes the next action for every row.

## Stage 1 — Employer lookup (personal emails)

For each target row, find the current employer, company URL, LinkedIn URL, confidence and a short note.

- Use hints in the email handle: business names (`brightledgerconsulting@`, `jmfinance04@`), designations (`acma`, `cpa`), locale (`.ca`, `.co.uk`, `126.com` → China), birth years or numbers that also appear in LinkedIn slugs.
- **Confidence:** High = name + finance context + handle/location signals all align. Medium = likely, with some signal. Low = plausible but a common name or weak signal.
- Skip initials-only names. Very common names with no distinguishing signal get Low or no match.
- **Never invent URLs.** Company URL only if the domain was actually seen; LinkedIn only if that exact profile URL appeared in results.
- **Company Source values:** `LinkedIn/web search` (employer found), `LinkedIn/web search (profile only)` (profile matched, employer not visible), `Searched – no match`. Say you used the profile-only value if the user asked for only two values.

## Stage 2 — Firmographics and titles

Per row with an employer, capture: title, industry, sub_industry, employees, revenue_band, hq_country, multi_entity (Yes/No/Unknown), company_type (Operating company / Accounting/advisory firm / Solo/freelance consultant / Big enterprise >10k / Nonprofit/Gov/Education / Student/None), plus a research note with its source.

**Execution:**

- Fan out to parallel `general-purpose` subagents: about 20 rows each for employer lookup, about 40 rows each for firmographics. Each writes a JSON array to the scratchpad. Give them the exact schema, the no-guessing rules and a limit of 3 searches per row.
- **Web search has a session-wide cap (~200 searches).** Big lists will hit it. Have agents tag unsearched rows (`not searched – search cap`) so you can mark them `Partial` and hand them to Clay.
- **Clay fallback** (`search-contacts-by-name`):
  - Max 20 contacts per call, but calls over ~10 often time out at 180 s, so use batches of 8–10.
  - Needs a company **domain** (from the Company URL or a business email). It can't look up personal-email rows that have no domain.
  - Company firmographics come back even when the person isn't found, so it's still worth running.
  - Contact hit rate is about 25%. Treat a returned title as current only if the company matches; ignore results where the latest employer differs, e.g. the person moved on.
  - To save credits and time, only send operating companies or unknown types. Titles don't change the tier for accounting firms, big enterprises or nonprofits.
  - Responses are very verbose (location arrays). Transcribe the key fields (company, emp, industry, country, revenue, contact, title, li) to a JSONL file right after each call.
  - Map Clay revenue buckets: `0-500K/1M-5M/5M-10M` → `<$10M`, `10M-25M` → `$10M-$30M`, `25M-75M/75M-200M` → `$30M-$200M`, `200M-500M/500M-1B` → `$200M-$1B`, `1B-10B` → `>$1B`.

## Stage 3 — ICP scoring

**Load the ICP sources fresh each run** (they change):

- `icp-config.md`: buyer titles, excluded verticals, revenue sweet spot, and scoring weights.
- Your **customer list** (CRM export or database: name, domain, industry, sub-industry, employees, revenue band, HQ). Use it for lookalike matching and to flag existing customers.
- Your **target-account list** (with account owner). Flag any matches.

**Matching pitfalls** (all seen in practice):

- Never match on an empty domain or empty normalized name; it matches everything.
- No substring matching on company names (EY matched "dBeyond"). Use exact normalized name or exact domain.
- Verify customer matches by domain: a short acronym domain like `abc.com` can belong to an unrelated company, while your customer "ABC" is really `abc-us.com`.

**Score (0–100) = persona (0–40) + company (0–60).**

Persona:

- 40: CFO, CAO/Chief Accounting, VP / Head / Director of Finance, Finance Director, Controller or Financial Controller (not Assistant)
- 32: Assistant Controller, or Director/VP/Head/Treasurer of accounting, FP&A, reporting or tax
- 25: Fractional CFO. Founder/CEO/COO/CTO/Owner/MD also gets 25 at a software or fintech company, otherwise 15
- 20: Finance or accounting manager
- 8: Finance individual contributor (accountant, analyst, auditor, bookkeeper)
- 0: Non-finance role (engineer, marketing, student, intern)
- 12: Title unknown

Company, for operating companies:

- **Industry:** Software/SaaS 25; Financial services 22; Holding/PE 20; Healthcare & life sciences 18; Professional services 18; Energy 12; Education 10; Other/unknown 8; Manufacturing 0. Retail scores 12 if hospitality, e-commerce or marketplace (customer lookalikes), otherwise 3.
- **Size:** Revenue $30–200M 20; $10–30M 13; $200M–1B 12; <$10M 5; >$1B 3. If revenue is unknown, use employees: 100–1000 → 16; 50–99 → 11; 1001–5000 → 9; <50 → 4; >5000 → 2; unknown → 8.
- **Multi-entity:** Yes 10; Unknown 4; No 1.
- **Geography:** US/UK/CA/DACH/IE/Nordics/FR/NL/BE/LU/ES/PT/IT/AU/NZ 5; other 1; unknown 2.
- **Customer lookalike:** +5 if the sub-industry matches a customer segment (fintech, insurtech, health tech, vertical SaaS, HR tech, data/infra, martech, IT services, staffing/BPO, hospitality, e-commerce, wealth, biotech, providers, PE/holding, ag tech, energy tech, education, regtech). Name the customers in a `Customer Lookalike` column.

Company scores for other types:

- Accounting/advisory firm 10 → tier **P – Partner/channel**
- Solo consultant 5 → tier **P**
- Big enterprise 8
- Nonprofit/Gov/Edu 5
- Student 0

Adjustments and tiers:

- Multiply the company score by 0.6 for Low-confidence and 0.85 for Medium-confidence employer matches.
- Cap excluded verticals (manufacturing, non-hospitality retail) at 54, so Tier C at most.
- Tiers: **A ≥70** route to an AE now · **B 55–69** SDR/AE follow-up · **C 35–54** nurture · **D <35** low priority · **P** partner/channel · **U** unscored (no employer).

## Stage 4 — Attendance

- HubSpot workflow exports usually include only names (`Trigger Record Name`), not emails. Match on normalized name (strip accents and punctuation, lowercase).
- Unmatched names are usually speakers, hosts or internal staff. List them and confirm; don't add them.
- If one name matches two rows (same person, two emails), mark both `Yes (same person, 2 emails)`.
- Add `Attended` (Yes / No (registered only)) and an `Attendee Rank` (ICP order among attendees only). For Tier A/B non-attendees, append "did not attend: send recording first" to Next Action.

## Output

Write one CSV and hand it back to the user.

- **Columns:** the original columns first, then ICP Rank, Attendee Rank, ICP Score, ICP Tier, Attended, Next Action, Title, Persona Fit, Industry, Sub-Industry, Employees, Revenue Band, HQ Country, Multi-Entity, Company Type, Customer Lookalike, ICP Flag, Research Note, Research Basis (Web researched / Clay company data (+ title) / Partial — search limit hit / Not researched).
- **Sort order:** tier (A, B, C, P, D, U), then score descending.
- **ICP Flag examples:** Partner/channel, Excluded vertical, Enterprise above ICP size, Possible duplicate person, Not the X customer (explain why).

## Final check (always run before delivering)

- Row count matches the input, and original columns are identical except for filled blank LinkedIn URLs (count them).
- Score ranges sit inside each tier's bounds, and excluded verticals are ≤54.
- Duplicate people (same name, different emails) are flagged, not removed.
- Report the counts per tier, how many rows are Partial or unresearched, and any customer or target-account matches.
- Call out that Low-confidence and title-less Tier B rows need a human check before outreach.

## Reply format

Keep it short:

- A tier-count table.
- The top Tier A names (name, title, company).
- What was flagged.
- Where the data is thin.
- An offer to finish the partial rows.

Don't restate the whole file.