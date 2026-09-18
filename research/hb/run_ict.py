import sys, statistics, random
sys.path.insert(0, 'research/hb')
from ict import load, signals, unit, WARMUP

K_STOP, K_TGT, HORIZON, COOLDOWN = 3.0, 4.0, 20, 20


def simulate(b, i, side, u):
    """Pessimistic: stop is checked before target on every bar."""
    e = b[i]['c']
    sgn = 1 if side == 'LONG' else -1
    stop, tgt = e - sgn * K_STOP * u, e + sgn * K_TGT * u
    for m in range(1, HORIZON + 1):
        if i + m >= len(b):
            return None
        x = b[i + m]
        if (x['l'] <= stop) if side == 'LONG' else (x['h'] >= stop):
            return -K_STOP / K_STOP, m
        if (x['h'] >= tgt) if side == 'LONG' else (x['l'] <= tgt):
            return K_TGT / K_STOP, m
    x = b[i + HORIZON]
    return sgn * (x['c'] - e) / (K_STOP * u), HORIZON


def run(b, sigs, cost_pts, force=None, rand=False, seed=0):
    rg = random.Random(seed)
    busy, out = -1, []
    for i, s in sigs:
        if i < busy:
            continue
        u = unit(b, i)
        side = rg.choice(['LONG', 'SHORT']) if rand else (force or s)
        r = simulate(b, i, side, u)
        if r is None:
            break
        out.append((b[i]['t'], side, r[0] - cost_pts / (K_STOP * u)))
        busy = i + r[1] + COOLDOWN
    return out
