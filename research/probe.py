"""Probe mode: measures what the veto layer ASKS FOR, not whether it makes money.

Twenty to forty hand-collected bars will not produce enough baseline signals to
say anything about edge - it will produce one or two, where the pre-registration
demands a hundred. So probe mode asks the only questions a sample that size can
actually answer:

  - which facts does the veto layer say it is missing?  (this is the direct,
    measured answer to "which plots would ACE need to export")
  - how often does it abstain for lack of data?
  - is its judgement direction-sensitive at all?

Every bar is probed with BOTH a hypothetical long and a hypothetical short, so
a layer that answers the same way to both reveals itself: that answer carries no
directional information whatever its wording.

No outcome is computed here and simulate() is never called, so there is nothing
to leak. Probe mode cannot produce a verdict and does not try.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace_data import load_csv
from baselines import STOP_ATR, TARGET_ATR
from snapshot import build as build_snapshot


def probe(rows, start=20, step=1, symbol="ANON-1"):
    out = []
    for i in range(start, len(rows), step):
        r = rows[i]
        if not r.get('atr') or not r.get('gap_ok', True):
            continue
        for side in ("LONG", "SHORT"):
            sgn = 1 if side == "LONG" else -1
            sig = {"baseline": "PROBE", "side": side, "entry": r['close'],
                   "stop": r['close'] - sgn * STOP_ATR * r['atr'],
                   "target": r['close'] + sgn * TARGET_ATR * r['atr'],
                   "exit_on_bias_neutral": False}
            snap = build_snapshot(rows[:i + 1], sig, symbol)
            out.append({"probe_id": f"{i}-{side}", "bar_seq": i, "side": side,
                        "time": r.get('time'), "snapshot": snap})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="research/out/probe_snapshots.jsonl")
    ap.add_argument("--step", type=int, default=1)
    a = ap.parse_args()

    rows, present, missing = load_csv(a.csv)
    print(f"{a.csv}: {len(rows)} bars")
    ohlc = {'time', 'open', 'high', 'low', 'close', 'volume'}
    ace_fields = [p for p in present if p not in ohlc]
    print(f"ACE fields present: {len(ace_fields)} -> {', '.join(ace_fields)}")
    if missing:
        print("absent from this collection:", ", ".join(missing))

    items = probe(rows, step=a.step)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False, default=str) + "\n")
    print(f"{len(items)} probe snapshots ({len(items)//2} bars x 2 directions) -> {a.out}")
    print("No outcomes computed. Probe mode cannot produce a verdict.")


if __name__ == "__main__":
    main()
