# DECOMMISSIONED

**Date:** 2026-08-28

This dashboard is retired and must not be used as an authoritative source for token usage or cost.

## Why it was retired

- `token_tracker.py` assigns a fabricated flat estimate of 2,000 tokens to every run.
- `server.js` uses a separate, inconsistent context-based estimator.
- The source CSV contains context metadata, not measured token usage or provider cost.
- Dashboard data stopped updating in March 2026.
- Model mappings and prices became stale.

Updating labels or prices would make invented numbers look more credible without making them true.

## Status

- No active cron invokes the tracker, reporter, or server.
- The project is preserved only as historical evidence.
- Do not run, deploy, extend, or cite its output for decisions.

A future replacement requires a separately approved source contract using measured OpenClaw per-run usage or authoritative provider billing data.

Evidence: `audits/workspace-optimization/baseline/phase-4/phase-4b-validation-decision.md` in the parent workspace repository.
