"""Leave-one-segment-out: the only honest validation left once data runs out.

A filter is chosen on two segments and judged on the third, rotating. Picking
the best threshold on all three and reporting it would be the overfitting this
whole run is meant to avoid.

Caveat that cannot be removed: the candidate feature list and the grid were
written after looking at all three segments, so this is optimistic. It bounds
the answer from above, not from below.
"""
import itertools
import statistics
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import load, features   # noqa: E402
from engine import simulate, WARMUP   # noqa: E402

EX = {"sl_pct": 0.15, "tp_pct": 0.15, "max_bars": 48, "cooldown": 20}
SEGS = [('SEG-1', 'research/loop/TEST.csv'),
        ('SEG-2/3', 'research/blank/FORWARD.csv'),
        ('SEG-4', 'research/loop/SEG4.csv')]

GRID = [('net20', '>', th) for th in (-2.0, -1.5, -1.0, -0.5, 0.0)] + \
       [('net60', '<=', th) for th in (-2.0, -1.0, 0.0, 1.0)] + \
       [('span20', '<=', th) for th in (2.5, 3.0, 3.5)] + \
       [('pos60', '<=', th) for th in (0.25, 0.5, 0.75)] + \
       [('vol20', '<=', th) for th in (0.4, 0.5, 0.6)]


def candidates(path):
    b = load(path)
    busy = -1
    out = []
    for i in range(WARMUP, len(b)):
        if i < busy:
            continue
        f = features(b[:i + 1], i)
        if not (f['rng'] < 0.5 and f['span20'] < 4):
            continue
        o = simulate(b, i, 'SHORT', EX)
        if o is None:
            break
        out.append((f, o))
        busy = i + o['bars'] + EX['cooldown']
    return out


def keep(f, cond):
    k, op, th = cond
    return f[k] > th if op == '>' else f[k] <= th


def score(rows, conds):
    sel = [o['r'] for f, o in rows if all(keep(f, c) for c in conds)]
    return (statistics.mean(sel), len(sel), sum(1 for r in sel if r > 0)) if len(sel) >= 10 else (None, len(sel), 0)


def main():
    data = {n: candidates(p) for n, p in SEGS}
    print("базовый уровень (без дополнительного фильтра):")
    for n, _ in SEGS:
        m, k, w = score(data[n], [])
        print(f"  {n:<9s} n={k:3d} wr={w/k:.2f} meanR={m:+.3f}")

    print("\nLEAVE-ONE-SEGMENT-OUT, лучший ОДИН фильтр по двум сегментам → проверка на третьем:")
    lifts = []
    for held, _ in SEGS:
        train = [r for n, _ in SEGS if n != held for r in data[n]]
        best, bestm = None, -9
        for c in GRID:
            m, k, _ = score(train, [c])
            if m is not None and m > bestm:
                best, bestm = c, m
        base_m, base_k, base_w = score(data[held], [])
        m, k, w = score(data[held], [best])
        cond = f"{best[0]} {best[1]} {best[2]}"
        if m is None:
            print(f"  держим {held:<9s} выбран [{cond:<16s}] → на отложенном осталось {k} сделок, мало для вывода")
            continue
        lifts.append(m - base_m)
        print(f"  держим {held:<9s} выбран [{cond:<16s}] обучение {bestm:+.3f}R  →  "
              f"отложенный n={k:3d} wr={w/k:.2f} meanR={m:+.3f}  (было {base_m:+.3f}, "
              f"сдвиг {m-base_m:+.3f}R)")
    if len(lifts) == 3:
        good = sum(1 for x in lifts if x > 0)
        print(f"\n  улучшение на отложенном сегменте: {good} из 3, средний сдвиг {statistics.mean(lifts):+.3f}R")
        print("  ВЕРДИКТ:", "фильтр переносится" if good == 3 else
              "устойчивого переноса нет — на части сегментов фильтр вредит")


if __name__ == '__main__':
    main()
