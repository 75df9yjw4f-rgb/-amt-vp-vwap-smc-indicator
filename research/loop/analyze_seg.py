"""Per-segment analysis of a finished ledger."""
import json, statistics, sys, os
from math import comb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from policy import load_all
from engine import simulate
from features import load

led, bars, poldir = sys.argv[1], sys.argv[2], sys.argv[3]
recs = [json.loads(l) for l in open(led)]
outs = [r['payload'] for r in recs if r['kind'] == 'OUTCOME']
decs = [r['payload'] for r in recs if r['kind'] == 'DECISION']
d = {r['hash']: r['payload'] for r in recs if r['kind'] == 'DECISION'}
rs = [o['r'] for o in outs]
n, w = len(rs), sum(1 for r in rs if r > 0)
p = min(1.0, sum(comb(n, k) for k in range(0, min(w, n - w) + 1)) / 2 ** n * 2)
print(f"n={n} побед {w} ({w/n:.0%}) итог {sum(rs):+.1f}R ожидание {statistics.mean(rs):+.3f}R p(≠50%)={p:.3f}")
print("исходы:", {k: sum(1 for o in outs if o['outcome'] == k) for k in ('TARGET', 'STOP', 'TIME')},
      f" средняя длительность {statistics.mean(o['bars'] for o in outs):.1f} баров")

P = {pp.version: pp for pp in load_all(poldir)}
cur = P[max(P)]
nofilter = type(cur)({**cur.to_dict(), 'rules': [r for r in cur.to_dict()['rules'] if r['id'] != 'R0']})
fl = [x for x in decs if nofilter.decide(x['features'])[0] != cur.decide(x['features'])[0]]
b = load(bars)
tot = ww = 0
for x in fl:
    o = simulate(b, x['bar'], 'SHORT', cur.exits)
    if o:
        tot += o['r']; ww += o['r'] > 0
if fl:
    print(f"R0 заблокировал {len(fl)}; постфактум они дали бы {tot:+.1f}R, побед {ww}/{len(fl)} ({ww/len(fl):.0%})")
    print(f"  → L2 на этом сегменте: {'подтверждён' if ww/len(fl) < 0.5 else 'ОПРОВЕРГНУТ (резал прибыль)'}")
