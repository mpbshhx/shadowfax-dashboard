# Quick Start Guide - Token Dashboard

## Installation

1. Install Python dependencies:
```bash
cd C:\Temp\token-dashboard-build
pip install -r requirements.txt
```

## Usage

### Generate/Update Token Data
Run the tracker to pull latest usage data from logs and APIs:
```bash
python token_tracker.py
```

Output goes to:
- `C:\Users\hhx-sandbox2\.openclaw\workspace\token-dashboard\usage-data.json`
- `C:\Temp\token-dashboard-build\usage-data.json` (local copy)

### View Dashboard
Open the HTML dashboard in your browser:
```bash
start index.html
```

Or manually open: `C:\Temp\token-dashboard-build\index.html`

Features:
- Real-time KPIs (today's cost, MTD, HF balance, active models)
- 30-day cost trend line chart
- 30-day token volume bar chart (stacked by model)
- Last 7 days detailed breakdown table
- Auto-refreshes every 5 minutes

### Send Discord Report
Post daily summary to #morning-briefs:
```bash
python discord_report.py
```

Example output:
```
**Token Usage Report - 2026-03-17**

Today est. cost: $0.00 | MTD: $0.09
HF Balance: N/A

**Runs Today:**
Kimi: 0 | Sonnet: 0 | Opus: 0 | Haiku: 0

**Last 7 Days Cost Trend:**
`#@#_##_`
```

## Automation Setup

### Option 1: Windows Task Scheduler
Create a daily task at 8 AM:

```powershell
schtasks /create /tn "TokenDashboard" /tr "python C:\Temp\token-dashboard-build\token_tracker.py && python C:\Temp\token-dashboard-build\discord_report.py" /sc daily /st 08:00
```

### Option 2: OpenClaw Cron
Add to your OpenClaw cron config:

```json
{
  "schedule": "0 8 * * *",
  "description": "Daily token usage report",
  "command": "python C:\\Temp\\token-dashboard-build\\token_tracker.py && python C:\\Temp\\token-dashboard-build\\discord_report.py"
}
```

## Troubleshooting

### "No module named 'requests'"
Install dependencies:
```bash
pip install requests
```

### "usage-log.csv not found"
Ensure OpenClaw usage log exists at:
`C:\Users\hhx-sandbox2\.openclaw\workspace\memory\usage-log.csv`

### Discord message not sending
Verify Discord bot token in:
`C:\Users\hhx-sandbox2\.openclaw\openclaw.json` at `channels.discord.token`

### Dashboard shows "Loading..."
1. Run `python token_tracker.py` first to generate data
2. Check that `usage-data.json` exists in the same directory as `index.html`
3. Open browser console (F12) to see errors

### HF Balance shows "N/A"
- HuggingFace token might be missing or invalid in openclaw.json
- API might be down (dashboard still works with CSV data)

## Files Overview

```
C:\Temp\token-dashboard-build\
├── token_tracker.py      # Data aggregation script
├── discord_report.py     # Discord daily reporter
├── index.html            # Dashboard UI
├── requirements.txt      # Python dependencies
├── usage-data.json       # Generated data (auto-created)
├── README.md             # Full documentation
└── QUICKSTART.md         # This file
```

## Daily Workflow

1. **Morning (Automated)**: Cron runs `token_tracker.py` + `discord_report.py`
   - Updates usage data from logs + APIs
   - Posts report to Discord #morning-briefs

2. **Anytime**: Open `index.html` to view dashboard
   - Auto-refreshes every 5 minutes
   - Works offline with local data

3. **Manual Update**: Run `python token_tracker.py` anytime to refresh data

## Cost Estimates

Per million tokens (blended input/output):
- **Kimi K2.5**: $0.15/M (cheapest, used for subagents)
- **Claude Haiku 3.5**: $1.00/M
- **Claude Sonnet 4.6**: $3.00/M (default primary model)
- **Claude Opus 4.6**: $15.00/M (most expensive, heavy research)

Estimates assume 2000 tokens per cron run on average.

## Support

For issues or questions:
- Check README.md for detailed documentation
- Review OpenClaw logs: `C:\tmp\openclaw\openclaw-YYYY-MM-DD.log`
- Verify config: `C:\Users\hhx-sandbox2\.openclaw\openclaw.json`
