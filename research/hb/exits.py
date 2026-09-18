"""Exit families. Entries are held fixed so the difference is the exit alone."""
import sys
sys.path.insert(0, 'research/hb')
from ict import unit

FAMILIES = {
    'E1': dict(stop=3.0, target=4.0, horizon=20, trail=None, be_at=None),
    'E2': dict(stop=3.0, target=None, horizon=60, trail=3.0, be_at=None),
    'E3': dict(stop=3.0, target=None, horizon=60, trail=None, be_at=None),
    'E4': dict(stop=3.0, target=6.0, horizon=40, trail=None, be_at=2.0),
    'E5': dict(stop=3.0, target=8.0, horizon=60, trail=None, be_at=None),
}


def simulate(b, i, side, u, f):
    """Pessimistic throughout: the stop is checked before the target on every bar,
    and a trail or break-even move only ever tightens the stop."""
    e = b[i]['c']
    sgn = 1 if side == 'LONG' else -1
    stop = e - sgn * f['stop'] * u
    tgt = e + sgn * f['target'] * u if f['target'] else None
    best = e
    for m in range(1, f['horizon'] + 1):
        if i + m >= len(b):
            return None
        x = b[i + m]
        if (x['l'] <= stop) if side == 'LONG' else (x['h'] >= stop):
            return sgn * (stop - e) / (f['stop'] * u), m
        if tgt is not None and ((x['h'] >= tgt) if side == 'LONG' else (x['l'] <= tgt)):
            return f['target'] / f['stop'], m
        best = max(best, x['c']) if side == 'LONG' else min(best, x['c'])
        if f['be_at'] and sgn * (best - e) >= f['be_at'] * u:
            stop = max(stop, e) if side == 'LONG' else min(stop, e)
        if f['trail']:
            t = best - sgn * f['trail'] * u
            stop = max(stop, t) if side == 'LONG' else min(stop, t)
    x = b[i + f['horizon']]
    return sgn * (x['c'] - e) / (f['stop'] * u), f['horizon']


def run(b, sigs, cost, fam, cooldown=20):
    f = FAMILIES[fam]
    busy, out = -1, []
    for i, s in sorted(sigs):
        if i < busy:
            continue
        u = unit(b, i)
        r = simulate(b, i, s, u, f)
        if r is None:
            break
        out.append((b[i]['t'], s, r[0] - cost / (f['stop'] * u)))
        busy = i + r[1] + cooldown
    return out
