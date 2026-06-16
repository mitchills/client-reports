"""
Serves Meta Ads data cached from a Pipeboard MCP pull.
Used when --pipeboard flag is passed to run.py.
To refresh: pull fresh data via Pipeboard and update meta_cache.json.
"""
import json
from datetime import date
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "meta_cache.json"


def pull(account_id: str, period_start: date, period_end: date) -> dict:
    cache = json.loads(CACHE_FILE.read_text())
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"
    key = f"{period_start}_{period_end}"
    data = cache.get(account_id, {}).get(key)
    if data is None:
        raise RuntimeError(
            f"No cached Meta data for {account_id} {period_start}→{period_end}. "
            "Update meta_cache.json with a fresh Pipeboard pull."
        )
    return {
        "client": account_id,
        "platform": "meta",
        "spend": data["spend"],
        "conversions": data["conversions"],
        "cost_per_conv": data["cost_per_conv"],
        "breakdown": data["breakdown"],
        "prior": data["prior"],
        "campaigns": data.get("campaigns", []),
    }
