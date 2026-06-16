"""
Serves Google Ads data cached from a Pipeboard MCP pull.
Used automatically when GOOGLE_DEVELOPER_TOKEN is not configured.
To refresh: pull fresh data via Pipeboard and update google_cache.json.
"""
import json
from datetime import date
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "google_cache.json"


def pull(customer_id: str, period_start: date, period_end: date) -> dict:
    cache = json.loads(CACHE_FILE.read_text())
    key = f"{period_start}_{period_end}"
    data = cache.get(customer_id, {}).get(key)
    if data is None:
        raise RuntimeError(
            f"No cached Google data for {customer_id} {period_start}→{period_end}. "
            "Update google_cache.json with a fresh Pipeboard pull."
        )
    return {
        "client": customer_id,
        "platform": "google",
        "spend": data["spend"],
        "conversions": data["conversions"],
        "cost_per_conv": data["cost_per_conv"],
        "breakdown": data["breakdown"],
        "prior": data["prior"],
        "campaigns": data.get("campaigns", []),
    }
