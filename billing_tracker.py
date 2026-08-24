#!/usr/bin/env python3
"""
Multi-Provider Billing Tracker for Shadowfax

Queries live billing/usage APIs from:
  - OpenRouter: /api/v1/key (works - MTD spend available)
  - HuggingFace: No public billing API found (requires web dashboard scraping)
  - Anthropic:   No billing API; no ANTHROPIC_API_KEY in config

Output JSON: {anthropic: {...}, openrouter: {...}, huggingface: {...}}
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# ── Paths ────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
OUTPUT_FILE = Path(__file__).parent / "billing_status.json"


def load_env_keys():
    """Load API keys from openclaw.json"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return {
            "anthropic": config.get("env", {}).get("ANTHROPIC_API_KEY"),
            "openrouter": config.get("env", {}).get("OPENROUTER_API_KEY"),
            "huggingface": config.get("env", {}).get("HF_TOKEN"),
        }
    except Exception as e:
        print(f"[billing_tracker] Failed to load config: {e}")
        return {"anthropic": None, "openrouter": None, "huggingface": None}


# ── Provider: OpenRouter ──────────────────────────────────────────────────────
def fetch_openrouter():
    """
    OpenRouter /api/v1/key endpoint - WORKS.
    Returns: {mtd_spend, limit, currency, usage_daily, usage_weekly, usage_monthly,
              limit_remaining, total_credits, error}
    """
    key = load_env_keys()["openrouter"]
    if not key:
        return {"mtd_spend": None, "limit": None, "currency": "USD",
                "error": "OPENROUTER_API_KEY not found in openclaw.json env"}

    try:
        # Primary: /api/v1/key - gives limit, remaining, and usage breakdowns
        r = requests.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        if r.status_code != 200:
            return {"mtd_spend": None, "limit": None, "currency": "USD",
                    "error": f"HTTP {r.status_code}: {r.text[:200]}"}

        data = r.json().get("data", {})
        limit = data.get("limit")          # e.g. 20 (weekly USD limit)
        mtd = data.get("usage_monthly")    # MTD spend in USD
        weekly = data.get("usage_weekly")  # weekly spend (current billing cycle)
        limit_remaining = data.get("limit_remaining")  # credits left

        # OpenRouter limit resets weekly, so usage_monthly IS the best MTD proxy
        result = {
            "mtd_spend": mtd,
            "limit": limit,
            "limit_remaining": limit_remaining,
            "currency": "USD",
            "usage_daily": data.get("usage_daily"),
            "usage_weekly": weekly,
            "usage_monthly": mtd,
            "limit_reset": data.get("limit_reset"),  # e.g. "weekly"
            "total_credits": None,
            "error": None,
        }

        # Supplement: /api/v1/credits - gives total credits
        try:
            rc = requests.get(
                "https://openrouter.ai/api/v1/credits",
                headers={"Authorization": f"Bearer {key}"},
                timeout=10,
            )
            if rc.status_code == 200:
                cd = rc.json().get("data", {})
                result["total_credits"] = cd.get("total_credits")
                result["lifetime_usage"] = cd.get("total_usage")
        except Exception:
            pass  # Non-critical supplement

        return result

    except requests.RequestException as e:
        return {"mtd_spend": None, "limit": None, "currency": "USD",
                "error": f"Request failed: {e}"}


