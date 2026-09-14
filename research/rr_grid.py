"""Exploratory sweep of the reward-to-risk ratio, stop held fixed.

This runs AFTER the held-out verdict, so it is hypothesis generation and not
evidence: the set it runs on has already been looked at. The whole grid is
printed rather than a single ratio, because reporting one cell chosen after the
fact is how a sweep turns into a fitted result.

No veto decisions are needed - the bracket is mechanical - so this uses the full
population instead of a sample.
"""
import json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ace_data import load_csv
from baselines import pct_book
from outcomes import simulate

STOP_PCT = 0.15


def run(rows, tgt_pct, stop_pct):
    book = pct_book(tgt_pct, stop_pct)
    out, open_until = [], {}
    for i in range(len(rows)):
        if not rows[i].get('gap_ok', True):
            continue
        for name, fn in book.items():
            if i < open_until.get(name, -1):
                continue
            sig = fn(rows[:i + 1])
            if not sig:
                continue
            o = simulate(rows, i, sig)
            if o and o.get('r_multiple') is not None:
                out.append((name, rows[i], sig, o))
                open_until[name] = i + o['bars_held']
    return out


def stats(rs):
    if not rs:
        return None
    w = [r for r in rs if r > 0]
    l = [r for r in rs if r <= 0]
    gw, gl = sum(w), -sum(l)
    eq = peak = dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return (len(rs), sum(rs) / len(rs), len(w) / len(rs),
            gw / gl if gl > 0 else float('inf'), eq, dd)


def mech_M(bias, side):
    if bias is None:
        return 'ACCEPT'
    if side == 'LONG' and bias <= -0.15:
        return 'VETO'
    if side == 'SHORT' and bias >= 0.15:
        return 'VETO'
    return 'ACCEPT'


rows, _, _ = load_csv('research/data/XAU-HELDOUT.csv')
print(f"{'R:R':>5s} {'цель%':>7s} {'сделок':>7s} {'expect':>9s} {'winrate':>9s}"
      f" {'нужно':>7s} {'PF':>6s} {'итог R':>9s} {'maxDD':>7s}")
print("-" * 74)
grid = {}
for rr in (0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
    tgt = round(STOP_PCT * rr, 4)
    res = run(rows, tgt, STOP_PCT)
    grid[rr] = res
    n, ex, wr, pf, tot, dd = stats([o['r_multiple'] for _, _, _, o in res])
    need = 1.0 / (1.0 + rr)          # break-even win rate at this R:R
    print(f"{rr:>5.1f} {tgt:>7.3f} {n:>7d} {ex:>+9.3f} {wr:>8.1%} {need:>7.1%}"
          f" {pf:>6.2f} {tot:>+9.2f} {dd:>7.2f}")

print("\n'нужно' — winrate безубытка при данном R:R. Сравнивайте с фактическим.")

print("\n=== R:R 0.8 подробно: арм 1 против M ===")
res = grid[0.8]
allr = [o['r_multiple'] for _, _, _, o in res]
macc = [o['r_multiple'] for _, r, s, o in res
        if mech_M(r.get('bias'), s['side']) == 'ACCEPT']
mvet = [o['r_multiple'] for _, r, s, o in res
        if mech_M(r.get('bias'), s['side']) == 'VETO']
for lab, rs in (('Baseline      ', allr), ('+ Mechanical M', macc)):
    n, ex, wr, pf, tot, dd = stats(rs)
    print(f"  {lab} n={n:4d} exp {ex:+.3f}R  wr {wr:.1%}  PF {pf:.2f}  "
          f"итог {tot:+.2f}R  DD {dd:.2f}")
if mvet:
    n, ex, wr, *_ = stats(mvet)
    print(f"  M отсёк {n} сделок, их ожидание {ex:+.3f}R, winrate {wr:.1%}")

print("\n=== по правилу при R:R 0.8 ===")
for b in ('B1p', 'B2p', 'B3p'):
    rs = [o['r_multiple'] for nm, _, _, o in res if nm == b]
    if rs:
        n, ex, wr, pf, tot, dd = stats(rs)
        print(f"  {b}: n={n:4d}  exp {ex:+.3f}R  wr {wr:.1%}  PF {pf:.2f}  итог {tot:+.2f}R")
