#!/usr/bin/env python3
"""
Build google_cache.json + meta_cache.json from a fresh Pipeboard pull.

Lean refresh: ref date 2026-06-15 → keys "2026-06-09_2026-06-15" (7d) and
"2026-05-01_2026-05-31" (May/last month). One canonical conversion action
per client (avoids Meta double-counting across action types).

TRUST GATE: every entry carries an independent account-level total
(account_check) pulled separately from the campaign data. Each entry is
reconciled (campaign-sum vs account total) at build time — if anything is
off by more than the tolerance, the build FAILS and writes nothing.
"""
import json
import sys
from pathlib import Path

GEN = Path(__file__).parent
SEVEN = "2026-06-09_2026-06-15"
MAY = "2026-05-01_2026-05-31"
PULLED_AT = "2026-06-16"

SPEND_TOL = 1.00   # $ — a missing campaign or fat-finger always exceeds this
CONV_TOL = 0.05    # conversions — exact bar float noise

_errors = []


def r2(x):
    return round(x, 2)


def entry(campaigns, label, account_check, prior_conv=0, prior_spend=0.0, note=""):
    """
    campaigns: list of (name, spend, conv).
    account_check: (account_spend, account_conv) pulled independently at account level.
    Reconciles campaign-sum vs account total; records verified flag.
    """
    spend = sum(c[1] for c in campaigns)
    conv = sum(c[2] for c in campaigns)
    acc_spend, acc_conv = account_check

    spend_ok = abs(spend - acc_spend) <= max(SPEND_TOL, 0.01 * acc_spend)
    conv_ok = abs(conv - acc_conv) <= CONV_TOL
    verified = spend_ok and conv_ok
    if not verified:
        _errors.append(
            f"{label} RECONCILE FAIL: campaign-sum ${r2(spend)}/{r2(conv)}c "
            f"vs account ${r2(acc_spend)}/{r2(acc_conv)}c "
            f"(spend_ok={spend_ok} conv_ok={conv_ok})"
        )

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
        "verified": verified,
        "pulled_at": PULLED_AT,
        "account_check": {"spend": r2(acc_spend), "conversions": r2(acc_conv)},
        "note": note,
    }


# ── META ─ campaigns: (name, spend, conv) ; account_check: (acct_spend, acct_conv) ──
meta = {
    "act_1405008824620416": {  # A Plus Physio — bookings (purchase)
        SEVEN: entry([("MM | Conversions | Physio", 78.27, 1),
                      ("MM | Conversions | Chiro", 45.88, 1)],
                     "Booking", (124.15, 2), prior_conv=0, prior_spend=151.65),
        MAY: entry([("MM | Conversions | Physio", 563.14, 8),
                    ("MM | Conversions | Chiro", 218.72, 0)],
                   "Booking", (781.86, 8)),
    },
    "act_851463511303862": {  # Regen Health — leads
        SEVEN: entry([("MM | Conversions | Physio", 339.00, 5)],
                     "Lead", (339.02, 5), prior_conv=1, prior_spend=163.66),
        MAY: entry([("MM | Conversions | Physio", 1467.31, 0)],
                   "Lead", (1467.31, 0)),
    },
    "act_631477383077560": {  # Summit Chiro — bookings (custom conv)
        SEVEN: entry([("MM | Conversions | Chiro", 133.80, 6)],
                     "Booking", (133.80, 6), prior_conv=2, prior_spend=107.05),
        MAY: entry([("MM | Conversions | Chiro", 750.43, 26)],
                   "Booking", (750.43, 26)),
    },
    "act_718379509811221": {  # Heidelberg Osteopaths — bookings (custom conv)
        SEVEN: entry([("MM | Bookings | Osteo", 799.48, 6)],
                     "Booking", (799.48, 6), prior_conv=13, prior_spend=569.02),
        MAY: entry([("MM | Bookings | Osteo", 1696.98, 25),
                    ("MM | Bookings | Remedial", 305.58, 4)],
                   "Booking", (2002.56, 29)),
    },
    "act_488804362788988": {  # Elite Health — bookings (custom conv)
        SEVEN: entry([("MM | Cliniko Bookings | BH", 606.78, 17),
                      ("MM | Cliniko Bookings | TW", 516.91, 7),
                      ("MM | Cliniko Bookings | COOP", 57.93, 1),
                      ("MM | IG Page Visits", 28.36, 0),
                      ("Instagram post (boosted)", 73.93, 0)],
                     "Booking", (1283.91, 25), prior_conv=20, prior_spend=1147.20),
        MAY: entry([("MM | Cliniko Bookings | BH", 2927.57, 53),
                    ("MM | Cliniko Bookings | TW", 2080.51, 37),
                    ("MM | Cliniko Bookings | COOP", 517.08, 6),
                    ("MM | IG Page Visits", 124.20, 2),
                    ("Instagram post (boosted)", 57.56, 0)],
                   "Booking", (5706.92, 98)),
    },
    "act_887644738898147": {  # Stepz Fitness — leads
        SEVEN: entry([("MM | Forms | Info Pack", 287.85, 2)],
                     "Lead", (287.85, 2), prior_conv=2, prior_spend=276.47),
        MAY: entry([("MM | Forms | Info Pack", 1248.29, 15),
                    ("EXP Brightwater | Conversion", 501.25, 6),
                    ("MM | Forms | Retarget", 30.02, 3)],
                   "Lead", (1779.56, 24)),
    },
}

# ── GOOGLE (account_check from aggregate_metrics; priors n/a → 0) ─────────────
google = {
    "1519461427": {  # A Plus Physio
        SEVEN: entry([("MM | PMax | Physio", 68.19, 2),
                      ("MM | PMax | Chiro", 69.37, 1)], "Booking", (137.56, 3)),
        MAY: entry([("MM | PMax | Physio", 446.52, 8),
                    ("MM | PMax | Chiro", 116.93, 2)], "Booking", (563.44, 10)),
    },
    "2080537843": {  # Regen Health
        SEVEN: entry([("MM | PMax | Physio", 190.69, 2),
                      ("MM | Search | Physio", 63.86, 0)], "Booking", (254.54, 2)),
        MAY: entry([("MM | PMax | Physio", 254.93, 3),
                    ("MM | Search | Physio", 347.28, 2)], "Booking", (602.22, 5)),
    },
    "3650022070": {  # Summit Chiro
        SEVEN: entry([("MM | Search | Sports Chiro", 56.10, 2)], "Booking", (56.10, 2)),
        MAY: entry([("MM | Search | Sports Chiro", 308.28, 8)], "Booking", (308.28, 8)),
    },
    "6443816223": {  # Heidelberg Osteopaths
        SEVEN: entry([("MM | Search | Osteo", 406.70, 12)], "Booking", (406.70, 12)),
        MAY: entry([("MM | Search | Osteo", 1375.48, 57.99)], "Booking", (1375.48, 57.99)),
    },
}

# ── HARD GATE: refuse to write if anything failed reconciliation ─────────────
if _errors:
    print("✗ BUILD ABORTED — reconciliation failures:", file=sys.stderr)
    for e in _errors:
        print(f"   {e}", file=sys.stderr)
    sys.exit(1)

(GEN / "meta_cache.json").write_text(json.dumps(meta, indent=2))
(GEN / "google_cache.json").write_text(json.dumps(google, indent=2))
print(f"✓ caches written + reconciled (7d + May), pulled {PULLED_AT}")