# ── Provider: HuggingFace ─────────────────────────────────────────────────────
def fetch_huggingface():
    """
    HuggingFace has NO public billing/usage API.
    The whoami-v2 endpoint reveals billingMode but NOT MTD spend.
    Returns: {mtd_spend, limit, currency, billing_mode, period_end, error}
    """
    key = load_env_keys()["huggingface"]
    if not key:
        return {"mtd_spend": None, "limit": None, "currency": "USD",
                "error": "HF_TOKEN not found in openclaw.json env"}

    try:
        r = requests.get(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        if r.status_code != 200:
            return {"mtd_spend": None, "limit": None, "currency": "USD",
                    "error": f"HTTP {r.status_code}: {r.text[:200]}"}

        data = r.json()
        billing_mode = data.get("billingMode")  # "prepaid" | "subscription"
        period_end = data.get("periodEnd")      # Unix timestamp
        is_pro = data.get("isPro", False)

        # HF has no MTD spend endpoint - only web dashboard
        # period_end is subscription renewal, not billing cycle spend
        result = {
            "mtd_spend": None,
            "limit": None,
            "currency": "USD",
            "billing_mode": billing_mode,
            "period_end": period_end,
            "is_pro": is_pro,
            "error": None,
            "_no_api": (
                "HuggingFace has no public billing/usage API. "
                "MTD spend requires scraping app.huggingface.co/settings/billing "
                "or using the HF PRO dashboard. No API endpoint exists for usage data."
            ),
        }
        return result

    except requests.RequestException as e:
        return {"mtd_spend": None, "limit": None, "currency": "USD",
                "error": f"Request failed: {e}"}


# ── Provider: Anthropic ────────────────────────────────────────────────────────
def fetch_anthropic():
    """
    Anthropic has NO public billing/usage API.
    No ANTHROPIC_API_KEY found in openclaw.json config.
    Returns: {mtd_spend, limit, currency, error}
    """
    key = load_env_keys()["anthropic"]
    if not key:
        return {"mtd_spend": None, "limit": None, "currency": "USD",
                "error": "ANTHROPIC_API_KEY not found in openclaw.json env"}

    # Even with a key, Anthropic does not expose a public billing/usage endpoint.
    # Their platform billing dashboard at platform.anthropic.com is UI-only.
    # The Messages API (api.anthropic.com) does not include a billing endpoint.
    try:
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        }
        r = requests.get("https://api.anthropic.com/v1/usage", headers=headers, timeout=10)
        if r.status_code == 404:
            return {
                "mtd_spend": None,
                "limit": None,
                "currency": "USD",
                "error": (
                    "Anthropic has no public billing API. "
                    "No /v1/usage or /v1/billing endpoint exists. "
                    "Usage data only available via platform.anthropic.com dashboard "
                    "(requires browser session with login)."
                ),
            }
        elif r.status_code == 200:
            data = r.json()
            return {"mtd_spend": data, "limit": None, "currency": "USD", "error": None}
        else:
            return {
                "mtd_spend": None,
                "limit": None,
                "currency": "USD",
                "error": f"HTTP {r.status_code}: {r.text[:200]}",
            }
    except requests.RequestException as e:
        return {"mtd_spend": None, "limit": None, "currency": "USD",
                "error": f"Request failed: {e}"}


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"[billing_tracker] Running at {datetime.now().isoformat()}")

    keys = load_env_keys()
    print(f"  Keys found: anthropic={bool(keys['anthropic'])}, "
          f"openrouter={bool(keys['openrouter'])}, "
          f"huggingface={bool(keys['huggingface'])}")

    result = {
        "timestamp": datetime.now().isoformat(),
        "anthropic": fetch_anthropic(),
        "openrouter": fetch_openrouter(),
        "huggingface": fetch_huggingface(),
    }

    # Write output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Console summary
    print(f"\n  === Results ===")
    for provider in ["anthropic", "openrouter", "huggingface"]:
        r = result[provider]
        if r.get("error") and not r.get("_no_api"):
            print(f"  {provider}: ERROR - {r['error']}")
        elif r.get("mtd_spend") is not None:
            print(f"  {provider}: mtd_spend=${r['mtd_spend']}, "
                  f"limit=${r.get('limit')}, remaining=${r.get('limit_remaining')}")
        elif r.get("_no_api"):
            print(f"  {provider}: NO API - {r['_no_api'][:80]}...")
        else:
            print(f"  {provider}: mtd_spend=null, error={r.get('error','?')[:60]}")

    print(f"\n  Output written to: {OUTPUT_FILE}")
    return result


if __name__ == "__main__":
    main()
