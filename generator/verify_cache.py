#!/usr/bin/env python3
"""
Independent cache validator — the publish gate.

Re-checks each cache entry actually used by a render:
  1. campaign rows sum to the entry totals (internal consistency)
  2. entry totals match the independently-pulled account_check (reconciliation)
  3. entry is flagged verified, and has a pulled_at date

Returns (ok, errors). run.py calls verify() before rendering and refuses to
publish if it fails. Can also be run standalone: `python verify_cache.py`.
"""
import json
import sys
from pathlib import Path

GEN = Path(__file__).parent
SPEND_TOL = 1.00
CONV_TOL = 0.05


def _check_entry(who, e):
    errs = []
    camp_spend = round(sum(c.get("spend", 0) for c in e.get("campaigns", [])), 2)
    camp_conv = round(sum(c.get("conversions", 0) for c in e.get("campaigns", [])), 2)

    # 1. campaigns sum to entry totals
    if abs(camp_spend - e["spend"]) > SPEND_TOL:
        errs.append(f"{who}: campaign spend Σ${camp_spend} ≠ entry ${e['spend']}")
    if abs(camp_conv - e["conversions"]) > CONV_TOL:
        errs.append(f"{who}: campaign conv Σ{camp_conv} ≠ entry {e['conversions']}")

    # 2. entry totals reconcile to independent account_check
    ac = e.get("account_check")
    if not ac:
        errs.append(f"{who}: missing account_check — cannot verify")
    else:
        if abs(e["spend"] - ac["spend"]) > max(SPEND_TOL, 0.01 * ac["spend"]):
            errs.append(f"{who}: spend ${e['spend']} ≠ account ${ac['spend']}")
        if abs(e["conversions"] - ac["conversions"]) > CONV_TOL:
            errs.append(f"{who}: conv {e['conversions']} ≠ account {ac['conversions']}")

    # 3. verified flag + freshness stamp present
    if not e.get("verified"):
        errs.append(f"{who}: not marked verified")
    if not e.get("pulled_at"):
        errs.append(f"{who}: missing pulled_at")
    return errs


def verify(keys=None):
    """Validate both caches. keys: optional list of date-keys to limit to."""
    errors = []
    for fname, plat in (("google_cache.json", "G"), ("meta_cache.json", "M")):
        path = GEN / fname
        if not path.exists():
            errors.append(f"{fname} missing")
            continue
        cache = json.loads(path.read_text())
        for acc, periods in cache.items():
            for k, e in periods.items():
                if keys and k not in keys:
                    continue
                errors.extend(_check_entry(f"{plat}:{acc[-6:]}:{k}", e))
    return (len(errors) == 0), errors


if __name__ == "__main__":
    ok, errors = verify()
    if ok:
        print("✓ cache verified — all entries reconcile to account totals")
        sys.exit(0)
    print("✗ cache verification FAILED:", file=sys.stderr)
    for e in errors:
        print(f"   {e}", file=sys.stderr)
    sys.exit(1)
