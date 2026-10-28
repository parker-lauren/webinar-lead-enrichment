#!/usr/bin/env python3
"""Score and tier an enriched lead list against an ICP.

Score (0-100) = persona (0-40) + company (0-60), adjusted for match confidence
and capped for excluded verticals. Tiers: A >=70 · B 55-69 · C 35-54 · D <35 ·
P partner/channel · U unscored (no employer).

Input: a CSV with the original registrant columns plus enrichment columns
(Title, Industry, Sub-Industry, Employees, Revenue Band, HQ Country,
Multi-Entity, Company Type, Confidence, Attended). Original columns are kept
untouched; scoring columns are appended. Edit the tables below to match your
own ICP (see icp-config.md).

Usage:
    python score_leads.py enriched.csv ranked.csv
"""
import csv, re, sys
from collections import Counter

# ---------------------------------------------------------------- persona ---
def persona_score(title, industry=""):
    t = (title or "").lower().strip()
    if not t:
        return 12, "Unknown title"
    if "assistant controller" in t:
        return 32, "Accounting leader"
    if re.search(r"\b(cfo|chief financial|chief accounting|cao)\b", t) and "fractional" not in t:
        return 40, "Economic buyer"
    if re.search(r"\b(vp|vice president|head|director)\b.*\bfinance\b|\bfinance director\b|\bcontroller\b", t):
        return 40, "Economic buyer"
    if re.search(r"\b(vp|vice president|head|director|treasurer)\b.*\b(accounting|fp&a|reporting|tax)\b", t):
        return 32, "Accounting leader"
    if "fractional" in t and "cfo" in t:
        return 25, "Fractional CFO"
    if re.search(r"\b(founder|ceo|coo|cto|owner|managing director|md)\b", t):
        tech = any(k in (industry or "").lower() for k in ("software", "saas", "fintech"))
        return (25 if tech else 15), "Exec (non-finance)"
    if re.search(r"\b(finance|accounting)\b.*\bmanager\b|\bmanager\b.*\b(finance|accounting)\b", t):
        return 20, "Finance manager"
    if re.search(r"accountant|analyst|auditor|bookkeep", t):
        return 8, "Finance IC"
    return 0, "Non-finance"

# ---------------------------------------------------------------- company ---
INDUSTRY = {"software": 25, "saas": 25, "financial services": 22, "fintech": 22,
            "holding": 20, "private equity": 20, "healthcare": 18, "life sciences": 18,
            "professional services": 18, "energy": 12, "education": 10, "manufacturing": 0}
REVENUE = {"$30M-$200M": 20, "$10M-$30M": 13, "$200M-$1B": 12, "<$10M": 5, ">$1B": 3}
GEO_CORE = {"US", "UK", "CA", "DE", "AT", "CH", "IE", "SE", "NO", "DK", "FI", "FR",
            "NL", "BE", "LU", "ES", "PT", "IT", "AU", "NZ"}
LOOKALIKE_SEGMENTS = {"fintech", "insurtech", "health tech", "vertical saas", "hr tech",
                      "data/infra", "martech", "it services", "staffing/bpo", "hospitality",
                      "e-commerce", "wealth", "biotech", "regtech", "pe/holding"}
OTHER_TYPES = {"accounting/advisory firm": (10, "P"), "solo/freelance consultant": (5, "P"),
               "big enterprise >10k": (8, None), "nonprofit/gov/education": (5, None),
               "student/none": (0, None)}


def industry_score(ind, sub):
    i = (ind or "").lower()
    if "retail" in i:
        return 12 if any(k in (sub or "").lower() for k in ("hospitality", "e-commerce", "marketplace")) else 3
    for k, v in INDUSTRY.items():
        if k in i:
            return v
    return 8


def size_score(rev, emp):
    if rev in REVENUE:
        return REVENUE[rev]
    try:
        e = int(str(emp).replace(",", ""))
    except ValueError:
        return 8
    if 100 <= e <= 1000: return 16
    if 50 <= e < 100: return 11
    if 1000 < e <= 5000: return 9
    if e < 50: return 4
    return 2


