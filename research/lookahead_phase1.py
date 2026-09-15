"""Proves the Phase 1 entry logic cannot see the future.

The full bar list is passed in every time - not a slice - so mutating later bars
genuinely reaches the code under test. Entries are collected with `entries_only`,
which drops exit simulation and the one-position block: with blocking on, an
entry before bar i can change when a later bar moves, because the exit of an
earlier trade decides whether a slot was free, and that is not a leak.

The negative control matters as much as the audit: with the FVG allowed to be
read on its own formation bar, the audit must fail. One that cannot fail proves
nothing.
"""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ace_data import load_csv, rederive
from phase1 import run


def audit(rows, thr=0.15, samples=40, seed=11, leak=False):
    rng = random.Random(seed)
    idx = [i for i in range(300, len(rows) - 100)]
    rng.shuffle(idx)
    idx = idx[:samples]
    checked = fails = 0
    for i in idx:
        base = [e for e in run(rows, thr, entries_only=True,
                               _leak_next_bar=leak) if e['bar'] <= i]
        saved = [dict(r) for r in rows[i + 1:]]
        for r in rows[i + 1:]:
            for k in ('open', 'high', 'low', 'close', 'bias',
                      'swing_hi', 'swing_lo'):
                if r.get(k) is not None:
                    r[k] = r[k] * rng.uniform(0.5, 1.5) + rng.uniform(-20, 20)
        rederive(rows)
        after = [e for e in run(rows, thr, entries_only=True,
                                _leak_next_bar=leak) if e['bar'] <= i]
        checked += 1
        if base != after:
            fails += 1
        for r, s in zip(rows[i + 1:], saved):
            r.update(s)
        rederive(rows)
    return checked, fails


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'research/data/XAU-HELDOUT.csv'
    rows, _, _ = load_csv(path)
    c, f = audit(rows)
    print(f"аудит Phase 1: {c} проверок, утечек {f}")
    c2, f2 = audit(rows, samples=30, seed=12, leak=True)
    print(f"негативный контроль (чтение бара i+20): {c2} проверок, утечек {f2}"
          f"  -> {'СРАБОТАЛ' if f2 else 'НЕ СРАБОТАЛ, аудит бесполезен'}")
    sys.exit(1 if f or not f2 else 0)
