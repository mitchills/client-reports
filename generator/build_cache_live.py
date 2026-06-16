#!/usr/bin/env python3
"""
Build google_cache.json + meta_cache.json from a fresh Pipeboard pull.
Lean refresh: ref date 2026-06-15 → keys "2026-06-09_2026-06-15" (7d) and
"2026-05-01_2026-05-31" (May/last month). One canonical conversion action
per client (avoids Meta double-counting across action types).
"""
import json
from pathlib import Path

GEN = Path(__file__).parent
SEVEN = "2026-06-09_2026-06-15"
MAY = "2026-05-01_2026-05-31"


def r2(x):
    return round(x, 2)


def entry(campaigns, label, prior_conv=0, prior_spend=0.0):
    """campaigns: list of (name, spend, conv). Builds a cache entry."""
    spend = sum(c[1] for c in campaigns)
    conv = sum(c[2] for c in campaigns)
    camps = [{
        "name": n, "spend": r2(s), "conversions": r2(cv),
        "cost_per_conv": r2(s / cv) if cv else 0.0, "adsets": [],
    } for (n, s, cv) in campaigns]
    camps.sort(key=lambda x: x["conversions"], reverse=True)
    return {
        "spend": r2(spend),
        "conversions": r2(conv),
        "cost_per_conv": r2(spend / conv) if conv else 0.0,
        "breakdown": [{"name": label, "conversions": r2(conv)}] if conv else [],
        "campaigns": camps,
        "prior": {
            "conversions": r2(prior_conv),
            "cost_per_conv": r2(prior_spend / prior_conv) if prior_conv else 0.0,
        },
    }


# ── META ─────────────────────────────────────────────────────────────────────
meta = {
    # A Plus Physio — bookings (purchase action)
    "act_1405008824620416": {
        SEVEN: entry([("MM | Conversions | Physio", 78.27, 1),
                      ("MM | Conversions | Chiro", 45.88, 1)],
                     "Booking", prior_conv=0, prior_spend=151.65),
        MAY: entry([("MM | Conversions | Physio", 563.14, 8),
                    ("MM | Conversions | Chiro", 218.72, 0)], "Booking"),
    },
    # Regen Health — leads
    "act_851463511303862": {
        SEVEN: entry([("MM | Conversions | Physio", 339.00, 5)],
                     "Lead", prior_conv=1, prior_spend=163.66),
        MAY: entry([("MM | Conversions | Physio", 1467.31, 0)], "Lead"),
    },
    # Summit Chiro — bookings (custom conv)
    "act_631477383077560": {
        SEVEN: entry([("MM | Conversions | Chiro", 133.80, 6)],
                     "Booking", prior_conv=2, prior_spend=107.05),
        MAY: entry([("MM | Conversions | Chiro", 750.43, 26)], "Booking"),
    },
    # Heidelberg Osteopaths — bookings (custom conv)
    "act_718379509811221": {
        SEVEN: entry([("MM | Bookings | Osteo", 799.48, 6)],
                     "Booking", prior_conv=13, prior_spend=569.02),
        MAY: entry([("MM | Bookings | Osteo", 1696.98, 25),
                    ("MM | Bookings | Remedial", 305.58, 4)], "Booking"),
    },
    # Elite Health — bookings (custom conv)
    "act_488804362788988": {
        SEVEN: entry([("MM | Cliniko Bookings | BH", 606.78, 17),
                      ("MM | Cliniko Bookings | TW", 516.91, 7),
                      ("MM | Cliniko Bookings | COOP", 57.93, 1),
                      ("MM | IG Page Visits", 28.36, 0),
                      ("Instagram post (boosted)", 73.93, 0)],
                     "Booking", prior_conv=20, prior_spend=1147.20),
        MAY: entry([("MM | Cliniko Bookings | BH", 2927.57, 53),
                    ("MM | Cliniko Bookings | TW", 2080.51, 37),
                    ("MM | Cliniko Bookings | COOP", 517.08, 6),
                    ("MM | IG Page Visits", 124.20, 2),
                    ("Instagram post (boosted)", 57.56, 0)], "Booking"),
    },
    # Stepz Fitness — leads
    "act_887644738898147": {
        SEVEN: entry([("MM | Forms | Info Pack", 287.85, 2)],
                     "Lead", prior_conv=2, prior_spend=276.47),
        MAY: entry([("MM | Forms | Info Pack", 1248.29, 15),
                    ("EXP Brightwater | Conversion", 501.25, 6),
                    ("MM | Forms | Retarget", 30.02, 3)], "Lead"),
    },
}

# ── GOOGLE (conversions field direct; priors n/a → 0) ────────────────────────
google = {
    "1519461427": {  # A Plus Physio
        SEVEN: entry([("MM | PMax | Physio", 68.19, 2),
                      ("MM | PMax | Chiro", 69.37, 1)], "Booking"),
        MAY: entry([("MM | PMax | Physio", 446.52, 8),
                    ("MM | PMax | Chiro", 116.93, 2)], "Booking"),
    },
    "2080537843": {  # Regen Health
        SEVEN: entry([("MM | PMax | Physio", 190.69, 2),
                      ("MM | Search | Physio", 63.86, 0)], "Booking"),
        MAY: entry([("MM | PMax | Physio", 254.93, 3),
                    ("MM | Search | Physio", 347.28, 2)], "Booking"),
    },
    "3650022070": {  # Summit Chiro
        SEVEN: entry([("MM | Search | Sports Chiro", 56.10, 2)], "Booking"),
        MAY: entry([("MM | Search | Sports Chiro", 308.28, 8)], "Booking"),
    },
    "6443816223": {  # Heidelberg Osteopaths
        SEVEN: entry([("MM | Search | Osteo", 406.70, 12)], "Booking"),
        MAY: entry([("MM | Search | Osteo", 1375.48, 57.99)], "Booking"),
    },
}

(GEN / "meta_cache.json").write_text(json.dumps(meta, indent=2))
(GEN / "google_cache.json").write_text(json.dumps(google, indent=2))
print("✓ caches written (7d + May) for ref 2026-06-15")
for acc, per in {**{f"M:{k[-6:]}": v for k, v in meta.items()},
                 **{f"G:{k[-6:]}": v for k, v in google.items()}}.items():
    s = per[SEVEN]
    print(f"  {acc}  7d: {s['conversions']:g} conv  ${s['spend']:g}  CPA ${s['cost_per_conv']:g}")
