"""
Orchestrator — the one thing Mitch runs.
Usage: python run.py [--ref YYYY-MM-DD] [--pipeboard]
  --ref       reference end date for "last 7 days" (default: yesterday)
  --pipeboard use Pipeboard-cached data for both Google and Meta
              (reads google_cache.json + meta_cache.json, skips live SDK calls)
"""

import argparse
import calendar
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import google_pull
import meta_pull
from render import merge_client, render_and_publish

CLIENTS_FILE = Path(__file__).parent / "clients.json"


def compute_periods(ref: date) -> list[dict]:
    """Return the three periods to pull, each with start/end dates and a display label."""
    # Last 7 days: ref-6 → ref
    p7_end = ref
    p7_start = ref - timedelta(days=6)

    # Last 14 days: ref-13 → ref
    p14_end = ref
    p14_start = ref - timedelta(days=13)

    # Last month: full previous calendar month
    first_of_this_month = ref.replace(day=1)
    lm_end = first_of_this_month - timedelta(days=1)
    lm_start = lm_end.replace(day=1)

    def fmt(d): return d.strftime("%-d %b %Y")

    # Current month: 1st of ref's month to ref
    cm_start = ref.replace(day=1)
    cm_end = ref

    return [
        {"key": "7d",    "label": "Last 7 days",    "start": p7_start,  "end": p7_end,  "date_str": f"{fmt(p7_start)} – {fmt(p7_end)}"},
        {"key": "14d",   "label": "Last 14 days",   "start": p14_start, "end": p14_end, "date_str": f"{fmt(p14_start)} – {fmt(p14_end)}"},
        {"key": "mtd",   "label": "This month",     "start": cm_start,  "end": cm_end,  "date_str": f"{fmt(cm_start)} – {fmt(cm_end)}"},
        {"key": "month", "label": "Last month",     "start": lm_start,  "end": lm_end,  "date_str": f"{fmt(lm_start)} – {fmt(lm_end)}"},
    ]


def pull_period(period: dict, clients: list, g_client, google_ready: bool, g_fallback=None) -> list[dict]:
    """Pull all clients for a single period. Returns list of merged client dicts."""
    results = []
    errors = []

    for c in clients:
        name = c["name"]
        pulls = []

        if (google_ready or g_fallback) and c.get("google_customer_id"):
            try:
                if google_ready:
                    result = google_pull.pull(g_client, c["google_customer_id"], period["start"], period["end"])
                else:
                    result = g_fallback(c["google_customer_id"], period["start"], period["end"])
                pulls.append(result)
            except Exception as e:
                errors.append(f"{name} Google: {e}")

        if c.get("meta_account_id"):
            try:
                result = meta_pull.pull(c["meta_account_id"], period["start"], period["end"])
                pulls.append(result)
            except Exception as e:
                errors.append(f"{name} Meta: {e}")

        if pulls:
            results.append(merge_client(name, pulls))

    if errors:
        for e in errors:
            print(f"  ⚠ {e}")

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref", help="Reference end date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--pipeboard", action="store_true", help="Use Pipeboard-cached data for both Google and Meta")
    args = parser.parse_args()

    ref = (
        date.fromisoformat(args.ref) if args.ref
        else date.today() - timedelta(days=1)
    )

    periods = compute_periods(ref)

    if args.pipeboard:
        pipeboard_clients_file = Path(__file__).parent / "clients_pipeboard.json"
        clients = json.loads(pipeboard_clients_file.read_text())
        print("Pipeboard mode — loading clients_pipeboard.json")
    else:
        clients = json.loads(CLIENTS_FILE.read_text())

    google_ready = (not args.pipeboard) and os.environ.get("GOOGLE_DEVELOPER_TOKEN", "PENDING") != "PENDING"
    g_client = google_pull.build_client() if google_ready else None
    g_fallback = None
    if not google_ready:
        try:
            import google_cache_pull
            g_fallback = google_cache_pull.pull
            if not args.pipeboard:
                print("Google credentials not set — using cached Pipeboard data.")
        except ImportError:
            print("Google credentials not set — skipping Google pulls.")

    if args.pipeboard:
        import meta_cache_pull as _meta_cache
        meta_pull.pull = _meta_cache.pull  # swap in cache-backed puller
        print("Pipeboard mode — Meta data served from meta_cache.json")
    else:
        meta_pull.init()

    all_periods = []
    for period in periods:
        print(f"Pulling {period['label']} ({period['date_str']}) …")
        clients_data = pull_period(period, clients, g_client, google_ready, g_fallback)
        if not clients_data:
            print(f"  No data for {period['label']} — skipping.")
            continue
        all_periods.append({**period, "clients": clients_data})

    if not all_periods:
        print("No data pulled — aborting.", file=sys.stderr)
        sys.exit(1)

    # ── Publish gate: refuse to publish if cache data doesn't reconcile ──
    if args.pipeboard or not google_ready:
        used_keys = [f"{p['start']}_{p['end']}" for p in all_periods]
        import verify_cache
        ok, errors = verify_cache.verify(keys=used_keys)
        if not ok:
            print("✗ PUBLISH BLOCKED — cache failed verification:", file=sys.stderr)
            for e in errors:
                print(f"   {e}", file=sys.stderr)
            print("Dashboard NOT updated. Fix the cache and re-run.", file=sys.stderr)
            sys.exit(1)
        print(f"✓ Verified {len(used_keys)} period(s) — figures reconcile to account totals.")

    print("Rendering and encrypting dashboard …")
    render_and_publish(all_periods)
    print("Done.")


if __name__ == "__main__":
    main()
