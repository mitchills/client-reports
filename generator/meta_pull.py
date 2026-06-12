"""
Pull Meta Ads data for a single ad account for an arbitrary date range.
Returns a normalised dict matching the contract in the spec.
"""

import os
from collections import defaultdict
from datetime import date, timedelta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount


def pull(account_id: str, period_start: date, period_end: date) -> dict:
    """
    account_id:   with or without "act_" prefix
    period_start: first day of reporting window (inclusive)
    period_end:   last day of reporting window (inclusive)
    """
    start = period_start.strftime("%Y-%m-%d")
    end = period_end.strftime("%Y-%m-%d")

    # Prior period = same duration immediately preceding
    duration = (period_end - period_start).days + 1
    prior_end = period_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=duration - 1)

    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"

    account = AdAccount(account_id)

    try:
        custom_convs = account.get_custom_conversions(fields=["id", "name"])
        custom_conv_map = {cc["id"]: cc["name"] for cc in custom_convs}
    except Exception:
        custom_conv_map = {}

    CONVERSION_OBJECTIVES = [
        "OUTCOME_LEADS", "OUTCOME_SALES", "LEAD_GENERATION",
        "CONVERSIONS", "OUTCOME_APP_PROMOTION",
    ]

    CONVERSION_ACTION_TYPES = {
        "lead", "purchase", "complete_registration", "contact",
        "submit_application", "schedule",
        "offsite_conversion.fb_pixel_lead",
        "offsite_conversion.fb_pixel_purchase",
        "offsite_conversion.fb_pixel_complete_registration",
        "onsite_conversion.lead_grouped",
    }

    ACTION_LABELS = {
        "lead": "Lead",
        "purchase": "Purchase",
        "complete_registration": "Registration",
        "contact": "Contact",
        "submit_application": "Application",
        "schedule": "Booking",
        "offsite_conversion.fb_pixel_lead": "Lead",
        "offsite_conversion.fb_pixel_purchase": "Purchase",
        "offsite_conversion.fb_pixel_complete_registration": "Registration",
        "onsite_conversion.lead_grouped": "Lead",
    }

    def friendly_name(action_type: str) -> str:
        if action_type in ACTION_LABELS:
            return ACTION_LABELS[action_type]
        if action_type.startswith("offsite_conversion.custom."):
            conv_id = action_type.split(".")[-1]
            return custom_conv_map.get(conv_id, "Custom Conversion")
        return action_type.replace("_", " ").replace(".", " ").title()

    def is_conversion_action(action_type: str) -> bool:
        return (
            action_type in CONVERSION_ACTION_TYPES
            or action_type.startswith("offsite_conversion.custom.")
        )

    def count_conversions(actions: list) -> tuple[float, list]:
        conversions = 0.0
        breakdown = []
        for action in (actions or []):
            if is_conversion_action(action["action_type"]):
                count = float(action["value"])
                conversions += count
                breakdown.append({"name": friendly_name(action["action_type"]), "conversions": count})
        breakdown.sort(key=lambda x: x["conversions"], reverse=True)
        return conversions, breakdown

    # Current period: adset level for campaign → adset hierarchy
    adset_rows = list(account.get_insights(params={
        "time_range": {"since": start, "until": end},
        "fields": ["campaign_id", "campaign_name", "adset_id", "adset_name", "spend", "actions"],
        "level": "adset",
        "filtering": [{"field": "campaign.objective", "operator": "IN", "value": CONVERSION_OBJECTIVES}],
    }))

    camp_map = {}
    for row in adset_rows:
        cid = row["campaign_id"]
        if cid not in camp_map:
            camp_map[cid] = {"name": row["campaign_name"], "spend": 0.0, "conversions": 0.0, "adsets": []}
        c = camp_map[cid]
        adset_spend = float(row.get("spend", 0))
        adset_conv, _ = count_conversions(row.get("actions", []))
        adset_cpc = (adset_spend / adset_conv) if adset_conv else 0.0
        c["spend"] += adset_spend
        c["conversions"] += adset_conv
        c["adsets"].append({
            "name": row["adset_name"],
            "conversions": round(adset_conv, 1),
            "cost_per_conv": round(adset_cpc, 2),
            "spend": round(adset_spend, 2),
        })

    campaigns = []
    total_spend = 0.0
    total_conversions = 0.0
    for c in camp_map.values():
        c["adsets"].sort(key=lambda x: x["conversions"], reverse=True)
        c["cost_per_conv"] = round((c["spend"] / c["conversions"]) if c["conversions"] else 0.0, 2)
        c["spend"] = round(c["spend"], 2)
        c["conversions"] = round(c["conversions"], 1)
        total_spend += c["spend"]
        total_conversions += c["conversions"]
        campaigns.append(c)
    campaigns.sort(key=lambda x: x["conversions"], reverse=True)

    all_actions: dict[str, float] = defaultdict(float)
    for row in adset_rows:
        for action in (row.get("actions") or []):
            if is_conversion_action(action["action_type"]):
                all_actions[action["action_type"]] += float(action["value"])
    breakdown = sorted(
        [{"name": friendly_name(k), "conversions": v} for k, v in all_actions.items()],
        key=lambda x: x["conversions"], reverse=True,
    )

    cost_per_conv = (total_spend / total_conversions) if total_conversions else 0.0

    # Prior period: account level only
    prior_rows = list(account.get_insights(params={
        "time_range": {"since": prior_start.strftime("%Y-%m-%d"), "until": prior_end.strftime("%Y-%m-%d")},
        "fields": ["spend", "actions"],
        "level": "account",
        "filtering": [{"field": "campaign.objective", "operator": "IN", "value": CONVERSION_OBJECTIVES}],
    }))
    prior_spend, prior_conversions = 0.0, 0.0
    if prior_rows:
        prior_spend = float(prior_rows[0].get("spend", 0))
        prior_conversions, _ = count_conversions(prior_rows[0].get("actions", []))
    prior_cpc = (prior_spend / prior_conversions) if prior_conversions else 0.0

    return {
        "client": account_id,
        "platform": "meta",
        "spend": round(total_spend, 2),
        "conversions": round(total_conversions, 1),
        "cost_per_conv": round(cost_per_conv, 2),
        "breakdown": breakdown,
        "campaigns": campaigns,
        "prior": {
            "conversions": prior_conversions,
            "cost_per_conv": round(prior_cpc, 2),
        },
    }


def init():
    FacebookAdsApi.init(access_token=os.environ["META_ACCESS_TOKEN"])