def excluded(ind, sub):
    i, s = (ind or "").lower(), (sub or "").lower()
    return "manufacturing" in i or ("retail" in i and not any(k in s for k in ("hospitality", "e-commerce", "marketplace")))


def score_row(r):
    ctype = (r.get("Company Type") or "").strip().lower()
    if not ctype and not r.get("Industry"):
        return None, "U", "Unscored: no employer found", ""
    p, fit = persona_score(r.get("Title"), r.get("Industry"))
    flag, look = [], ""
    if ctype in OTHER_TYPES:
        c, forced = OTHER_TYPES[ctype]
        if forced:
            flag.append("Partner/channel")
            return p + c, forced, fit, "; ".join(flag)
        if "enterprise" in ctype:
            flag.append("Enterprise above ICP size")
    else:
        c = industry_score(r.get("Industry"), r.get("Sub-Industry"))
        c += size_score(r.get("Revenue Band"), r.get("Employees"))
        c += {"yes": 10, "no": 1}.get((r.get("Multi-Entity") or "").lower(), 4)
        geo = (r.get("HQ Country") or "").upper()
        c += 5 if geo in GEO_CORE else (2 if not geo else 1)
        sub = (r.get("Sub-Industry") or "").lower()
        if sub in LOOKALIKE_SEGMENTS:
            c += 5
            look = sub
    c = min(c, 60)
    c *= {"low": 0.6, "medium": 0.85}.get((r.get("Confidence") or "").lower(), 1.0)
    s = round(p + c)
    if excluded(r.get("Industry"), r.get("Sub-Industry")):
        s = min(s, 54)
        flag.append("Excluded vertical")
    tier = "A" if s >= 70 else "B" if s >= 55 else "C" if s >= 35 else "D"
    if look:
        flag.append(f"Lookalike: {look}")
    return s, tier, fit, "; ".join(flag)


NEXT = {"A": "Route to AE now", "B": "SDR/AE follow-up", "C": "Nurture",
        "D": "Low priority", "P": "Partner/channel team", "U": "Research employer"}
ORDER = {t: i for i, t in enumerate("ABCPDU")}


def main(src, dst):
    with open(src, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        cols = list(rows[0].keys()) if rows else []
    for r in rows:
        s, tier, fit, flag = score_row(r)
        r["ICP Score"], r["ICP Tier"], r["Persona Fit"], r["ICP Flag"] = ("" if s is None else s), tier, fit, flag
        nxt = NEXT[tier]
        if tier in "AB" and (r.get("Attended") or "").lower().startswith("no"):
            nxt += "; did not attend: send recording first"
        r["Next Action"] = nxt
    rows.sort(key=lambda r: (ORDER[r["ICP Tier"]], -(r["ICP Score"] or 0)))
    for i, r in enumerate(rows, 1):
        r["ICP Rank"] = i
    att = [r for r in rows if (r.get("Attended") or "").lower().startswith("yes")]
    for i, r in enumerate(att, 1):
        r["Attendee Rank"] = i
    out = ["ICP Rank", "Attendee Rank", "ICP Score", "ICP Tier", "Next Action", "Persona Fit", "ICP Flag"]
    with open(dst, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols + out, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    # checks
    for r in rows:
        s, t = r["ICP Score"], r["ICP Tier"]
        assert t in "PU" or (t == "A" and s >= 70) or (t == "B" and 55 <= s < 70) or (t == "C" and 35 <= s < 55) or (t == "D" and s < 35), r
        assert "Excluded vertical" not in r["ICP Flag"] or s <= 54
    print(f"rows in {len(rows)} -> out {len(rows)} (original columns unchanged)")
    c = Counter(r["ICP Tier"] for r in rows)
    print("tiers:", " · ".join(f"{t} {c[t]}" for t in "ABCPDU" if c[t]))
    for r in rows[:5]:
        print(f"  {r['ICP Tier']} {r['ICP Score']:>3}  {r.get('Name','')}, {r.get('Title','')}, {r.get('Company','')}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
