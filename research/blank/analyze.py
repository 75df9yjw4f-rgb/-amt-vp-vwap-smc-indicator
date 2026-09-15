"""Loss taxonomy for the blank-chart run. Categories are the ones frozen in
docs/23 section 8 and are computed from the recorded trade, never chosen after.
"""
import json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import load, candidates, features, MAX_BARS

b = load('research/blank/FORWARD.csv')
st = json.load(open('research/blank/state.json'))
cands = candidates(b)

# median net_move_20 over ALL candidates — the reference the protocol names
med_nm20 = statistics.median(abs(features(b, bar)['net_move_20']) for bar, _ in cands)

taken = [t for t in st['trades'] if t['decision'] in ('LONG', 'SHORT')]
taken.sort(key=lambda t: t['bar'])


def vol_during(i, bars, side):
    seg = b[i + 1:i + bars + 1]
    if len(seg) < 3:
        return None
    rng = statistics.mean(x['h'] - x['l'] for x in seg)
    pre = b[max(0, i - 19):i + 1]
    rng0 = statistics.mean(x['h'] - x['l'] for x in pre)
    return rng / rng0 if rng0 else None


CATS = ['ENTERED_EXTENDED', 'RANGE_BOUND', 'AGAINST_MOMENTUM', 'EARLY',
        'STOP_TOO_TIGHT', 'TARGET_TOO_FAR', 'VOL_SHIFT', 'POST_LOSS_FLIP']

prev_loss_run = []          # outcomes in order, to evaluate POST_LOSS_FLIP
for n, t in enumerate(taken):
    f = t['f']
    c = set()
    if abs(f['net_move_20']) > 2 * med_nm20:
        c.add('ENTERED_EXTENDED')
    if f['range_60_vs_med'] < 1.5:
        c.add('RANGE_BOUND')
    sgn = 1 if t['decision'] == 'LONG' else -1
    if f['net_move_20'] * sgn < 0:
        c.add('AGAINST_MOMENTUM')
    if t.get('mfe_before_mae') is not None and t['mfe_before_mae'] < 0.3:
        c.add('EARLY')
    if t['outcome'] == 'STOP' and t.get('mfe_after_stop', 0) >= 0.8:
        c.add('STOP_TOO_TIGHT')
    if 0.5 <= t['mfe'] < 1.0 and t['outcome'] != 'TARGET':
        c.add('TARGET_TOO_FAR')
    v = vol_during(t['bar'], t['bars'], t['decision'])
    if v is not None and v < 0.7:
        c.add('VOL_SHIFT')
    # within 2 trades after a loss AND opposite direction to the previous trade
    if n >= 1:
        recent = taken[max(0, n - 2):n]
        if any(x['r'] < 0 for x in recent) and taken[n - 1]['decision'] != t['decision']:
            c.add('POST_LOSS_FLIP')
    if not c:
        c.add('UNCLASSIFIED')
    t['cats'] = sorted(c)

losers = [t for t in taken if t['r'] < 0]
winners = [t for t in taken if t['r'] > 0]
flat = [t for t in taken if t['r'] == 0]
print(f"сделок {len(taken)}  убыточных {len(losers)}  прибыльных {len(winners)}  нулевых {len(flat)}")
print(f"итог {sum(t['r'] for t in taken):+.2f}R   ожидание {statistics.mean(t['r'] for t in taken):+.3f}R")
print(f"медиана |net_move_20| по всем {len(cands)} кандидатам: {med_nm20:.2f}\n")
print(f"{'категория':<18s} {'убыт':>8s} {'приб':>8s} {'отнош':>7s}  доминирует?")
dom = []
for k in CATS + ['UNCLASSIFIED']:
    nl = sum(1 for t in losers if k in t['cats'])
    nw = sum(1 for t in winners if k in t['cats'])
    sl = nl / len(losers) if losers else 0
    sw = nw / len(winners) if winners else 0
    ratio = (sl / sw) if sw else float('inf') if sl else 0.0
    ok = sl >= 0.50 and ratio >= 1.5
    if ok:
        dom.append(k)
    print(f"{k:<18s} {nl:>3d} ({sl:>3.0%}) {nw:>3d} ({sw:>3.0%}) {ratio:>7.2f}  {'ДА' if ok else '—'}")
print()
print("ДОМИНИРУЮЩАЯ ПРИЧИНА:", ', '.join(dom) if dom else "НЕТ — ни одна категория не прошла критерий (>=50% убытков И >=1.5x доля у победителей)")
json.dump(taken, open('research/blank/classified.json', 'w'), ensure_ascii=False, indent=1)
