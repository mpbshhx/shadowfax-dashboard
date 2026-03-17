#!/usr/bin/env python3
"""
Discord Daily Report for OpenClaw Token Usage
Posts daily summary to #morning-briefs channel
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import requests


CHANNEL_ID = '1482153149992144996'  # #morning-briefs


def load_config():
    """Load OpenClaw config to get Discord token"""
    config_path = Path(r'C:\Users\hhx-sandbox2\.openclaw\openclaw.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_usage_data():
    """Load aggregated usage data"""
    data_path = Path(r'C:\Users\hhx-sandbox2\.openclaw\workspace\token-dashboard\usage-data.json')

    if not data_path.exists():
        # Fallback to build directory
        data_path = Path(r'C:\Temp\token-dashboard-build\usage-data.json')

    if not data_path.exists():
        raise FileNotFoundError("usage-data.json not found")

    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_sparkline(values):
    """Generate ASCII sparkline from list of values"""
    if not values or all(v == 0 for v in values):
        return '-' * len(values)

    # Simplified ASCII bars for better compatibility
    ticks = '_.,-=*#@'

    min_val = min(values)
    max_val = max(values)
    value_range = max_val - min_val

    if value_range == 0:
        return ticks[4] * len(values)

    sparkline = ''
    for v in values:
        normalized = (v - min_val) / value_range
        index = int(normalized * (len(ticks) - 1))
        sparkline += ticks[index]

    return sparkline


def format_report(data):
    """Format the daily Discord report message"""
    today = datetime.now().date().isoformat()
    current_month = today[:7]  # YYYY-MM

    # Find today's data
    today_data = None
    for day in data['days']:
        if day['date'] == today:
            today_data = day
            break

    # Calculate MTD
    mtd_cost = 0
    for day in data['days']:
        if day['date'].startswith(current_month):
            mtd_cost += day.get('total_est_cost_usd', 0)

    # Get last 7 days costs for sparkline
    last_7_days = data['days'][-7:]
    cost_values = [day.get('total_est_cost_usd', 0) for day in last_7_days]
    sparkline = generate_sparkline(cost_values)

    # Today's stats
    today_cost = today_data.get('total_est_cost_usd', 0) if today_data else 0
    kimi_runs = today_data['models'].get('kimi', {}).get('runs', 0) if today_data else 0
    sonnet_runs = today_data['models'].get('sonnet', {}).get('runs', 0) if today_data else 0
    opus_runs = today_data['models'].get('opus', {}).get('runs', 0) if today_data else 0
    haiku_runs = today_data['models'].get('haiku', {}).get('runs', 0) if today_data else 0

    hf_balance = data.get('hf_balance')
    hf_balance_str = f"${hf_balance:.2f}" if hf_balance is not None else "N/A"

    # Format message
    report = f"""**Token Usage Report - {today}**

Today est. cost: ${today_cost:.2f} | MTD: ${mtd_cost:.2f}
HF Balance: {hf_balance_str}

**Runs Today:**
Kimi: {kimi_runs} | Sonnet: {sonnet_runs} | Opus: {opus_runs} | Haiku: {haiku_runs}

**Last 7 Days Cost Trend:**
`{sparkline}`
"""

    return report


def send_discord_message(token, channel_id, content):
    """Send message to Discord channel via bot"""
    url = f'https://discord.com/api/v10/channels/{channel_id}/messages'
    headers = {
        'Authorization': f'Bot {token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'content': content
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            print("Discord message sent successfully")
            return True
        else:
            print(f"Discord API error: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"Failed to send Discord message: {e}")
        return False


def main():
    print("Discord Report Generator - Starting...")

    # Load config
    config = load_config()
    discord_token = config.get('channels', {}).get('discord', {}).get('token')

    if not discord_token:
        print("ERROR: Discord token not found in config")
        return

    # Load usage data
    data = load_usage_data()
    print("Usage data loaded")

    # Generate report
    report = format_report(data)
    print("\nGenerated Report:")
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode('utf-8', errors='replace').decode('utf-8'))

    # Send to Discord
    success = send_discord_message(discord_token, CHANNEL_ID, report)

    if success:
        print("\nReport sent to Discord successfully!")
    else:
        print("\nFailed to send report to Discord")


if __name__ == '__main__':
    main()
