"""
Pull one week of Google Ads data for a single customer account via MCC.
Returns a normalised dict matching the contract in the spec.
"""

import os
from datetime import date, timedelta
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException


def _pct_change(current, prior):
    if prior == 0:
        return None
    return round((current - prior) / prior * 100, 1)


def pull(client: GoogleAdsClient, customer_id: str, period_start: date, period_end: date) -> dict:
    """
    customer_id:  plain digits, no dashes (e.g. "1519461427")
    period_start: first day of reporting window (inclusive)
    period_end:   last day of reporting window (inclusive)
    """
    ga_service = client.get_service("GoogleAdsService")
    login_customer_id = os.environ["GOOGLE_LOGIN_CUSTOMER_ID"]

    start = period_start.strftime("%Y-%m-%d")
    end = period_end.strftime("%Y-%m-%d")
    duration = (period_end - period_start).days + 1
    prior_end = period_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=duration - 1)
    prior_end_str = prior_end.strftime("%Y-%m-%d")
    prior_start_str = prior_start.strftime("%Y-%m-%d")

    query = f"""
        SELECT
          segments.conversion_action_name,
          metrics.conversions,
          metrics.cost_micros,
          metrics.average_cost
        FROM conversion_action
        WHERE segments.date BETWEEN '{start}' AND '{end}'
          AND metrics.conversions > 0
    """

    rows = []
    try:
        response = ga_service.search_stream(
            customer_id=customer_id,
            query=query,
            login_customer_id=login_customer_id,
        )
        for row in response:
            rows.append({
                "action": row.segments.conversion_action_name,
                "conversions": row.metrics.conversions,
                "cost_micros": row.metrics.cost_micros,
            })
    except GoogleAdsException as ex:
        raise RuntimeError(f"Google Ads API error for {customer_id}: {ex}") from ex

    total_conversions = sum(r["conversions"] for r in rows)
    total_spend = sum(r["cost_micros"] for r in rows) / 1_000_000
    cost_per_conv = (total_spend / total_conversions) if total_conversions else 0.0

    breakdown = [
        {"name": r["action"], "conversions": r["conversions"]}
        for r in sorted(rows, key=lambda x: x["conversions"], reverse=True)
    ]

    # Prior period
    prior_query = f"""
        SELECT
          metrics.conversions,
          metrics.cost_micros
        FROM customer
        WHERE segments.date BETWEEN '{prior_start_str}' AND '{prior_end_str}'
    """
    prior_conversions, prior_spend = 0.0, 0.0
    try:
        prior_response = ga_service.search(
            customer_id=customer_id,
            query=prior_query,
            login_customer_id=login_customer_id,
        )
        for row in prior_response:
            prior_conversions += row.metrics.conversions
            prior_spend += row.metrics.cost_micros / 1_000_000
    except GoogleAdsException:
        pass  # prior period failure is non-fatal; deltas will show as None

    prior_cpc = (prior_spend / prior_conversions) if prior_conversions else 0.0

    return {
        "client": customer_id,
        "platform": "google",
        "spend": round(total_spend, 2),
        "conversions": total_conversions,
        "cost_per_conv": round(cost_per_conv, 2),
        "breakdown": breakdown,
        "prior": {
            "conversions": prior_conversions,
            "cost_per_conv": round(prior_cpc, 2),
        },
    }


def build_client() -> GoogleAdsClient:
    config = {
        "developer_token": os.environ["GOOGLE_DEVELOPER_TOKEN"],
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
        "login_customer_id": os.environ["GOOGLE_LOGIN_CUSTOMER_ID"],
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(config)
