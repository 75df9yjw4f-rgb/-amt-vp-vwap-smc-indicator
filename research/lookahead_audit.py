"""Proves the harness cannot see the future.

Method: build the snapshot and the baseline signal for bar i, then overwrite
every bar after i with random values and rebuild. If anything downstream of bar i
had leaked in, the snapshot hash or the signal would change. Both must be
identical for every bar tested.

This is a test of the harness, not an argument about it.
"""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace_data import load_csv, rederive
from baselines import BASELINES
from snapshot import build as build_snapshot


def audit(path, samples=150, seed=3):
    rows, _, _ = load_csv(path)
    rng = random.Random(seed)
    idx = [i for i in range(60, len(rows) - 5)]
    rng.shuffle(idx)
    idx = idx[:samples]

    checked = failures = 0
    for i in idx:
        history = rows[:i + 1]
        base = {}
        for name, fn in BASELINES.items():
            sig = fn(history)
            base[name] = (sig, build_snapshot(history, sig)["snapshot_hash"]
                          if sig else None)

        saved = [dict(r) for r in rows[i + 1:]]
        for r in rows[i + 1:]:
            for k in ("open", "high", "low", "close", "bias", "confidence",
                      "dev_poc", "dev_vah", "dev_val", "vwap_sess",
                      "band_u2", "band_l2", "swing_hi", "swing_lo",
                      "disp_up", "disp_dn"):
                if r.get(k) is not None:
                    r[k] = r[k] * rng.uniform(0.5, 1.5) + rng.uniform(-10, 10)

        rederive(rows)          # derived fields must be recomputed, or a leak
                                # hiding in them would never be exercised
        history2 = rows[:i + 1]
        for name, fn in BASELINES.items():
            sig2 = fn(history2)
            h2 = build_snapshot(history2, sig2)["snapshot_hash"] if sig2 else None
            checked += 1
            if (sig2, h2) != base[name]:
                failures += 1
                print(f"  LEAK at bar {i}, baseline {name}")

        for r, s in zip(rows[i + 1:], saved):
            r.update(s)
        rederive(rows)

    print(f"lookahead audit: {checked} checks over {len(idx)} bars, "
          f"{failures} leak(s)")
    return failures


if __name__ == "__main__":
    sys.exit(1 if audit(sys.argv[1] if len(sys.argv) > 1
                        else "research/data/SYNTHETIC-mechanics-test.csv") else 0)
