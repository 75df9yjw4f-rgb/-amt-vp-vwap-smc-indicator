"""Reads probe decisions and reports what the veto layer needed - nothing else.

Deliberately computes no P&L, no expectancy and no verdict. A probe run has no
outcomes attached, so there is nothing here that could be mistaken for evidence
about edge. Its output answers one question: which ACE values would have to
leave the script for this layer to stop abstaining.
"""
import json, sys
from collections import Counter, defaultdict


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def report(snaps, decs):
    by_id = {d["probe_id"]: d for d in decs}
    snap_by_id = {s["probe_id"]: s for s in snaps}
    matched = [pid for pid in snap_by_id if pid in by_id]

    print(f"probe snapshots: {len(snaps)}   decisions: {len(decs)}   "
          f"matched: {len(matched)}")
    if not matched:
        print("nothing to report")
        return

    dist = Counter(by_id[p]["decision"] for p in matched)
    total = len(matched)
    print("\n--- decisions ---")
    for k in ("ACCEPT", "VETO", "HOLD"):
        print(f"  {k:7s} {dist.get(k,0):4d}  {dist.get(k,0)/total:6.1%}")

    # The headline: what the layer said it lacked.
    miss = Counter(f for p in matched for f in by_id[p].get("facts_missing", []))
    print("\n--- facts the veto layer reported missing ---")
    if not miss:
        print("  none reported")
    for f, n in miss.most_common(25):
        print(f"  {n:4d}  {n/total:6.1%}   {f}")

    used = Counter(f for p in matched for f in by_id[p].get("facts_used", []))
    print("\n--- facts actually cited ---")
    for f, n in used.most_common(15):
        print(f"  {n:4d}  {n/total:6.1%}   {f}")

    # Direction sensitivity: the same bar judged long and short.
    bars = defaultdict(dict)
    for p in matched:
        bars[snap_by_id[p]["bar_seq"]][snap_by_id[p]["side"]] = by_id[p]["decision"]
    paired = {b: v for b, v in bars.items() if len(v) == 2}
    same = sum(1 for v in paired.values() if v["LONG"] == v["SHORT"])
    print("\n--- direction sensitivity ---")
    print(f"  bars judged in both directions: {len(paired)}")
    if paired:
        print(f"  same answer to long and short: {same}  ({same/len(paired):.1%})")
        both_accept = sum(1 for v in paired.values()
                          if v["LONG"] == v["SHORT"] == "ACCEPT")
        print(f"  accepted BOTH directions:      {both_accept}")
        print("  a layer that answers identically in both directions is not "
              "reading direction,\n  whatever its stated reasons say.")

    hall = sum(1 for p in matched if by_id[p].get("hallucinated"))
    if hall:
        print(f"\n  decisions citing facts absent from the snapshot: {hall}")

    print("\n" + "=" * 68)
    print("NO VERDICT. A probe run carries no outcomes, so it says nothing about")
    print("whether the veto helps or hurts. It measures data sufficiency only.")
    print("=" * 68)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: probe_report.py <probe_snapshots.jsonl> <decisions.jsonl>")
        sys.exit(2)
    report(load(sys.argv[1]), load(sys.argv[2]))
