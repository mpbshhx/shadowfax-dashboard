#!/usr/bin/env python3
"""
Token Usage Tracker for OpenClaw
Reads usage-log.csv, queries Anthropic/HuggingFace APIs, generates aggregated JSON
"""

import json
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path
import requests


# Cost estimates per million tokens (blended input/output)
COST_PER_M = {
    'huggingface/moonshotai/Kimi-K2.5': 0.15,
    'anthropic/claude-sonnet-4-6': 3.0,
    'anthropic/claude-opus-4-6': 15.0,
    'anthropic/claude-3-5-haiku-20241022': 1.0,
}

# Model name mapping for display
MODEL_DISPLAY_NAMES = {
    'huggingface/moonshotai/Kimi-K2.5': 'kimi',
    'anthropic/claude-sonnet-4-6': 'sonnet',
    'anthropic/claude-opus-4-6': 'opus',
    'anthropic/claude-3-5-haiku-20241022': 'haiku',
}


def load_config():
    """Load OpenClaw config to get API keys"""
    config_path = Path(r'C:\Users\hhx-sandbox2\.openclaw\openclaw.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_anthropic_usage(api_key):
    """
    Try to fetch Anthropic usage data from API
    Returns None if API calls fail
    """
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
    }

    # Try direct usage endpoint
    try:
        resp = requests.get('https://api.anthropic.com/v1/usage', headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Anthropic usage API failed: {e}")

    # Try organizations endpoint to find org_id
    try:
        resp = requests.get('https://api.anthropic.com/v1/organizations', headers=headers, timeout=10)
        if resp.status_code == 200:
            orgs = resp.json()
            if orgs and len(orgs) > 0:
                org_id = orgs[0].get('id')
                if org_id:
                    usage_url = f'https://api.anthropic.com/v1/organizations/{org_id}/usage'
                    resp = requests.get(usage_url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        return resp.json()
    except Exception as e:
        print(f"Anthropic organizations API failed: {e}")

    return None


def get_hf_balance(hf_token):
    """
    Fetch HuggingFace balance from whoami-v2 API
    Returns None if fails
    """
    if not hf_token:
        return None

    try:
        headers = {'Authorization': f'Bearer {hf_token}'}
        resp = requests.get('https://huggingface.co/api/whoami-v2', headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Balance might be in various fields, try common ones
            balance = data.get('balance') or data.get('credit_balance') or data.get('credits')
            return balance
    except Exception as e:
        print(f"HuggingFace API failed: {e}")

    return None


def load_usage_log():
    """
    Load and parse usage-log.csv
    Returns list of dicts with parsed data
    """
    log_path = Path(r'C:\Users\hhx-sandbox2\.openclaw\workspace\memory\usage-log.csv')

    if not log_path.exists():
        return []

    entries = []
    for enc in ('utf-8', 'cp1252'):
        try:
            with open(log_path, 'r', encoding=enc) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entries.append(row)
            break
        except UnicodeDecodeError:
            continue

    return entries


def aggregate_by_date(entries, days=30):
    """
    Aggregate usage entries by date and model
    Returns list of daily aggregates for last N days
    """
    # Get date range
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days-1)

    # Initialize daily data structure
    daily_data = {}
    for i in range(days):
        date = start_date + timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        daily_data[date_str] = {}

    # Process each entry
    for entry in entries:
        try:
            # Parse date from entry
            date_str = entry.get('date', '')
            if not date_str:
                continue

            # Only include last N days
            if date_str not in daily_data:
                continue

            model = entry.get('model', '')
            if not model:
                continue

            # Get display name
            display_name = MODEL_DISPLAY_NAMES.get(model, model)

            # Initialize model data if not exists
            if display_name not in daily_data[date_str]:
                daily_data[date_str][display_name] = {
                    'runs': 0,
                    'est_tokens': 0,
                    'est_cost_usd': 0.0,
                    'context_used_k': 0,
                }

            # Increment runs
            daily_data[date_str][display_name]['runs'] += 1

            # Estimate tokens (2000 per run average)
            est_tokens = 2000
            daily_data[date_str][display_name]['est_tokens'] += est_tokens

            # Calculate cost
            cost_per_m = COST_PER_M.get(model, 1.0)
            est_cost = (est_tokens / 1_000_000) * cost_per_m
            daily_data[date_str][display_name]['est_cost_usd'] += est_cost

            # Track context usage
            context_used = entry.get('context_used_k', '0')
            try:
                context_k = int(context_used)
                daily_data[date_str][display_name]['context_used_k'] += context_k
            except:
                pass

        except Exception as e:
            print(f"Error processing entry: {e}")
            continue

    # Format output
    result = []
    for date_str in sorted(daily_data.keys()):
        models = daily_data[date_str]

        # Calculate total cost for the day
        total_cost = sum(m['est_cost_usd'] for m in models.values())

        result.append({
            'date': date_str,
            'models': models,
            'total_est_cost_usd': round(total_cost, 4),
        })

    return result


def main():
    print("Token Usage Tracker - Starting...")

    # Load config
    config = load_config()

    # Get API keys
    anthropic_key = config.get('env', {}).get('ANTHROPIC_API_KEY')
    hf_token = config.get('env', {}).get('HF_TOKEN')

    # Try to get HuggingFace balance
    hf_balance = get_hf_balance(hf_token)
    print(f"HuggingFace balance: {hf_balance}")

    # Try to get Anthropic usage (optional)
    anthropic_usage = None
    if anthropic_key:
        anthropic_usage = get_anthropic_usage(anthropic_key)
        if anthropic_usage:
            print("Anthropic usage data fetched successfully")

    # Load usage log
    entries = load_usage_log()
    print(f"Loaded {len(entries)} usage log entries")

    # Aggregate by date (last 30 days)
    daily_aggregates = aggregate_by_date(entries, days=30)
    print(f"Aggregated into {len(daily_aggregates)} daily records")

    # Build output JSON
    output = {
        'updated_at': datetime.now().isoformat(),
        'hf_balance': hf_balance,
        'anthropic_usage': anthropic_usage,
        'days': daily_aggregates,
    }

    # Ensure output directory exists
    output_dir = Path(r'C:\Users\hhx-sandbox2\.openclaw\workspace\token-dashboard')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON file
    output_path = output_dir / 'usage-data.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Output written to: {output_path}")

    # Also copy to build directory for local dashboard
    build_output = Path(r'C:\Temp\token-dashboard-build\usage-data.json')
    with open(build_output, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"Copy written to: {build_output}")


if __name__ == '__main__':
    main()
