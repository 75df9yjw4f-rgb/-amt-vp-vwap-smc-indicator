"""Builds a CSV in the shape TradingView exports, for validating the harness.

IMPORTANT: the ACE columns produced here are SYNTHETIC. BIAS and CONFIDENCE are a
seeded random walk with no relationship to price, chosen deliberately so that any
P&L computed from this file is meaningless by construction and cannot later be
mistaken for a finding. VWAP and the value area are derived from the real prices
only so the geometry the baselines read is structurally realistic.

This file exists to prove the machinery runs. It proves nothing about ACE.
"""
import csv, json, math, random, statistics, sys


def build(kraken_json, out_csv, seed=7):
    d = json.load(open(kraken_json))
    key = [x for x in d["result"] if x != "last"][0]
    raw = d["result"][key]

    rng = random.Random(seed)
    bias, conf = 0.0, 0.5
    win, out = [], []
    for t, o, h, l, c, vwap_k, vol, cnt in raw:
        o, h, l, c, vol = float(o), float(h), float(l), float(c), float(vol)
        win.append((c, vol, h, l))
        if len(win) > 78:                      # ~6.5h of 5m bars
            win.pop(0)

        # --- synthetic scoring output: a bounded random walk, price-independent
        bias = max(-1.0, min(1.0, bias + rng.gauss(0, 0.08)))
        conf = max(0.0, min(1.0, conf + rng.gauss(0, 0.05)))

        # --- geometry derived from real prices
        tv = sum(w[1] for w in win) or 1.0
        vwap = sum(w[0] * w[1] for w in win) / tv
        sd = statistics.pstdev([w[0] for w in win]) if len(win) > 2 else 0.0
        highs = sorted(w[2] for w in win)
        lows = sorted(w[3] for w in win)
        vah = highs[int(0.70 * (len(highs) - 1))]
        val = lows[int(0.30 * (len(lows) - 1))]
        poc = statistics.median([w[0] for w in win])

        out.append({
            "time": t, "open": o, "high": h, "low": l, "close": c, "volume": vol,
            "Developing POC": round(poc, 2), "Developing VAH": round(vah, 2),
            "Developing VAL": round(val, 2),
            "Session VWAP": round(vwap, 2), "Daily VWAP": round(vwap, 2),
            "Weekly VWAP": round(vwap, 2), "Monthly VWAP": round(vwap, 2),
            "VWAP +2σ": round(vwap + 2 * sd, 2), "VWAP -2σ": round(vwap - 2 * sd, 2),
            "VWAP +3σ": round(vwap + 3 * sd, 2), "VWAP -3σ": round(vwap - 3 * sd, 2),
            "BIAS": round(bias, 4), "CONFIDENCE": round(conf, 4),
            "BULL": round(max(bias, 0), 4), "BEAR": round(max(-bias, 0), 4),
        })

    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    return len(out)


if __name__ == "__main__":
    n = build(sys.argv[1], sys.argv[2])
    print(f"{n} bars -> {sys.argv[2]}  (ACE columns are SYNTHETIC)")
