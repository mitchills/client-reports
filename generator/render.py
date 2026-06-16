"""
Merge pull data → fill template → encrypt → write index.html.
"""

import os
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, pass_eval_context

STALE_AFTER_DAYS = 8  # data older than this is flagged stale on the dashboard

GENERATOR_DIR = Path(__file__).parent
REPO_DIR = GENERATOR_DIR.parent
TEMPLATE_FILE = GENERATOR_DIR / "template.html"
OUTPUT_FILE = REPO_DIR / "index.html"
SALT = "ab7a22e4bbc324ecfe0649ee39a1ef27"


# ── Jinja2 filter ──────────────────────────────────────────────────────────────

def aud_filter(value):
    if value is None:
        return "—"
    return f"${value:,.2f}"


# ── Delta helpers ──────────────────────────────────────────────────────────────

def _pct_change(current, prior):
    if not prior:
        return None
    return round((current - prior) / prior * 100, 1)


def _delta_str(pct):
    if pct is None:
        return "n/a"
    sign = "+" if pct > 0 else ("−" if pct < 0 else "")
    return f"{sign}{abs(pct):.0f}%"


def _conv_delta_class(pct):
    if pct is None or (-5 < pct < 5):
        return "delta-flat"
    return "delta-down" if pct < 0 else "delta-up"


def _cpc_delta_class(pct):
    if pct is None or (-5 < pct < 5):
        return "delta-flat"
    # higher cost/conv = bad
    return "delta-cost-up" if pct > 0 else "delta-cost-down"


def _status(conv_pct):
    if conv_pct is None:
        return "ok", "Stable"
    if conv_pct <= -10:
        return "bad", "Needs attention"
    if conv_pct >= 10:
        return "good", "On track"
    return "ok", "Stable"


def _attention_note(conv_pct, cpc_pct):
    """One-liner shown at the top of a 'Needs attention' client detail."""
    if conv_pct is None:
        return None
    parts = []
    if conv_pct <= -10:
        parts.append(f"results down {abs(conv_pct):.0f}%")
    if cpc_pct is not None and cpc_pct >= 10:
        parts.append(f"cost per result up {abs(cpc_pct):.0f}%")
    if not parts:
        return None
    return " and ".join(parts).capitalize() + " vs the prior period."


# ── Data-quality flag ────────────────────────────────────────────────────────

def _data_flag(pulls: list[dict]) -> dict:
    """
    Worst-case trust signal across a client's platform pulls.
    error = a pull failed reconciliation (don't trust the number).
    stale = data older than STALE_AFTER_DAYS.
    """
    level = None  # None < stale < error
    notes = []
    for p in pulls:
        plat = p["platform"].capitalize()
        if not p.get("verified", False):
            level = "error"
            notes.append(f"{plat} unverified")
            continue
        pulled = p.get("pulled_at")
        if pulled:
            try:
                age = (date.today() - datetime.strptime(pulled, "%Y-%m-%d").date()).days
                if age > STALE_AFTER_DAYS and level != "error":
                    level = "stale"
                    notes.append(f"{plat} {age}d old")
            except ValueError:
                pass
        if p.get("note"):
            notes.append(f"{plat}: {p['note']}")
    if level is None and not notes:
        return {"level": None, "label": "", "note": ""}
    label = {"error": "⚠ Data error", "stale": "⚠ Stale"}.get(level, "⚠ Check")
    return {"level": level, "label": label, "note": "; ".join(notes)}


# ── Data merge ─────────────────────────────────────────────────────────────────

