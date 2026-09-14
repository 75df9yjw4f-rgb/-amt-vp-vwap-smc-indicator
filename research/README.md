# Phase 0 harness

Research only. No broker, no exchange, no orders, no execution, no notifications.
**ACE v1 is not modified and no plots are added.**

Rules, parameters and success criteria are frozen in `../docs/15-phase0-preregistration.md`.
Do not change them after a run.

## Files

| File | Role |
|---|---|
| `ace_data.py` | loads a TradingView chart-data export; computes ATR(14) |
| `baselines.py` | B1/B2/B3 and the regime classifier |
| `snapshot.py` | point-in-time snapshot; anonymised, normalised, hashed |
| `deciders.py` | `accept_all` (arm A), `random_veto` (null model), Claude stub |
| `outcomes.py` | forward simulation, R / MFE / MAE |
| `harness.py` | runs the loop, writes the decision log |
| `metrics.py` | metrics, bootstrap, permutation test, pre-registered verdict |
| `lookahead_audit.py` | proves the snapshot cannot see the future |
| `selftest_stats.py` | calibrates the verdict table against known-skill inputs |
| `veto_prompt.md` | the frozen prompt |
| `make_synthetic.py` | builds a fake-ACE CSV for testing the machinery only |

## Running

```bash
python3 research/lookahead_audit.py research/data/<file>.csv    # must report 0 leaks
python3 research/selftest_stats.py                              # must be all PASS

python3 research/harness.py research/data/<file>.csv --decider accept_all \
        --out research/out/armA.jsonl
python3 research/metrics.py research/out/armA.jsonl
```

## Getting real data

The harness has no data and cannot fetch any: exporting from TradingView is a
manual action in the UI, available to the account owner.

1. Open the chart with ACE. Set the symbol, timeframe and period.
2. `Export chart data…` → CSV (needs Pro+ / Premium).
3. Drop the file in `research/data/`.

Until that exists, no verdict can be produced. `research/data/SYNTHETIC-*.csv`
holds fabricated ACE columns and exists only to exercise the code; any P&L
computed from it is meaningless by construction.
