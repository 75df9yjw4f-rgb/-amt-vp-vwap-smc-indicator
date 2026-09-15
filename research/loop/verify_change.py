"""Did the new policy actually change decisions, or only the journal?"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from policy import load_all
from behavior_diff import at_points, free_replay
from ledger import Ledger

old_v, new_v = int(sys.argv[1]), int(sys.argv[2])
pols = {p.version: p for p in load_all('research/loop/policies')}
old, new = pols[old_v], pols[new_v]
decs = Ledger('research/loop/state/ledger.jsonl').decisions()

flips = at_points(decs, old, new)
print(f"=== v{old_v} → v{new_v}: контрфактуальная проверка ===")
print(f"точек решения в истории: {len(decs)}")
print(f"решений, которые ИЗМЕНИЛИСЬ бы: {len(flips)}")
byk = {}
for f in flips:
    byk[(f['old'], f['new'])] = byk.get((f['old'], f['new']), 0) + 1
for (a, b), n in sorted(byk.items()):
    print(f"   {a} → {b}: {n}")
acted = [f for f in flips if f['actual'] != 'HOLD']
print(f"из них там, где сделка РЕАЛЬНО была открыта: {len(acted)}")
for f in acted:
    print(f"   бар {f['bar']}: было {f['actual']}, стало бы {f['new']}")
if not flips:
    print("\nВЕРДИКТ: правило НИЧЕГО не изменило — это текст в журнале, а не поведение.")
else:
    print(f"\nВЕРДИКТ: поведение изменено, {len(flips)} решений расходятся.")

# Capped at the last decided bar: replaying the whole segment would show
# aggregates over bars not yet decided, and that is an input leak into the next
# policy. See ledger BREACH record from batch 2.
horizon = max(d['bar'] for d in decs) + 1
t_old = free_replay('research/loop/TEST.csv', old, upto=horizon)
t_new = free_replay('research/loop/TEST.csv', new, upto=horizon)
def s(t):
    r = [x['r'] for x in t]
    return f"n={len(t):3d} итог {sum(r):+5.1f}R побед {sum(1 for v in r if v>0)}/{len(r)}"
print(f"\nнезависимый прогон до бара {horizon} (дальше не смотрим):")
print(f"   v{old_v}: {s(t_old)}")
print(f"   v{new_v}: {s(t_new)}")
