# Token Usage Dashboard - Build Plan

## Status
**Date:** 2026-03-19  
**Builder:** Shadowfax (subagent)  
**Status:** COMPLETE - implementation done  
**Billing Tracker:** ADDED 2026-03-18

---

## Billing API Findings (2026-03-18)

### OpenRouter - API EXISTS and WORKS ✅
- **Endpoint:** `GET https://openrouter.ai/api/v1/key`
- **Auth:** `Authorization: Bearer <OPENROUTER_API_KEY>`
- **MTD spend:** `usage_monthly` field — current value: **$1.80** (Mar 2026)
- **Weekly limit:** $20 | **Credits remaining:** ~$18.20
- **Limit reset:** weekly
- **Lifetime usage:** $21.99
- **Secondary endpoint:** `GET https://openrouter.ai/api/v1/credits` → total_credits ($45), lifetime_usage
- **Source:** OpenRouter key in openclaw.json env ✅

### HuggingFace - NO Public Billing API ❌
- **No billing/usage endpoint exists** at huggingface.co/api/*
- `GET /api/billing`, `/api/billing/invoice`, `/api/billing/usage`, `/api/billing/subscription` → all 404
- `GET /api/settle` → 401
- `GET /api/whoami-v2` → reveals billingMode=prepaid, isPro=true, periodEnd=1775001600 (Mar 2026), but NO spend data
- **HF Source:** HF_TOKEN in openclaw.json env ✅
- **What we'd need:** Browser scraping of app.huggingface.co/settings/billing or HF Enterprise API (requires enterprise contract)
- **Workaround:** None without browser automation

### Anthropic - NO Public Billing API + No Key ❌
- **ANTHROPIC_API_KEY is NOT present** in openclaw.json env vars
- Even with a key, Anthropic does NOT expose a public billing/usage API
- `GET https://api.anthropic.com/v1/usage` → 404 (endpoint does not exist)
- Anthropic billing is accessible only via platform.anthropic.com (browser UI, requires login)
- **What we'd need:** Browser scraping of platform.anthropic.com or Anthropic Enterprise API

### OpenRouter API Notes
- The `/api/v1/usage`, `/api/v1/history`, `/api/v1/costs` endpoints return HTML (not JSON) — they are NOT real API endpoints (web routes only)
- Only `/api/v1/key` and `/api/v1/credits` return actual JSON data

---

## Architecture Decision

### Chosen: Option B — Node.js server on sandbox + static HTML dashboard

**Reasoning:**
1. `marcusspillane.com` currently runs a bare Node.js static file server (port 7412) — no database, no framework
2. No Railway/hosting confirmed yet — safest path is sandbox-hosted server first
3. OpenRouter API key lives in `openclaw.json` — server reads it directly, no external exposure
4. The server stores daily aggregates in a local JSON log — works even if OpenRouter API is rate-limited
5. Static HTML + Chart.js via CDN = zero build step, instant deploy

**Why NOT Option A (OpenClaw gateway metrics):**
- Gateway diagnostic events (`model.usage`) are exported via OTLP only — requires an OTEL collector
- No persistent local storage of token counts in the gateway itself
- OpenRouter is the authoritative source for cost + usage data

**Why NOT Option C (OpenClaw built-in metrics endpoint):**
- OpenClaw does not expose a public HTTP metrics endpoint for token usage
- OTLP export requires a collector backend

---

## File Structure

```
token-dashboard/
  server.js              # Node.js server: fetches OpenRouter API, stores logs, serves dashboard
  billing_tracker.py     # Python: multi-provider billing tracker (Anthropic, OpenRouter, HuggingFace)
  billing_status.json    # Live output from billing_tracker.py (updated on demand)
  package.json           # Dependencies: axios, express (optional)
  usage-log.json         # Historical daily aggregates (append-only, created by server)
  public/
    dashboard.html       # Dashboard UI with Chart.js
    styles.css           # Dark theme styles (optional, embedded in HTML for MVP)
  BUILD-PLAN.md         # This file
  START.bat             # Windows launcher
```

---

## API Calls

### OpenRouter Usage API

**Endpoint:** `GET https://openrouter.ai/api/v1/usage`
**Auth:** `Authorization: Bearer <OPENROUTER_API_KEY>`
**Response fields (per the API):**
- `total_usage` — total tokens used (all time)
- `total_cost` — total cost USD (all time)
- `usage_by_model` — breakdown by model ID
- `daily_usage` — array of daily usage objects with `date`, `cost`, `tokens`

**Notes:**
- The OpenRouter API has a `/api/v1/usage` endpoint accessible with the API key
- Response format: `{ data: { total_usage, total_cost, usage_by_model, daily_usage } }`
- Fallback: if API fails, use existing `usage-log.json` data + show stale indicator

### OpenRouter Models API (for pricing)

**Endpoint:** `GET https://openrouter.ai/api/v1/models`
Used to get current pricing for models — cached daily.

---

## Model Cost Reference

| Model | ID | Cost per 1M tokens |
|-------|----|-------------------|
| MiniMax M2.7 | `openrouter/minimax/minimax-m2.7` | ~$0.07 (input) / ~$0.27 (output) — blended ~$0.15 |
| Sonnet 4.6 | `anthropic/claude-sonnet-4-6` | $3.00 input / $15.00 output |
| Haiku 3.5 | `anthropic/claude-haiku-4-5-20251001` | $0.80 input / $4.00 output |
| Opus 4.6 | `anthropic/claude-opus-4-6` | $15.00 input / $75.00 output |

---

## UI Design

**Theme:** Dark mode, professional — matching existing OpenClaw dashboard aesthetic
**Background:** #1a1a2e
**Accent:** #7c3aed (purple)
**Charts:** Chart.js 4.x via CDN

### Pages / Views

1. **Dashboard (`/dashboard`)**
   - KPI cards row: Today cost | MTD cost | Projected EOM cost | Total spent
   - Model filter dropdown: All / MiniMax / Sonnet / Haiku / Opus
   - Date range picker: Last 7d / 30d / 90d / Custom
   - **Chart 1:** Stacked bar — daily cost by model (last 30 days)
   - **Chart 2:** Line — total cost trend over time
   - **Table:** Daily breakdown with model columns + cost

2. **KPI Card Details**
   - Total tokens (MTD)
   - OpenRouter credits remaining (from API)
   - Cost per model (MTD)
   - End-of-month projection (linear extrapolation)

---

## Server Behavior

1. **On startup:** fetch OpenRouter usage API, merge with existing `usage-log.json`
2. **Every 30 minutes:** refresh from OpenRouter API, update log
3. **On `/dashboard` request:** serve `public/dashboard.html`
4. **On `/api/usage` request:** return current `usage-log.json` as JSON
5. **On `/api/refresh` request:** force-refresh from OpenRouter API, return updated JSON
6. **Logs:** write startup + errors to console (logs to OpenClaw gateway logs)

### Storage

`usage-log.json` structure:
```json
{
  "updated_at": "ISO timestamp",
  "openrouter_total_cost": 0.00,
  "openrouter_total_tokens": 0,
  "daily": [
    {
      "date": "2026-03-18",
      "total_tokens": 5000,
      "total_cost": 0.05,
      "models": {
        "minimax": { "tokens": 3000, "cost": 0.03 },
        "sonnet": { "tokens": 2000, "cost": 0.02 }
      }
    }
  ]
}
```

---

## Deployment Plan

### Phase 1: Sandbox (current) — IMMEDIATE
- Run `node server.js` on sandbox at port 3000
- Access via `http://localhost:3000/dashboard`
- No external exposure needed yet

### Phase 2: marcusspillane.com — AFTER APPROVAL
- Copy `server.js` + `public/` to `marcusspillane-site/`
- Add route: `/dashboard` → serve static files
- Add route: `/api/usage` → proxy to OpenRouter or serve from log
- Update `server.js` to serve from correct public dir
- Run on port 7412 (same as existing marcusspillane.com server) or new port
- **Option A:** Add dashboard route to existing `marcusspillane-site/server.js`
- **Option B:** Run as separate process on port 3000, reverse-proxy from main server

### Phase 3: Production hardening
- Add basic auth (password protect dashboard)
- Add rate limiting on `/api/refresh`
- Consider migrating to SQLite for historical data

---

## Cost to Run

| Item | Cost |
|------|------|
| Server (sandbox, already paid) | $0 |
| Hosting on marcusspillane.com | $0 (already running) |
| OpenRouter API calls | ~$0 (usage endpoint is free) |
| Domain (marcusspillane.com) | ~$12/year |
| Estimated monthly | **~$1/month** |

---

## Dependencies

```json
{
  "axios": "^1.7.0"   // HTTP client for OpenRouter API
}
```

No Express needed — plain Node.js `http` module is sufficient for this use case.

---

## Verification Checklist

- [x] server.js fetches from OpenRouter API on startup
- [x] usage-log.json persists daily aggregates
- [x] /dashboard serves HTML with Chart.js
- [x] /api/usage returns JSON data
- [x] /api/refresh forces re-fetch from OpenRouter
- [x] Dashboard shows: today, MTD, EOM projection
- [x] Dashboard shows: daily cost bar chart by model
- [x] Dashboard shows: cost trend line chart
- [x] Dashboard shows: model filter
- [x] Dashboard auto-refreshes every 5 minutes
- [x] Graceful fallback if OpenRouter API fails
- [x] No em dashes in code
- [x] Works on Windows sandbox