def merge_client(name: str, pulls: list[dict]) -> dict:
    """
    pulls: list of dicts from google_pull.pull() and/or meta_pull.pull()
    Returns a fully rendered context dict for the template.
    """
    total_spend = sum(p["spend"] for p in pulls)
    total_conv = sum(p["conversions"] for p in pulls)
    total_cpc = (total_spend / total_conv) if total_conv else 0.0

    prior_conv = sum(p["prior"]["conversions"] for p in pulls)
    prior_spend = sum(p["prior"]["conversions"] * p["prior"]["cost_per_conv"] for p in pulls)
    prior_cpc = (prior_spend / prior_conv) if prior_conv else 0.0

    conv_pct = _pct_change(total_conv, prior_conv)
    cpc_pct = _pct_change(total_cpc, prior_cpc)
    status, status_label = _status(conv_pct)

    platforms = []
    for p in pulls:
        p_prior_conv = p["prior"]["conversions"]
        p_prior_cpc = p["prior"]["cost_per_conv"]
        p_conv_pct = _pct_change(p["conversions"], p_prior_conv)
        p_cpc_pct = _pct_change(p["cost_per_conv"], p_prior_cpc)
        platforms.append({
            "name": p["platform"].capitalize(),
            "conversions": p["conversions"],
            "cost_per_conv": p["cost_per_conv"],
            "spend": p["spend"],
            "conv_delta_class": _conv_delta_class(p_conv_pct),
            "conv_delta_str": _delta_str(p_conv_pct),
            "cpc_delta_class": _cpc_delta_class(p_cpc_pct),
            "cpc_delta_str": _delta_str(p_cpc_pct),
        })

    breakdown = []
    for p in pulls:
        breakdown.append({
            "platform": p["platform"].capitalize(),
            "entries": p["breakdown"],
        })

    # Campaign → adset drill-down, grouped by platform
    campaign_groups = []
    for p in pulls:
        camps = p.get("campaigns", [])
        campaign_groups.append({
            "platform": p["platform"].capitalize(),
            "campaigns": camps,
        })

    return {
        "name": name,
        "total_conversions": total_conv,
        "total_cpc": total_cpc,
        "total_spend": total_spend,
        "conv_delta_class": _conv_delta_class(conv_pct),
        "conv_delta_str": _delta_str(conv_pct),
        "cpc_delta_class": _cpc_delta_class(cpc_pct),
        "cpc_delta_str": _delta_str(cpc_pct),
        "status": status,
        "status_label": status_label,
        "attention_note": _attention_note(conv_pct, cpc_pct) if status == "bad" else None,
        "platforms": platforms,
        "breakdown": breakdown,
        "campaign_groups": campaign_groups,
        "data_flag": _data_flag(pulls),
    }


# ── Render + encrypt ───────────────────────────────────────────────────────────

def render_and_publish(periods: list[dict]):
    """
    periods: list of dicts, each with keys:
      key, label, date_str, clients (list of merged client dicts)
    """
    env = Environment(loader=FileSystemLoader(str(GENERATOR_DIR)))
    env.filters["aud"] = aud_filter
    tmpl = env.get_template("template.html")

    html = tmpl.render(
        periods=periods,
        generated_date=date.today().strftime("%-d %b %Y"),
    )

    # Write plaintext to temp file, encrypt to a separate output dir, then move to index.html
    tmp = REPO_DIR / "_tmp_plain.html"
    enc_dir = REPO_DIR / "_encrypted"
    enc_dir.mkdir(exist_ok=True)
    tmp.write_text(html, encoding="utf-8")

    password = os.environ["STATICRYPT_PASSWORD"]
    result = subprocess.run(
        [
            "npx", "staticrypt", str(tmp),
            "-p", password,
            "--salt", SALT,
            "--remember", "30",
            "-c", "false",
            "--short",
            "-d", str(enc_dir),
        ],
        capture_output=True, text=True, cwd=str(REPO_DIR),
    )

    tmp.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"StatiCrypt failed:\n{result.stderr}")

    encrypted_out = enc_dir / "_tmp_plain.html"
    if not encrypted_out.exists():
        raise RuntimeError(f"StatiCrypt output not found at {encrypted_out}")

    encrypted_out.rename(OUTPUT_FILE)
    enc_dir.rmdir()

    print(f"Dashboard written to {OUTPUT_FILE}")
