/**
 * Token Usage Dashboard Server
 * Fetches usage from OpenRouter API (with fallback), parses local CSV logs,
 * stores daily aggregates, and serves the dashboard UI.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ── Config ────────────────────────────────────────────────────────────────────
const PORT = 3000;
const BASE_DIR = __dirname;
const LOG_FILE = path.join(BASE_DIR, 'usage-log.json');
const CSV_LOG = path.join(os.homedir(), '.openclaw', 'workspace', 'memory', 'usage-log.csv');
const PUBLIC_DIR = path.join(BASE_DIR, 'public');
const CONFIG_PATH = path.join(os.homedir(), '.openclaw', 'openclaw.json');

// ── Cost per million tokens ────────────────────────────────────────────────────
const COST_PER_M = {
  'openrouter/minimax/minimax-m2.7': 0.15,   // blended
  'huggingface/moonshotai/kimi-k2.5': 0.15,
  'anthropic/claude-sonnet-4-6': 3.00,
  'anthropic/claude-opus-4-6': 15.00,
  'anthropic/claude-3-5-haiku-20241022': 1.00,
  'anthropic/claude-haiku-4-5-20251001': 0.80,
};

// ── Model normalization ────────────────────────────────────────────────────────
function normalizeModel(modelId) {
  if (!modelId) return 'unknown';
  const id = modelId.toLowerCase();
  if (id.includes('minimax')) return 'minimax';
  if (id.includes('kimi')) return 'minimax';
  if (id.includes('sonnet')) return 'sonnet';
  if (id.includes('opus')) return 'opus';
  if (id.includes('haiku')) return 'haiku';
  return 'other';
}

// ── Config ─────────────────────────────────────────────────────────────────────
function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  } catch (e) {
    return null;
  }
}

// ── OpenRouter API ─────────────────────────────────────────────────────────────
async function fetchOpenRouterUsage(apiKey) {
  if (!apiKey) return null;
  try {
    const res = await fetch('https://openrouter.ai/api/v1/usage', {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      }
    });
    if (!res.ok) return null;
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('json')) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

// ── CSV log parser ─────────────────────────────────────────────────────────────
function parseCSVLog() {
  try {
    if (!fs.existsSync(CSV_LOG)) return [];
    const raw = fs.readFileSync(CSV_LOG, 'utf8');
    const lines = raw.trim().split('\n');
    if (lines.length < 2) return [];
    const header = lines[0].split(',');
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const vals = lines[i].split(',');
      const row = {};
      header.forEach((h, idx) => { row[h.trim()] = (vals[idx] || '').trim(); });
      rows.push(row);
    }
    return rows;
  } catch (e) {
    return [];
  }
}

function csvToDaily(rows) {
  const byDate = {};
  rows.forEach(row => {
    const date = row.date;
    if (!date) return;
    const model = normalizeModel(row.model);
    const ctx = parseInt(row.context_used_k) || 0;

    // Estimate tokens: context_used_k * 1.5 round trips per session + base 500
    // For cron sessions (low context) estimate ~2000 tokens
    // For active sessions (high context) estimate based on context
    let estTokens = 2000;
    if (ctx > 50) estTokens = Math.round(ctx * 1500);
    else if (ctx > 10) estTokens = Math.round(ctx * 800);

    const costPerM = COST_PER_M[row.model] || COST_PER_M[row.model?.toLowerCase()] || 1.0;
    const estCost = (estTokens / 1_000_000) * costPerM;

    if (!byDate[date]) {
      byDate[date] = { date, total_tokens: 0, total_cost: 0, models: {} };
    }
    if (!byDate[date].models[model]) {
      byDate[date].models[model] = { tokens: 0, cost: 0, runs: 0 };
    }
    byDate[date].models[model].tokens += estTokens;
    byDate[date].models[model].cost += estCost;
    byDate[date].models[model].runs += 1;
    byDate[date].total_tokens += estTokens;
    byDate[date].total_cost += estCost;
  });

  return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
}

// ── Load / save log ───────────────────────────────────────────────────────────
function loadUsageLog() {
  try {
    if (fs.existsSync(LOG_FILE)) {
      return JSON.parse(fs.readFileSync(LOG_FILE, 'utf8'));
    }
  } catch (e) { /* ignore */ }
  return { updated_at: null, daily: [], openrouter_total_cost: 0, openrouter_total_tokens: 0, source: 'csv' };
}

function saveUsageLog(data) {
  fs.writeFileSync(LOG_FILE, JSON.stringify(data, null, 2), 'utf8');
}

