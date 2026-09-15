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
| `parse_alerts.py` | turns collected heartbeat-alert messages into the same CSV schema |

## Running

```bash
python3 research/lookahead_audit.py research/data/<file>.csv    # must report 0 leaks
python3 research/selftest_stats.py                              # must be all PASS

python3 research/harness.py research/data/<file>.csv --decider accept_all \
        --out research/out/armA.jsonl
python3 research/metrics.py research/out/armA.jsonl
```

## Getting real data

Two routes, both manual on the TradingView side. See `../docs/17-phase0-data-acquisition.md`.

1. **Chart data export** — `Export chart data…` in the chart's top-right menu, with
   ACE on the chart and history scrolled in. The current pricing page lists this on
   every tier including free Basic; check before assuming it is unavailable.
2. **Heartbeat alerts** — an always-true alert firing once per bar close, carrying the
   plotted ACE values via `{{plot("...")}}`. Collect the messages, then:

   ```bash
   python3 research/parse_alerts.py collected.txt research/data/FORWARD-01.csv
   ```

Either way the file lands in `research/data/` and the rest of the pipeline is identical.

Until that exists, no verdict can be produced. `research/data/SYNTHETIC-*.csv`
holds fabricated ACE columns and exists only to exercise the code; any P&L
computed from it is meaningless by construction.
