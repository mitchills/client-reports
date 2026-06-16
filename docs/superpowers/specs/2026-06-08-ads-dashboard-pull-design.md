# Ads Dashboard Pull — Design

**Date:** 2026-06-08
**Owner:** Mitch (Mastered Marketing)
**Status:** Approved, pre-implementation

## Goal

Populate the existing encrypted client dashboard (https://mitchills.github.io/client-reports/)
with live Google Ads + Meta Ads data for ~50 accounts, **for free**, replacing Pipeboard
(~$500 USD/mo at scale, and currently blocked from adding accounts pending allow-list/upgrade).

Out of scope for now: the remote "Weekly Ad Check" routine, and any write/optimisation
features (AdTurbo replacement). The build is architected so write can be added later using
the same credentials, but none of it is built in this effort.

## Key decision (settled in prior thread)

Integrate **once at the manager level**, not per-account:

- **Google Ads:** Google Ads API via the **MCC** + one approved **developer token**. Covers
  every account under the MCC, including future clients. `login_customer_id` = the MCC ID.
- **Meta:** Marketing API via one **Business Manager system-user token** (long-lived). Covers
  every ad account the BM manages.
- Data from both APIs is free. One-off setup covers all clients forever; only the Google
  developer-token application + light yearly API-version upkeep are ongoing.

## Architecture — Approach A: direct API pull script

Everything runs locally on Mitch's machine. No hosted server, no monthly cost.

Lives inside the existing `~/client-reports` repo in a new `generator/` folder. Generator code
is safe to keep in the repo (contains no secrets). Secrets live in `generator/.env`, which is
**gitignored** so they are never published. The published site is already public + encrypted.

### Components

| File | Purpose | Depends on |
|------|---------|------------|
| `generator/clients.json` | List of ~50 clients: friendly name → Google customer ID + Meta `act_` ID. The only file Mitch edits to add a client. | — |
| `generator/.env` (gitignored) | Google dev token + OAuth (client_id, client_secret, refresh_token, login_customer_id); Meta system-user token. Set once. | — |
| `generator/google_pull.py` | One GAQL query per account via the MCC: spend, conversions, cost/conv, conversion breakdown by conversion action, current period + prior period. Returns a normalised per-client dict. | `.env`, `clients.json` |
| `generator/meta_pull.py` | Same metrics per account via the BM Insights API. Returns the same normalised shape. | `.env`, `clients.json` |
| `generator/render.py` | Fills the recovered HTML template with the pulled data, re-encrypts with StatiCrypt, writes `index.html`, commits + pushes. | template, pull output |
| `generator/run.py` | Orchestrator. The one thing Mitch runs. Logs in once per platform, loops clients, pulls both, renders, publishes. | all of the above |

### Data flow

```
run.py
  → auth Google MCC (once) + Meta BM (once)
  → for each client in clients.json:
        google_pull.py  →  { spend, conversions, cost_per_conv, breakdown, prior_period }
        meta_pull.py    →  { spend, conversions, cost_per_conv, breakdown, prior_period }
  → merge into per-client rows
  → render.py: template + rows → index.html → StatiCrypt encrypt → git commit + push
  → live dashboard updated
```

### Normalised per-client shape (contract between pull and render)

Both pull modules return this so `render.py` doesn't care which platform produced it:

```json
{
  "client": "A Plus",
  "platform": "google | meta",
  "spend": 0.0,
  "conversions": 0.0,
  "cost_per_conv": 0.0,
  "breakdown": [{ "name": "Phone Calls", "conversions": 0.0 }],
  "prior": { "conversions": 0.0, "cost_per_conv": 0.0 }
}
```

## Dashboard template constraint

The live `index.html` is StatiCrypt-encrypted (AES-256-CBC) with **no plaintext source kept
anywhere**. Before anything can render, decrypt it **once** (Mitch provides the password) to
recover the clean HTML, then turn the client-row section into a fill-in template.

Layout rules to preserve (from prior work):
- Keep `.wrap` max-width at **960px** (760px makes the client name wrap and the breakdown stack).
- Inter font, expandable client rows, conversion breakdown.
- Data is rendered per-snapshot; prior-period *results* deltas require a live prior-week pull
  (handled by the `prior` field above).

Re-encrypt with: `npx staticrypt <file> -p <pw> --salt <salt> --remember 30 -c false`
(salt from `.staticrypt.json`). Password is Mitch's to provide; never stored.

## One-time prerequisites (Mitch's homework)

1. **Recover the template** — provide the dashboard password so the current `index.html` can be
   decrypted once into a reusable template. **Blocks everything else.**
2. **Google Ads developer token** — apply through the MCC (Tools → API Center). Approval takes
   a few days (the long-pole). Free "basic access" tier daily op cap is far above what 50
   accounts of reporting needs. Also need an OAuth client + refresh token (one-time setup).
3. **Meta system-user token** — generate in Business Manager (Business Settings → System Users
   → add → generate token with `ads_read`). ~5 minutes, self-serve.

## Build order

1. Recover template (needs password).
2. Acquire credentials (Google dev token is the wait; Meta is quick).
3. Build + test `google_pull.py` on **A Plus** (Google 151-946-1427) — the one account already
   reachable today via Pipeboard, useful for validating numbers.
4. Add `meta_pull.py` (A Plus `act_1405008824620416`).
5. Build `render.py` + encrypt + publish; verify one-client dashboard end to end.
6. Load all ~50 clients into `clients.json`, run `run.py`, verify full dashboard.

## Tech choices

- **Python** — both Google (`google-ads`) and Meta (`facebook-business`) ship official Python
  libraries. Path of least resistance.
- **Secrets** — `.env` via `python-dotenv`, gitignored. Never committed, never printed.

## Risks / notes

- Google dev token approval delay — start the application first.
- Conversion-action naming differs per account; breakdown must read action names dynamically,
  not a hardcoded list.
- Google reports in account currency; confirm all accounts are AUD or normalise.
- This is read-only now but reuses the same auth if write is added later (AdTurbo replacement).
