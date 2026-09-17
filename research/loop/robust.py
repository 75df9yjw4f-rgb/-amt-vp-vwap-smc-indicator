"""Robustness checks for a segment result. Bypasses the ledger (fast path);
the ledger run is the authoritative one, this only stress-tests it.
"""
import statistics, sys, os
from math import comb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import load, features
from engine import simulate, WARMUP

def sweep(path, pcts, filt=True, quarters=1):
    b = load(path)
    for pct in pcts:
        ex = {"sl_pct": pct, "tp_pct": pct, "max_bars": 48, "cooldown": 20}
        busy = -1; rows = []
        for i in range(WARMUP, len(b)):
            if i < busy: continue
            f = features(b[:i+1], i)
            if not (f['rng'] < 0.5 and f['span20'] < 4): continue
            if filt and f['net20'] <= -1.0: continue
            o = simulate(b, i, 'SHORT', ex)
            if o is None: break
            rows.append((i, o)); busy = i + o['bars'] + ex['cooldown']
        rs = [o['r'] for _, o in rows]
        if not rs: continue
        n = len(rs); w = sum(1 for r in rs if r > 0)
        p = min(1.0, sum(comb(n, k) for k in range(0, min(w, n-w)+1))/2**n*2)
        line = f"  скобка {pct:>6.3f}%  n={n:3d} побед {w/n:.2f} итог {sum(rs):+6.1f}R ожид {statistics.mean(rs):+.3f}R p={p:.3f}"
        if quarters > 1:
            step = len(b)//quarters
            qs = []
            for q in range(quarters):
                sel = [o['r'] for i, o in rows if q*step <= i < (q+1)*step]
                qs.append(f"{statistics.mean(sel):+.2f}({len(sel)})" if len(sel) >= 5 else "—")
            line += "   по четвертям: " + " ".join(qs)
        print(line)

if __name__ == '__main__':
    print("SEG-5 (15м), с фильтром R0 — чувствительность к скобке и стабильность по времени:")
    sweep('research/loop/SEG5.csv', [0.25, 0.30, 0.376, 0.45, 0.55], quarters=4)
    print("\nSEG-5 БЕЗ фильтра R0 (чтобы отделить вклад гипотезы от вклада урока):")
    sweep('research/loop/SEG5.csv', [0.376], filt=False, quarters=4)
