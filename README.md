# Shadowfax Token Usage Dashboard

A comprehensive token usage tracking and reporting system for OpenClaw's AI model usage across multiple providers (Anthropic, HuggingFace).

## Components

### 1. `token_tracker.py`
Python script that:
- Reads usage logs from `~/.openclaw/workspace/memory/usage-log.csv`
- Queries Anthropic and HuggingFace APIs for current balances
- Aggregates usage by date and model (last 30 days)
- Generates `usage-data.json` with cost estimates and token counts
- Estimates based on average 2000 tokens per cron run

**Cost Estimates (per million tokens, blended):**
- Kimi K2.5: $0.15/M
- Claude Sonnet 4.6: $3.00/M
- Claude Opus 4.6: $15.00/M
- Claude Haiku 3.5: $1.00/M

**Usage:**
```bash
python token_tracker.py
```

Output: `C:\Users\hhx-sandbox2\.openclaw\workspace\token-dashboard\usage-data.json`

### 2. `index.html`
Dark-themed dashboard with:
- **KPI Cards**: Today's cost, MTD cost, HF balance, active models
- **Line Chart**: Daily estimated cost by model (last 30 days)
- **Bar Chart**: Daily token volume stacked by model (last 30 days)
- **Table**: Last 7 days detailed breakdown
- **Auto-refresh**: Every 5 minutes

**Color Scheme:**
- Background: #1a1a2e
- Accent: #7c3aed (purple)
- Kimi: Blue (#3b82f6)
- Sonnet: Green (#10b981)
- Opus: Orange (#f59e0b)
- Haiku: Pink (#ec4899)

**Usage:**
Open `file://C:/Temp/token-dashboard-build/index.html` in browser

### 3. `discord_report.py`
Daily report generator that:
- Reads `usage-data.json`
- Formats a summary message with:
  - Today's estimated cost
  - Month-to-date cost
  - HuggingFace balance
  - Run counts by model
  - ASCII sparkline of last 7 days costs
- Posts to Discord channel #morning-briefs (ID: 1482153149992144996)

**Usage:**
```bash
python discord_report.py
```

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure OpenClaw config exists at:
   `C:\Users\hhx-sandbox2\.openclaw\openclaw.json`

3. Run token tracker to generate initial data:
```bash
python token_tracker.py
```

4. Open dashboard:
   - Double-click `index.html`
   - Or: `start index.html`

## Data Flow

```
usage-log.csv
    |
    v
token_tracker.py --> usage-data.json
    |                      |
    v                      v
[Anthropic API]       index.html
[HuggingFace API]          |
                           v
                   discord_report.py --> Discord #morning-briefs
```

## Automation

To automate daily reporting, add to OpenClaw cron:

```json
{
  "schedule": "0 8 * * *",
  "command": "python C:\\Temp\\token-dashboard-build\\token_tracker.py && python C:\\Temp\\token-dashboard-build\\discord_report.py"
}
```

This runs at 8 AM daily:
1. Updates usage data from logs + APIs
2. Posts report to Discord

## Files

- `token_tracker.py` - Data aggregation script
- `index.html` - Interactive dashboard
- `discord_report.py` - Discord reporter
- `requirements.txt` - Python dependencies
- `usage-data.json` - Generated data (auto-created)
- `README.md` - This file

## Notes

- Dashboard works offline (no server needed, uses file:// protocol)
- API keys read from OpenClaw config, NOT environment variables
- Handles missing HF token gracefully
- Anthropic API may return 404 (uses CSV data as fallback)
- No em dashes anywhere in code
- Python 3.x compatible
