"""Did the new policy actually change decisions, or only the journal?

Refuses to answer on an empty record. An earlier version hardcoded a ledger
path; when that file was gone it read zero decisions and cheerfully reported
"the rule changed nothing" — a verdict manufactured from missing data. A check
that returns a confident answer when it has no input is worse than no check.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from policy import load_all             # noqa: E402
from behavior_diff import at_points, free_replay   # noqa: E402
from ledger import Ledger               # noqa: E402

if len(sys.argv) < 5:
    sys.exit('Запуск: verify_change.py <старая версия> <новая версия> <леджер> <файл баров> '
             '[каталог политик]')
old_v, new_v, led_path, bars = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
poldir = sys.argv[5] if len(sys.argv) > 5 else 'research/loop/policies'

pols = {p.version: p for p in load_all(poldir)}
for v in (old_v, new_v):
    if v not in pols:
        sys.exit(f'версии v{v} нет в {poldir}')
old, new = pols[old_v], pols[new_v]

if not os.path.exists(led_path):
    sys.exit(f'ВЕРДИКТА НЕТ: леджера {led_path} не существует.')
decs = Ledger(led_path).decisions()
if not decs:
    sys.exit(f'ВЕРДИКТА НЕТ: в {led_path} нет ни одного решения. '
             'Отсутствие данных — это не «правило ничего не изменило».')

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
for f in acted[:20]:
    print(f"   бар {f['bar']}: было {f['actual']}, стало бы {f['new']}")
print("\nВЕРДИКТ: " + ("правило НИЧЕГО не изменило — это текст в журнале, а не поведение."
                       if not flips else f"поведение изменено, {len(flips)} решений расходятся."))

# Capped at the last decided bar: replaying further would show aggregates over
# bars not yet decided, and that is an input leak into the next policy.
horizon = max(d['bar'] for d in decs) + 1
t_old = free_replay(bars, old, upto=horizon)
t_new = free_replay(bars, new, upto=horizon)


def s(t):
    r = [x['r'] for x in t]
    return (f"n={len(t):3d} итог {sum(r):+5.1f}R побед {sum(1 for v in r if v > 0)}/{len(r)}"
            if r else "сделок нет")


print(f"\nнезависимый прогон до бара {horizon} (дальше не смотрим):")
print(f"   v{old_v}: {s(t_old)}")
print(f"   v{new_v}: {s(t_new)}")
