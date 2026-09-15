"""Walk-forward runner. Advances the stream by applying decisions in order.

A HOLD frees the next candidate immediately; only a taken trade costs its
duration plus the cooldown. The sequence of decision points therefore depends on
the decisions themselves and cannot be precomputed, which is why this is a step
loop rather than a batch.

The journal handed back contains only trades already CLOSED at the bar being
decided. Outcomes are computed after a decision is recorded, never before.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import load, candidates, features, simulate, COOLDOWN

STATE = 'research/blank/state.json'
BARS = 'research/blank/FORWARD.csv'
BATCH = 10          # journal refresh granularity; see docs/23 section 7
MAX_TRADES = 100


def fresh(b):
    return {'cursor': 0, 'busy_until': -1, 'trades': [], 'pending': []}


def next_slots(b, cands, st, k=BATCH):
    out = []
    i = st['cursor']
    while i < len(cands) and len(out) < k:
        bar, d = cands[i]
        if bar >= st['busy_until']:
            out.append({'idx': i, 'bar': bar, 'dir': d, 'f': features(b, bar)})
        i += 1
    return out


def main():
    b = load(BARS)
    cands = candidates(b)
    st = json.load(open(STATE)) if os.path.exists(STATE) else fresh(b)

    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        decs = json.load(open(sys.argv[2]))
        for d in decs:
            slot = next((s for s in st['pending'] if s['idx'] == d['idx']), None)
            if slot is None:
                continue
            st['cursor'] = slot['idx'] + 1
            # Blocking must be re-checked inside the batch: an earlier decision
            # in the same batch can open a position that covers a later slot.
            # Without this the run would overlap trades.
            if slot['bar'] < st['busy_until']:
                st['trades'].append({'bar': slot['bar'], 'decision': 'BLOCKED',
                                     'reason': 'position open', 'f': slot['f']})
                continue
            if d['decision'] == 'HOLD':
                st['trades'].append({'bar': slot['bar'], 'decision': 'HOLD',
                                     'reason': d['reason'], 'f': slot['f']})
                continue
            o = simulate(b, slot['bar'], d['decision'])
            if o is None:
                continue
            st['busy_until'] = slot['bar'] + o['bars'] + COOLDOWN
            st['trades'].append({'bar': slot['bar'], 'decision': d['decision'],
                                 'reason': d['reason'], 'f': slot['f'], **o})
        st['pending'] = next_slots(b, cands, st)
        json.dump(st, open(STATE, 'w'))

    if not st['pending']:
        st['pending'] = next_slots(b, cands, st)
        json.dump(st, open(STATE, 'w'))

    taken = [t for t in st['trades'] if t['decision'] in ('LONG', 'SHORT')]
    closed = [t for t in taken if 'r' in t]
    blocked = sum(1 for t in st['trades'] if t['decision'] == 'BLOCKED')
    holds = sum(1 for t in st['trades'] if t['decision'] == 'HOLD')
    print(f"=== сделок взято {len(taken)}, HOLD {holds}, заблокировано {blocked}, "
          f"кандидатов пройдено {st['cursor']}/{len(cands)} ===")
    if closed:
        import statistics
        rs = [t['r'] for t in closed]
        w = sum(1 for x in rs if x > 0)
        print(f"ЖУРНАЛ (только закрытые): exp {statistics.mean(rs):+.3f}R  "
              f"побед {w}/{len(rs)} ({w/len(rs):.0%})  итог {sum(rs):+.1f}R")
        print("последние 8 сделок:")
        for t in closed[-8:]:
            print(f"   bar {t['bar']:5d} {t['decision']:<5s} {t['outcome']:<6s} "
                  f"{t['r']:+.1f}R  ({t['reason'][:46]})")
    if len(taken) >= MAX_TRADES:
        print("\nДОСТИГНУТ ПРЕДЕЛ 100 СДЕЛОК — прогон завершён")
        return
    print(f"\n--- СЛЕДУЮЩИЕ {len(st['pending'])} КАНДИДАТОВ ---")
    print(f"  {'idx':>4s} {'bar':>5s} {'напр':>8s} {'ч':>3s} {'poz':>5s} "
          f"{'rng':>5s} {'vol':>5s} {'ход20':>7s} {'ход60':>7s} {'диап60':>7s} "
          f"{'run60':>6s} {'сесс':>6s}")
    for s in st['pending']:
        f = s['f']
        run = abs(f['net_move_60']) / f['range_60_vs_med'] if f['range_60_vs_med'] else 0
        print(f"  {s['idx']:>4d} {s['bar']:>5d} {s['dir']:>8s} {f['hour_utc']:>3d} "
              f"{f['bar_pos']:>5.2f} {f['range_vs_med100']:>5.1f} "
              f"{f['realized_vol_20']:>5.2f} {f['net_move_20']:>+7.1f} "
              f"{f['net_move_60']:>+7.1f} {f['range_60_vs_med']:>7.1f} "
              f"{run:>6.2f} {f['close_vs_session_open']:>+6.1f}")


if __name__ == '__main__':
    main()
