"""Phase 0 harness: CSV -> point-in-time snapshots -> baseline signals ->
veto decision -> decision log.

Order of operations matters and is enforced here: the decision is taken and
written before simulate() is ever called for that signal, so the outcome cannot
reach the decider (docs/15 section 7.4).
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace_data import load_csv
from baselines import BASELINES, SCALP, pct_book, regime, ace_context
from snapshot import build as build_snapshot
from outcomes import simulate
import deciders


def run(rows, decider, symbol="ANON-1", timeframe="TF-A", which=("B1", "B2", "B3"),
        book=None):
    log, open_until = [], {}
    for i in range(len(rows)):
        history = rows[:i + 1]          # the ONLY thing a decision may see
        for name in which:
            if i < open_until.get(name, -1):
                continue                # one position per baseline at a time
            if not rows[i].get('gap_ok', True):
                continue        # hole in the series; see mark_gaps()
            sig = (book or BASELINES)[name](history)
            if not sig:
                continue

            snap = build_snapshot(history, sig, symbol, timeframe)
            decision = decider(snap)    # decided BEFORE any outcome exists

            rec = {
                "bar_seq": i,
                "time": rows[i].get("time"),
                "symbol": symbol, "timeframe": timeframe,
                "snapshot_hash": snap["snapshot_hash"],
                "snapshot": snap,
                "baseline": name,
                "baseline_decision": {k: sig[k] for k in
                                      ("side", "entry", "stop", "target")},
                "claude_decision": decision["decision"],
                "veto_reason": decision.get("reason_code"),
                "facts_used": decision.get("facts_used", []),
                "facts_missing": decision.get("facts_missing", []),
                "conflicts": decision.get("conflicts", []),
                "reason": decision.get("reason", ""),
                "regime": snap["regime"]["label"],
                "ace_context": snap["ace_score"]["context_strength"],
                "planned_rr": snap["proposed_trade"]["planned_rr"],
            }

            # Outcome is computed afterwards, by a separate call, and is written
            # to its own block. Arm A needs it for every signal; arm B reads the
            # same field and simply excludes the ones it vetoed.
            out = simulate(rows, i, sig)
            rec["outcome"] = out or {"outcome": "INVALID"}
            rec["hallucinated"] = _hallucinated(decision.get("facts_used", []), snap)
            log.append(rec)
            if out and out.get("bars_held"):
                open_until[name] = i + out["bars_held"]
    return log


def _hallucinated(facts, snap):
    """True if a cited fact is not a path that exists in the snapshot."""
    for f in facts:
        node, ok = snap, True
        for part in f.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                ok = False
                break
        if not ok:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--decider", default="accept_all",
                    choices=["accept_all", "random", "claude"])
    ap.add_argument("--veto-rate", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tgt-pct", type=float,
                    help="fixed take-profit as a %% of entry price")
    ap.add_argument("--stop-pct", type=float,
                    help="fixed stop as a %% of entry price")
    ap.add_argument("--scalp", action="store_true",
                    help="use the symmetric 1:1 variants B1s/B2s/B3s")
    ap.add_argument("--out", default="research/out/decisions.jsonl")
    args = ap.parse_args()

    if args.decider == "accept_all":
        dec = deciders.accept_all
    elif args.decider == "random":
        dec = deciders.make_random_veto(args.veto_rate, args.seed)
    else:
        dec = deciders.claude_stub

    all_log = []
    for n, path in enumerate(args.csv, 1):
        rows, present, missing = load_csv(path)
        print(f"{path}: {len(rows)} bars | ACE fields present: {len(present)} "
              f"| absent from export: {len(missing)}")
        if missing:
            print("  absent:", ", ".join(missing))
        if args.tgt_pct:
            book = pct_book(args.tgt_pct, args.stop_pct or args.tgt_pct)
        else:
            book = SCALP if args.scalp else None
        names = tuple(book) if book else ("B1", "B2", "B3")
        all_log += run(rows, dec, symbol=f"ANON-{n}", which=names, book=book)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in all_log:
            fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    print(f"{len(all_log)} decisions -> {args.out}")


if __name__ == "__main__":
    main()
