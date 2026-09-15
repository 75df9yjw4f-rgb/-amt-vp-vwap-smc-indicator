"""What Claude is allowed to see between batches: closed trades only.

Nothing here reaches past the last closed trade. The next undecided bar index is
printed so the next policy version can declare a lawful effective_from_bar.
"""
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ledger import Ledger        # noqa: E402
from policy import load_all      # noqa: E402
import beliefs as B              # noqa: E402

LED = 'research/loop/state/ledger.jsonl'
POL = 'research/loop/policies'
BEL = 'research/loop/state/beliefs.json'


def main():
    led = Ledger(LED)
    ok, bad = led.verify()
    decs = led.decisions()
    outs = led.outcomes()
    by_hash = {}
    for r in led.read():
        if r['kind'] == 'DECISION':
            by_hash[r['hash']] = r['payload']

    print(f"ЛЕДЖЕР: {len(led.read())} записей, целостность {'OK' if ok else 'НАРУШЕНА: '+str(bad)}")
    print(f"решений {len(decs)}  сделок {len(outs)}  "
          f"HOLD {sum(1 for d in decs if d['action']=='HOLD')}")
    if outs:
        rs = [o['r'] for o in outs]
        w = sum(1 for r in rs if r > 0)
        print(f"итог {sum(rs):+.1f}R  ожидание {statistics.mean(rs):+.3f}R  "
              f"побед {w}/{len(rs)} ({w/len(rs):.0%})")
    print(f"следующий нерешённый бар: {max((d['bar'] for d in decs), default=119)+1}")

    print("\nЗАКРЫТЫЕ СДЕЛКИ")
    print(f"  {'#':>3s} {'бар':>5s} {'v':>2s} {'прав':>4s} {'напр':>5s} {'исх':<6s} "
          f"{'R':>5s} {'rng':>5s} {'span20':>6s} {'net20':>6s} {'pos60':>5s} {'час':>3s}")
    for n, o in enumerate(outs, 1):
        f = by_hash.get(o['decision_hash'], {}).get('features', {})
        print(f"  {n:>3d} {o['bar']:>5d} {o['policy_version']:>2d} "
              f"{str(o['rule_id']):>4s} {o['side']:>5s} {o['outcome']:<6s} "
              f"{o['r']:>+5.1f} {f.get('rng',0):>5.2f} {f.get('span20',0):>6.2f} "
              f"{f.get('net20',0):>+6.2f} {f.get('pos60',0):>5.2f} {f.get('hour',0):>3d}")

    bl = B.load(BEL)
    if bl:
        ev = B.evaluate(bl, outs, by_hash)
        print("\nУБЕЖДЕНИЯ (статус пересчитан механически)")
        for e in ev:
            print(f"  {e['id']:<4s} n={e['n']:>3d} побед={e['wins']:>3d} "
                  f"wr={e['win_rate'] if e['win_rate'] is not None else '—'} "
                  f"{e['status_prev']} → {e['status']}"
                  f"{'  ИЗМЕНИЛОСЬ' if e['changed'] else ''}")
            print(f"       {e['statement']}")
        B.save(BEL, [{k: v for k, v in e.items()
                      if k in ('id', 'statement', 'scope', 'status', 'history')}
                     | {'history': e.get('history', []) +
                        ([f"{e['status_prev']}→{e['status']} @n={e['n']}"] if e['changed'] else [])}
                     for e in ev])

    pols = load_all(POL)
    print("\nПОЛИТИКИ")
    for p in pols:
        print(f"  v{p.version} с бара {p.effective_from_bar}: "
              f"{len(p.rules)} правил, гипотеза {p.hypothesis['id']} — {p.rationale[:70]}")


if __name__ == '__main__':
    main()
