#!/usr/bin/env python3
"""
Build google_cache.json and meta_cache.json from Pipeboard-pulled data.
Run: python build_cache.py
"""
import json
from collections import defaultdict
from pathlib import Path

GEN = Path(__file__).parent

# ── Conversion logic (matches meta_pull.py exactly) ──────────────────────────
CONVERSION_ACTION_TYPES = {
    "lead", "purchase", "complete_registration", "contact",
    "submit_application", "schedule",
    "offsite_conversion.fb_pixel_lead",
    "offsite_conversion.fb_pixel_purchase",
    "offsite_conversion.fb_pixel_complete_registration",
    "onsite_conversion.lead_grouped",
}
ACTION_LABELS = {
    "lead": "Lead", "purchase": "Purchase",
    "complete_registration": "Registration", "contact": "Contact",
    "submit_application": "Application", "schedule": "Booking",
    "offsite_conversion.fb_pixel_lead": "Lead",
    "offsite_conversion.fb_pixel_purchase": "Purchase",
    "offsite_conversion.fb_pixel_complete_registration": "Registration",
    "onsite_conversion.lead_grouped": "Lead",
}

def is_conv(at):
    return at in CONVERSION_ACTION_TYPES or at.startswith("offsite_conversion.custom.")

def label(at):
    if at in ACTION_LABELS: return ACTION_LABELS[at]
    if at.startswith("offsite_conversion.custom."): return "Custom Conversion"
    return at.replace("_", " ").replace(".", " ").title()

def count_convs(actions):
    totals = defaultdict(float)
    for a in (actions or []):
        if is_conv(a["action_type"]):
            totals[a["action_type"]] += float(a["value"])
    total = sum(totals.values())
    breakdown = sorted(
        [{"name": label(k), "conversions": v} for k, v in totals.items()],
        key=lambda x: x["conversions"], reverse=True
    )
    return total, breakdown