// ── Merge OpenRouter data ─────────────────────────────────────────────────────
function mergeOpenRouterData(log, orData) {
  if (!orData || !orData.data) return log;
  const data = orData.data;

  log.openrouter_total_cost = parseFloat(data.total_cost) || 0;
  log.openrouter_total_tokens = parseInt(data.total_usage) || 0;
  log.openrouter_source = 'api';

  const dailyMap = {};

  if (data.daily_costs && Array.isArray(data.daily_costs)) {
    data.daily_costs.forEach(day => {
      const date = day.date || day.day;
      if (!date) return;
      dailyMap[date] = {
        date,
        total_tokens: 0,
        total_cost: parseFloat(day.cost) || 0,
        models: {}
      };
    });
  }

  if (data.usage_by_model && Array.isArray(data.usage_by_model)) {
    data.usage_by_model.forEach(item => {
      const date = item.date || item.day;
      if (!date) return;
      const model = normalizeModel(item.model);
      const tokens = parseInt(item.total_tokens) || 0;
      const cost = parseFloat(item.cost) || 0;
      if (!dailyMap[date]) {
        dailyMap[date] = { date, total_tokens: 0, total_cost: 0, models: {} };
      }
      dailyMap[date].total_tokens += tokens;
      dailyMap[date].total_cost += cost;
      if (!dailyMap[date].models[model]) {
        dailyMap[date].models[model] = { tokens: 0, cost: 0 };
      }
      dailyMap[date].models[model].tokens += tokens;
      dailyMap[date].models[model].cost += cost;
    });
  }

  // Merge with CSV log
  const existingByDate = {};
  log.daily.forEach(d => { existingByDate[d.date] = d; });
  Object.keys(dailyMap).forEach(date => {
    existingByDate[date] = dailyMap[date];
  });

  // Keep last 90 days
  const dates = Object.keys(existingByDate).sort();
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 90);
  const cutoffStr = cutoff.toISOString().split('T')[0];
  log.daily = dates.filter(d => d >= cutoffStr).map(d => existingByDate[d]);
  log.updated_at = new Date().toISOString();

  return log;
}

// ── Refresh usage ─────────────────────────────────────────────────────────────
async function refreshUsage() {
  const config = loadConfig();
  const apiKey = config?.env?.OPENROUTER_API_KEY;

  // Always parse CSV as base
  const csvRows = parseCSVLog();
  const csvDaily = csvToDaily(csvRows);
  const log = loadUsageLog();

  // Try OpenRouter API
  let apiOk = false;
  if (apiKey) {
    console.log('[server] Trying OpenRouter API...');
    const orData = await fetchOpenRouterUsage(apiKey);
    if (orData) {
      console.log('[server] OpenRouter API OK — merging data');
      mergeOpenRouterData(log, orData);
      apiOk = true;
    } else {
      console.log('[server] OpenRouter API unreachable — using CSV data');
    }
  }

  // Merge CSV daily data where we don't have API data
  csvDaily.forEach(day => {
    const existing = log.daily.find(d => d.date === day.date);
    if (!existing) {
      log.daily.push(day);
    }
  });

  log.daily.sort((a, b) => a.date.localeCompare(b.date));

  // Keep last 90 days
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 90);
  const cutoffStr = cutoff.toISOString().split('T')[0];
  log.daily = log.daily.filter(d => d.date >= cutoffStr);

  log.updated_at = new Date().toISOString();
  log.source = apiOk ? 'openrouter+csv' : 'csv';
  log.api_reachable = apiOk;

  return log;
}

// ── HTTP Server ────────────────────────────────────────────────────────────────
function handleRequest(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  // API: get usage data
  if (url.pathname === '/api/usage') {
    try {
      const log = loadUsageLog();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(log));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }

  // API: force refresh
  if (url.pathname === '/api/refresh') {
    refreshUsage().then(log => {
      saveUsageLog(log);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(log));
    }).catch(e => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    });
    return;
  }

  // Serve dashboard
  if (url.pathname === '/' || url.pathname === '/dashboard' || url.pathname === '/index.html') {
    const filePath = path.join(PUBLIC_DIR, 'dashboard.html');
    if (fs.existsSync(filePath)) {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(fs.readFileSync(filePath));
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('dashboard.html not found');
    }
    return;
  }

  // Static files
  const filePath = path.join(PUBLIC_DIR, url.pathname.replace(/^\//, ''));
  if (fs.existsSync(filePath)) {
    const ext = path.extname(filePath);
    const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript', '.json': 'application/json' };
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'text/plain' });
    res.end(fs.readFileSync(filePath));
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not found');
}

// ── Main ───────────────────────────────────────────────────────────────────────
async function main() {
  console.log('Shadowfax Token Dashboard starting...');
  console.log(`[server] Base dir: ${BASE_DIR}`);
  console.log(`[server] CSV log: ${CSV_LOG}`);

  if (!fs.existsSync(PUBLIC_DIR)) {
    fs.mkdirSync(PUBLIC_DIR, { recursive: true });
  }

  // Initial load + refresh
  const log = await refreshUsage();
  saveUsageLog(log);
  console.log(`[server] Data source: ${log.source}`);
  console.log(`[server] Days loaded: ${log.daily.length}`);
  if (log.openrouter_total_cost) {
    console.log(`[server] OpenRouter total: $${log.openrouter_total_cost.toFixed(4)}`);
  }

  // HTTP server
  http.createServer(handleRequest).listen(PORT, () => {
    console.log(`\nDashboard: http://localhost:${PORT}/dashboard`);
    console.log(`API data: http://localhost:${PORT}/api/usage`);
    console.log(`Force refresh: http://localhost:${PORT}/api/refresh\n`);
  });

  // Refresh every 30 min
  setInterval(async () => {
    console.log('[server] Periodic refresh...');
    const l = await refreshUsage();
    saveUsageLog(l);
    console.log(`[server] Updated: ${l.daily.length} days, source: ${l.source}`);
  }, 30 * 60 * 1000);
}

main().catch(e => {
  console.error('[server] Fatal:', e);
  process.exit(1);
});