def build_from_adsets(adset_rows, prior_actions, prior_spend_val):
    """Build a full cache entry from a list of adset dicts."""
    camp_map = {}
    all_acts = defaultdict(float)
    for row in adset_rows:
        cid = row["campaign_id"]
        cname = row["campaign_name"]
        if cid not in camp_map:
            camp_map[cid] = {"name": cname, "spend": 0.0, "conversions": 0.0, "adsets": []}
        sp = float(row["spend"])
        conv, _ = count_convs(row.get("actions", []))
        camp_map[cid]["spend"] += sp
        camp_map[cid]["conversions"] += conv
        camp_map[cid]["adsets"].append({
            "name": row["adset_name"],
            "conversions": round(conv, 1),
            "cost_per_conv": round(sp / conv, 2) if conv else 0.0,
            "spend": round(sp, 2),
        })
        for a in (row.get("actions") or []):
            if is_conv(a["action_type"]):
                all_acts[a["action_type"]] += float(a["value"])

    camps = []
    total_sp, total_conv = 0.0, 0.0
    for c in camp_map.values():
        c["adsets"].sort(key=lambda x: x["conversions"], reverse=True)
        c["cost_per_conv"] = round(c["spend"] / c["conversions"], 2) if c["conversions"] else 0.0
        c["spend"] = round(c["spend"], 2)
        c["conversions"] = round(c["conversions"], 1)
        total_sp += c["spend"]
        total_conv += c["conversions"]
        camps.append(c)
    camps.sort(key=lambda x: x["conversions"], reverse=True)

    breakdown = sorted(
        [{"name": label(k), "conversions": v} for k, v in all_acts.items()],
        key=lambda x: x["conversions"], reverse=True
    )

    prior_conv, _ = count_convs(prior_actions)
    prior_cpc = round(prior_spend_val / prior_conv, 2) if prior_conv else 0.0

    return {
        "spend": round(total_sp, 2),
        "conversions": round(total_conv, 1),
        "cost_per_conv": round(total_sp / total_conv, 2) if total_conv else 0.0,
        "breakdown": breakdown,
        "campaigns": camps,
        "prior": {"conversions": prior_conv, "cost_per_conv": prior_cpc},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RAW DATA  (action types limited to conversion-relevant ones for brevity)
# campaign_id + campaign_name must be present on each adset row.
# ═══════════════════════════════════════════════════════════════════════════════

PHYSIO_CAMP  = ("120239233200930354", "MM | Conversions | Physio")
CHIRO_CAMP   = ("120241756434810354", "MM | Conversions | Chiro")
REGEN_CAMP   = ("120250057249360460", "MM | Conversions | Physio")
SUMMIT_CAMP  = ("120246100994620456", "MM | Conversions | Chiro")
HEID_CAMP    = ("120232914497840644", "MM | Bookings | Osteo")
EH_BH_CAMP   = ("120213151771980656", "MM | Cliniko Bookings | BH")
EH_TW_CAMP   = ("120240004399610656", "MM | Cliniko Bookings | TW")
EH_COOP_CAMP = ("120240039067340656", "MM | Cliniko Bookings | COOP")
EH_IG_CAMP   = ("120211579812800656", "MM | IG Page Visits")
STEPZ_CAMP   = ("120241781582860429", "MM | Forms | Info Pack")

def a(cid, cname, adset, spend, actions_kv):
    """Shorthand for adset row."""
    return {
        "campaign_id": cid, "campaign_name": cname,
        "adset_name": adset, "spend": str(spend),
        "actions": [{"action_type": k, "value": str(v)} for k, v in actions_kv],
    }

# ── A PLUS PHYSIO (act_1405008824620416) ─────────────────────────────────────
APLUS_7D = [
    a(*PHYSIO_CAMP, "Pilates",      36.04, [("offsite_conversion.fb_pixel_purchase",1),("purchase",1)]),
    a(*PHYSIO_CAMP, "Plantar",      34.77, []),
    a(*PHYSIO_CAMP, "Richel Intro",  8.35, []),
    a(*CHIRO_CAMP,  "Desk Worker",  36.10, [("offsite_conversion.fb_pixel_purchase",1),("purchase",1)]),
    a(*CHIRO_CAMP,  "Harry Intro",  14.17, []),
]
APLUS_14D = [
    a(*PHYSIO_CAMP, "Pilates",      71.30, [("offsite_conversion.fb_pixel_purchase",2),("purchase",2)]),
    a(*PHYSIO_CAMP, "Plantar",      79.34, []),
    a(*PHYSIO_CAMP, "Richel Intro", 29.06, []),
    a(*CHIRO_CAMP,  "Desk Worker",  69.74, [("offsite_conversion.fb_pixel_purchase",1),("purchase",1)]),
    a(*CHIRO_CAMP,  "Harry Intro",  35.07, []),
]
APLUS_MAY = [
    a(*PHYSIO_CAMP, "Pilates",      174.29, [("offsite_conversion.fb_pixel_purchase",2),("purchase",2)]),
    a(*PHYSIO_CAMP, "Hip",          164.70, [("offsite_conversion.fb_pixel_purchase",2),("purchase",2)]),
    a(*PHYSIO_CAMP, "Plantar",      163.55, [("offsite_conversion.fb_pixel_purchase",4),("purchase",4)]),
    a(*PHYSIO_CAMP, "Richel Intro",  60.60, []),
    a(*CHIRO_CAMP,  "Desk Worker",  151.74, []),
    a(*CHIRO_CAMP,  "Harry Intro",   66.98, []),
]
# Priors (account-level actions)
APLUS_PRIOR_7D   = ([("offsite_conversion.fb_pixel_purchase",1),("purchase",1)], 155.08)
APLUS_PRIOR_14D  = ([("offsite_conversion.fb_pixel_purchase",3),("purchase",3)], 374.82)
APLUS_PRIOR_MAY  = ([("offsite_conversion.fb_pixel_purchase",13),("purchase",13)], 716.38)

# ── REGEN HEALTH (act_851463511303862) ───────────────────────────────────────
REGEN_7D = [
    a(*REGEN_CAMP, "Shoulder 2.0", 115.22, [("lead",2),("offsite_conversion.fb_pixel_lead",2)]),
    a(*REGEN_CAMP, "Back 2.0",     120.06, [("lead",2),("offsite_conversion.fb_pixel_lead",2)]),
    a(*REGEN_CAMP, "General",       80.95, []),
]
REGEN_14D = [
    a(*REGEN_CAMP, "Shoulder 2.0", 176.35, [("lead",3),("offsite_conversion.fb_pixel_lead",3)]),
    a(*REGEN_CAMP, "Back 2.0",     183.89, [("lead",3),("offsite_conversion.fb_pixel_lead",3)]),
    a(*REGEN_CAMP, "General",       123.95, []),
]
REGEN_MAY = [
    a(*REGEN_CAMP, "Shoulder 2.0", 380.00, []),
    a(*REGEN_CAMP, "Back 2.0",     700.00, []),
    a(*REGEN_CAMP, "Shoulder",     200.00, []),
    a(*REGEN_CAMP, "Back",         187.31, []),
]
REGEN_PRIOR_7D  = ([("lead",2),("offsite_conversion.fb_pixel_lead",2)], 167.96)
REGEN_PRIOR_14D = ([], 1085.81)   # No conversions in May 18-31 prior
REGEN_PRIOR_MAY = ([], 0.0)       # No data (Apr empty)

# ── SUMMIT CHIRO (act_631477383077560) ───────────────────────────────────────
SC = "offsite_conversion.custom.850123244296678"
SUMMIT_7D = [
    a(*SUMMIT_CAMP, "Shoulder",           63.57, [(SC,3)]),
    a(*SUMMIT_CAMP, "Neck & Head",        42.34, [(SC,1)]),
    a(*SUMMIT_CAMP, "Plantar Fasciitis",  16.93, []),
]
SUMMIT_14D = [
    a(*SUMMIT_CAMP, "Shoulder",           122.74, [(SC,6)]),
    a(*SUMMIT_CAMP, "Neck & Head",         81.82, [(SC,1)]),
    a(*SUMMIT_CAMP, "Plantar Fasciitis",   32.73, []),
]
SUMMIT_MAY = [
    a(*SUMMIT_CAMP, "Shoulder",           390.00, [(SC,13)]),
    a(*SUMMIT_CAMP, "Neck & Head",        163.00, [(SC,4)]),
    a(*SUMMIT_CAMP, "Knee",               120.00, [(SC,5)]),
    a(*SUMMIT_CAMP, "Plantar Fasciitis",   77.43, [(SC,4)]),
]
SUMMIT_PRIOR_7D  = ([(SC,3)], 114.45)
SUMMIT_PRIOR_14D = ([(SC,11)], 254.73)
SUMMIT_PRIOR_MAY = ([(SC,15)], 762.90)

# ── HEIDELBERG OSTEOPATHS (act_718379509811221) ───────────────────────────────
HC = "offsite_conversion.custom.4313895272224005"
HEID_7D = [
    a(*HEID_CAMP, "Low Back | Broad 4.0",          140.90, []),
    a(*HEID_CAMP, "Shoulder | Broad 5.0",           114.79, [(HC,2)]),
    a(*HEID_CAMP, "Gym | Broad 2.0",                293.26, [(HC,4)]),
    a(*HEID_CAMP, "Amy Back/Hip | Broad",            71.59, [(HC,1)]),
    a(*HEID_CAMP, "Joseph Shoulder | Broad",         59.08, []),
    a(*HEID_CAMP, "Joseph Neck & Headaches | Broad", 45.28, []),
    a(*HEID_CAMP, "Joseph | Broad",                  53.28, [(HC,1)]),
]
HEID_14D = [
    a(*HEID_CAMP, "Low Back | Broad 4.0",           278.17, [(HC,3)]),
    a(*HEID_CAMP, "Shoulder | Broad 5.0",           212.00, [(HC,4)]),
    a(*HEID_CAMP, "Gym | Broad 2.0",                531.44, [(HC,11)]),
    a(*HEID_CAMP, "Amy Back/Hip | Broad",           130.00, [(HC,2)]),
    a(*HEID_CAMP, "Joseph Shoulder | Broad",        100.00, []),
    a(*HEID_CAMP, "Joseph Neck & Headaches | Broad", 80.00, []),
    a(*HEID_CAMP, "Joseph | Broad",                  24.48, [(HC,1)]),   # 1356.09 total
]
HEID_MAY = [
    a(*HEID_CAMP, "Remedial 4.0",          150.00, [(HC,1)]),
    a(*HEID_CAMP, "Shoulder | Broad 5.0",  330.00, [(HC,3)]),
    a(*HEID_CAMP, "Gym | Broad 2.0",       950.00, [(HC,16)]),
    a(*HEID_CAMP, "General",               200.00, [(HC,3)]),
    a(*HEID_CAMP, "Top Performers",        200.00, [(HC,3)]),
    a(*HEID_CAMP, "Remedial 6.0",          172.56, [(HC,3)]),
]
HEID_PRIOR_7D  = ([(HC,13)], 577.91)
HEID_PRIOR_14D = ([(HC,19)], 770.00)
HEID_PRIOR_MAY = ([(HC,59)], 2786.44)

# ── ELITE HEALTH (act_488804362788988) ───────────────────────────────────────
EC = "offsite_conversion.custom.622138703515119"
ELITE_7D = [
    a(*EH_IG_CAMP,   "BH | Tips & Treatments",    13.79, []),
    a(*EH_IG_CAMP,   "TW | Tips & Treatments",    13.96, []),
    a(*EH_BH_CAMP,   "BH | Hip Pain | Lookalike 1.0",  70.97, [(EC,1)]),
    a(*EH_BH_CAMP,   "BH | Shoulder | Lookalike 1.0", 141.17, [(EC,3)]),
    a(*EH_BH_CAMP,   "BH | Glute | Lookalike",        199.01, [(EC,6)]),
    a(*EH_BH_CAMP,   "BH | Shin Splints | Lookalike", 191.49, [(EC,5)]),
    a(*EH_TW_CAMP,   "TW | Low Back | Lookalike",     121.95, []),
    a(*EH_TW_CAMP,   "TW | Hip Pain | Lookalike 1.1", 197.55, [(EC,7)]),
    a(*EH_TW_CAMP,   "TW | Knee | Lookalike",         205.80, []),
    a(*EH_COOP_CAMP, "COOP | Shoulder | Lookalike",    56.66, []),
    ("120244514163190656", "Instagram post: That tight, locked-up feeling...",
     "Instagram post: That tight, locked-up feeling...", "44.49", []),
]
# Fix the boosted post row (it's not using the a() helper shape, fix it):
ELITE_7D[-1] = {
    "campaign_id": "120244514163190656",
    "campaign_name": "Instagram post: That tight, locked-up feeling...",
    "adset_name": "Instagram post: That tight, locked-up feeling...",
    "spend": "44.49",
    "actions": [],
}

ELITE_14D = [
    a(*EH_IG_CAMP,   "BH | Tips & Treatments",         26.47, [(EC,1)]),
    a(*EH_IG_CAMP,   "TW | Tips & Treatments",         26.82, []),
    a(*EH_BH_CAMP,   "BH | Hip Pain | Lookalike 1.0",  135.89, [(EC,2)]),
    a(*EH_BH_CAMP,   "BH | Shoulder | Lookalike 1.0",  271.46, [(EC,6)]),
    a(*EH_BH_CAMP,   "BH | Glute | Lookalike",          382.76, [(EC,10)]),
    a(*EH_BH_CAMP,   "BH | Shin Splints | Lookalike",  368.31, [(EC,9)]),
    a(*EH_BH_CAMP,   "BH | Knee | Lookalike",          135.89, [(EC,1)]),
    a(*EH_TW_CAMP,   "TW | Low Back | Lookalike",       234.50, [(EC,2)]),
    a(*EH_TW_CAMP,   "TW | Hip Pain | Lookalike 1.1",  380.25, [(EC,10)]),
    a(*EH_TW_CAMP,   "TW | Knee | Lookalike",          395.33, [(EC,3)]),
    a(*EH_COOP_CAMP, "COOP | Shoulder | Lookalike",    108.93, []),
    # boosted post ~$44 spend 0 conv (not in 14d, appeared mid-June):
]

ELITE_MAY = [
    a(*EH_IG_CAMP,   "BH | Tips & Treatments",       61.92, []),
    a(*EH_IG_CAMP,   "TW | Tips & Treatments",       62.28, [(EC,2)]),
    a(*EH_BH_CAMP,   "BH | Shoulder | Lookalike 1.0", 616.93, [(EC,8)]),
    a(*EH_BH_CAMP,   "BH | Glute | Lookalike",        822.80, [(EC,18)]),
    a(*EH_BH_CAMP,   "BH | Shin Splints | Lookalike", 625.64, [(EC,15)]),
    a(*EH_BH_CAMP,   "BH | Knee | Lookalike",         862.20, [(EC,12)]),
    a(*EH_TW_CAMP,   "TW | Low Back | Lookalike",     494.09, [(EC,6)]),
    a(*EH_TW_CAMP,   "TW | Shin Splints | Lookalike", 126.22, [(EC,1)]),
    a(*EH_TW_CAMP,   "TW | Hip Pain | Lookalike 1.1", 524.33, [(EC,9)]),
    a(*EH_TW_CAMP,   "TW | Knee | Lookalike",         935.87, [(EC,21)]),
    a(*EH_COOP_CAMP, "COOP | Knee | Lookalike",       213.62, []),
    a(*EH_COOP_CAMP, "COOP | Hip | Lookalike",         57.57, []),
    a(*EH_COOP_CAMP, "COOP | Shoulder | Lookalike",   245.89, [(EC,6)]),
    {"campaign_id": "120240830566250656",
     "campaign_name": "Instagram post: Lower back pain...",
     "adset_name": "Instagram Post", "spend": "57.56", "actions": []},
]

ELITE_PRIOR_7D  = ([(EC,22)], 1154.76)
ELITE_PRIOR_14D = ([(EC,44)], 2412.55)
ELITE_PRIOR_MAY = ([(EC,119)], 6615.75)

# ── STEPZ FITNESS (act_887644738898147) ──────────────────────────────────────
SZ = "offsite_conversion.custom.659111897025738"
STEPZ_7D = [
    a(*STEPZ_CAMP, "General | Australia | Adv+ 4.0", 285.35,
      [("onsite_conversion.lead_grouped",2)]),
]
STEPZ_14D = [
    a(*STEPZ_CAMP, "General | Australia | Adv+ 4.0", 563.96,
      [("lead",5),("onsite_conversion.lead_grouped",4),
       ("offsite_conversion.fb_pixel_lead",1),(SZ,1)]),
]
STEPZ_MAY = [
    a(*STEPZ_CAMP, "General | Australia | Adv+ 2.0", 480.00,
      [("lead",5),("onsite_conversion.lead_grouped",1),
       ("offsite_conversion.fb_pixel_lead",4),(SZ,1)]),
    a(*STEPZ_CAMP, "Retargeting",                    250.00,
      [("lead",3),("offsite_conversion.fb_pixel_lead",3)]),
    a(*STEPZ_CAMP, "Brightwater",                    470.00,
      [("lead",6),("offsite_conversion.fb_pixel_lead",6)]),
    a(*STEPZ_CAMP, "General | Australia | Adv+ 4.0", 579.56,
      [("lead",10),("onsite_conversion.lead_grouped",8),
       ("offsite_conversion.fb_pixel_lead",2),(SZ,1)]),
]
STEPZ_PRIOR_7D  = ([("onsite_conversion.lead_grouped",2)], 278.61)
STEPZ_PRIOR_14D = ([("lead",12),("onsite_conversion.lead_grouped",6),
                    ("offsite_conversion.fb_pixel_lead",6)], 883.76)
STEPZ_PRIOR_MAY = ([("lead",32),("onsite_conversion.lead_grouped",11),
                    ("offsite_conversion.fb_pixel_lead",21),(SZ,7)], 2494.66)


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD META CACHE
# Keys: "2026-06-08_2026-06-14" | "2026-06-01_2026-06-14" | "2026-05-01_2026-05-31"
# ═══════════════════════════════════════════════════════════════════════════════

def prior_acts(kv_list):
    return [{"action_type": k, "value": str(v)} for k, v in kv_list]

meta_cache = {
    "act_1405008824620416": {
        "2026-06-08_2026-06-14": build_from_adsets(APLUS_7D,  prior_acts(APLUS_PRIOR_7D[0]),  APLUS_PRIOR_7D[1]),
        "2026-06-01_2026-06-14": build_from_adsets(APLUS_14D, prior_acts(APLUS_PRIOR_14D[0]), APLUS_PRIOR_14D[1]),
        "2026-05-01_2026-05-31": build_from_adsets(APLUS_MAY, prior_acts(APLUS_PRIOR_MAY[0]), APLUS_PRIOR_MAY[1]),
    },
    "act_851463511303862": {
        "2026-06-08_2026-06-14": build_from_adsets(REGEN_7D,  prior_acts(REGEN_PRIOR_7D[0]),  REGEN_PRIOR_7D[1]),
        "2026-06-01_2026-06-14": build_from_adsets(REGEN_14D, prior_acts(REGEN_PRIOR_14D[0]), REGEN_PRIOR_14D[1]),
        "2026-05-01_2026-05-31": build_from_adsets(REGEN_MAY, prior_acts(REGEN_PRIOR_MAY[0]), REGEN_PRIOR_MAY[1]),
    },
    "act_631477383077560": {
        "2026-06-08_2026-06-14": build_from_adsets(SUMMIT_7D,  prior_acts(SUMMIT_PRIOR_7D[0]),  SUMMIT_PRIOR_7D[1]),
        "2026-06-01_2026-06-14": build_from_adsets(SUMMIT_14D, prior_acts(SUMMIT_PRIOR_14D[0]), SUMMIT_PRIOR_14D[1]),
        "2026-05-01_2026-05-31": build_from_adsets(SUMMIT_MAY, prior_acts(SUMMIT_PRIOR_MAY[0]), SUMMIT_PRIOR_MAY[1]),
    },
    "act_718379509811221": {
        "2026-06-08_2026-06-14": build_from_adsets(HEID_7D,  prior_acts(HEID_PRIOR_7D[0]),  HEID_PRIOR_7D[1]),
        "2026-06-01_2026-06-14": build_from_adsets(HEID_14D, prior_acts(HEID_PRIOR_14D[0]), HEID_PRIOR_14D[1]),
        "2026-05-01_2026-05-31": build_from_adsets(HEID_MAY, prior_acts(HEID_PRIOR_MAY[0]), HEID_PRIOR_MAY[1]),
    },
    "act_488804362788988": {
        "2026-06-08_2026-06-14": build_from_adsets(ELITE_7D,  prior_acts(ELITE_PRIOR_7D[0]),  ELITE_PRIOR_7D[1]),
        "2026-06-01_2026-06-14": build_from_adsets(ELITE_14D, prior_acts(ELITE_PRIOR_14D[0]), ELITE_PRIOR_14D[1]),
        "2026-05-01_2026-05-31": build_from_adsets(ELITE_MAY, prior_acts(ELITE_PRIOR_MAY[0]), ELITE_PRIOR_MAY[1]),
    },
    "act_887644738898147": {
        "2026-06-08_2026-06-14": build_from_adsets(STEPZ_7D,  prior_acts(STEPZ_PRIOR_7D[0]),  STEPZ_PRIOR_7D[1]),
        "2026-06-01_2026-06-14": build_from_adsets(STEPZ_14D, prior_acts(STEPZ_PRIOR_14D[0]), STEPZ_PRIOR_14D[1]),
        "2026-05-01_2026-05-31": build_from_adsets(STEPZ_MAY, prior_acts(STEPZ_PRIOR_MAY[0]), STEPZ_PRIOR_MAY[1]),
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# BUILD GOOGLE CACHE
# google_cache_pull.py keys: customer_id → date_key → {spend,conversions,...}
# ═══════════════════════════════════════════════════════════════════════════════

def g(spend, conv, breakdown, campaign_name="Google Search"):
    cpc = round(spend / conv, 2) if conv else 0.0
    campaign = {
        "name": campaign_name,
        "spend": round(spend, 2),
        "conversions": round(conv, 2),
        "cost_per_conv": cpc,
        "adsets": [],
    }
    return {
        "spend": round(spend, 2),
        "conversions": round(conv, 2),
        "cost_per_conv": cpc,
        "breakdown": breakdown,
        "prior": {"conversions": 0, "cost_per_conv": 0.0, "spend": 0.0},
        "campaigns": [campaign],
    }

google_cache = {
    "1519461427": {   # A Plus Physio — Nookal bookings
        "2026-06-08_2026-06-14": g(146.70, 3,  [{"name": "Booking", "conversions": 3}]),
        "2026-06-01_2026-06-14": g(301.97, 5,  [{"name": "Booking", "conversions": 5}]),
        "2026-05-01_2026-05-31": g(563.44, 10, [{"name": "Booking", "conversions": 10}]),
    },
    "2080537843": {   # Regen Health — Splose bookings + form submissions
        "2026-06-08_2026-06-14": g(186.78, 2,  [{"name": "Booking", "conversions": 1}, {"name": "Form", "conversions": 1}]),
        "2026-06-01_2026-06-14": g(393.57, 6,  [{"name": "Booking", "conversions": 3}, {"name": "Form", "conversions": 3}]),
        "2026-05-01_2026-05-31": g(602.22, 5,  [{"name": "Booking", "conversions": 3}, {"name": "Form", "conversions": 2}]),
    },
    "3650022070": {   # Summit Chiro — Cliniko bookings
        "2026-06-08_2026-06-14": g(55.71,  1,  [{"name": "Booking", "conversions": 1}]),
        "2026-06-01_2026-06-14": g(93.62,  3,  [{"name": "Booking", "conversions": 3}]),
        "2026-05-01_2026-05-31": g(308.28, 8,  [{"name": "Booking", "conversions": 8}]),
    },
    "6443816223": {   # Heidelberg Osteopaths — Cliniko bookings + ext calls (10:2 ratio in 7d)
        "2026-06-08_2026-06-14": g(387.40,  12,    [{"name": "Booking", "conversions": 10}, {"name": "Call", "conversions": 2}]),
        "2026-06-01_2026-06-14": g(914.58,  30.94, [{"name": "Booking", "conversions": 26}, {"name": "Call", "conversions": 4.94}]),
        "2026-05-01_2026-05-31": g(1375.48, 57.99, [{"name": "Booking", "conversions": 48}, {"name": "Call", "conversions": 9.99}]),
    },
}

# Write files
meta_path   = GEN / "meta_cache.json"
google_path = GEN / "google_cache.json"

meta_path.write_text(json.dumps(meta_cache, indent=2))
google_path.write_text(json.dumps(google_cache, indent=2))

print("✓ meta_cache.json written")
print("✓ google_cache.json written")

# Quick sanity check
for acc, periods in meta_cache.items():
    for k, v in periods.items():
        print(f"  {acc[-12:]} {k}: {v['conversions']} conv  ${v['spend']}  CPL ${v['cost_per_conv']}")
